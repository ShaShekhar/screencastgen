"""Celery tasks that execute screencastgen pipelines."""

import argparse
import json
import os
import sys
import uuid

from .celery_app import celery_app
from ..config import settings
from ..database import get_sync_session
from ..models import Job, JobStatus, UploadedFile
from ..services.storage import get_output_abs_path, get_upload_abs_path, get_output_dir
from .progress import ProgressBridge

from screencastgen.constants import (
    DEFAULT_FONT_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_STATUS_FILE,
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
)
from screencastgen.aligner import get_default_alignment_provider
from screencastgen.lipsync import get_default_lipsync_provider


def _build_audio_args(job: Job, pdf_path: str, output_dir: str) -> argparse.Namespace:
    cfg = job.config_json or {}
    backend = cfg.get("backend", "remote")
    output_filename = os.path.splitext(os.path.basename(pdf_path))[0] + ".wav"

    return argparse.Namespace(
        pdf=pdf_path,
        output=output_filename,
        output_dir=output_dir,
        backend=backend,
        voice=cfg.get("voice"),
        language=cfg.get("language", DEFAULT_LANGUAGE),
        model=cfg.get("model"),
        ref_audio=cfg.get("ref_audio"),
        ref_text=cfg.get("ref_text"),
        device=cfg.get("device", "auto"),
        tts_server_url=cfg.get("tts_server_url", settings.TTS_SERVER_URL),
        aligner=cfg.get("aligner", get_default_alignment_provider()),
        status_file=DEFAULT_STATUS_FILE,
        clean=False,
        verbose=True,
        no_concat=False,
        command="audio",
    )


def _build_highlight_args(job: Job, pdf_path: str, output_dir: str) -> argparse.Namespace:
    cfg = job.config_json or {}
    output_filename = os.path.splitext(os.path.basename(pdf_path))[0] + "_highlight.mp4"

    return argparse.Namespace(
        pdf=pdf_path,
        output=output_filename,
        output_dir=output_dir,
        backend=cfg.get("backend", "remote"),
        voice=cfg.get("voice"),
        language=cfg.get("language", DEFAULT_LANGUAGE),
        model=cfg.get("model"),
        ref_audio=cfg.get("ref_audio"),
        ref_text=cfg.get("ref_text"),
        device=cfg.get("device", "auto"),
        tts_server_url=cfg.get("tts_server_url", settings.TTS_SERVER_URL),
        aligner=cfg.get("aligner", get_default_alignment_provider()),
        status_file=DEFAULT_STATUS_FILE,
        clean=False,
        verbose=True,
        font_size=cfg.get("font_size", DEFAULT_FONT_SIZE),
        resolution=f"{cfg.get('width', DEFAULT_VIDEO_WIDTH)}x{cfg.get('height', DEFAULT_VIDEO_HEIGHT)}",
        fps=cfg.get("fps", DEFAULT_VIDEO_FPS),
        command="highlight",
    )


def _build_lipsync_args(job: Job, pdf_path: str, output_dir: str, db_session) -> argparse.Namespace:
    cfg = job.config_json or {}
    output_filename = os.path.splitext(os.path.basename(pdf_path))[0] + "_lipsync.mp4"

    ref_audio_path = ""
    ref_video_path = ""
    if job.ref_audio_file_id:
        ref_audio = db_session.get(UploadedFile, job.ref_audio_file_id)
        if ref_audio:
            ref_audio_path = get_upload_abs_path(ref_audio.stored_path)
    if job.ref_video_file_id:
        ref_video = db_session.get(UploadedFile, job.ref_video_file_id)
        if ref_video:
            ref_video_path = get_upload_abs_path(ref_video.stored_path)

    return argparse.Namespace(
        pdf=pdf_path,
        output=output_filename,
        output_dir=output_dir,
        backend=cfg.get("backend", "remote"),
        voice=cfg.get("voice"),
        language=cfg.get("language", DEFAULT_LANGUAGE),
        model=cfg.get("model"),
        tts_server_url=cfg.get("tts_server_url", settings.TTS_SERVER_URL),
        status_file=DEFAULT_STATUS_FILE,
        clean=False,
        verbose=True,
        ref_audio=ref_audio_path,
        ref_video=ref_video_path,
        ref_text=cfg.get("ref_text"),
        device=cfg.get("device", "auto"),
        aligner=cfg.get("aligner", get_default_alignment_provider()),
        lipsync_provider=cfg.get("lipsync_provider", get_default_lipsync_provider()),
        face_position=cfg.get("face_position", "left"),
        font_size=cfg.get("font_size", DEFAULT_FONT_SIZE),
        resolution=f"{cfg.get('width', DEFAULT_VIDEO_WIDTH)}x{cfg.get('height', DEFAULT_VIDEO_HEIGHT)}",
        fps=cfg.get("fps", DEFAULT_VIDEO_FPS),
        command="lipsync",
    )


@celery_app.task(bind=True, max_retries=0)
def run_pipeline_task(self, job_id: str):
    """Execute the appropriate screencastgen pipeline for a job."""
    from screencastgen.cli import run_audio_pipeline, run_highlight_pipeline, run_lipsync_pipeline

    db_session = get_sync_session()

    try:
        job = db_session.get(Job, uuid.UUID(job_id))
        if not job:
            return {"error": "Job not found"}

        job.status = JobStatus.running
        job.celery_task_id = self.request.id
        db_session.commit()

        uploaded_file = db_session.get(UploadedFile, job.uploaded_file_id)
        if not uploaded_file:
            job.status = JobStatus.failed
            job.error_message = "Uploaded file record not found"
            db_session.commit()
            return {"error": "File not found"}

        pdf_path = get_upload_abs_path(uploaded_file.stored_path)
        output_dir = get_output_dir(uuid.UUID(job_id))

        # Build args namespace
        pipeline_type = job.pipeline_type.value
        if pipeline_type == "audio":
            args = _build_audio_args(job, pdf_path, output_dir)
            pipeline_func = run_audio_pipeline
        elif pipeline_type == "highlight":
            args = _build_highlight_args(job, pdf_path, output_dir)
            pipeline_func = run_highlight_pipeline
        elif pipeline_type == "lipsync":
            args = _build_lipsync_args(job, pdf_path, output_dir, db_session)
            pipeline_func = run_lipsync_pipeline
        else:
            job.status = JobStatus.failed
            job.error_message = f"Unknown pipeline type: {pipeline_type}"
            db_session.commit()
            return {"error": "Unknown pipeline"}

        # Install progress bridge
        bridge = ProgressBridge(
            job_id=job_id,
            db_session=db_session,
            fallback_stdout=sys.stdout,
        )
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = bridge
        sys.stderr = bridge

        try:
            exit_code = pipeline_func(args)
            if exit_code == 0:
                output_path = get_output_abs_path(uuid.UUID(job_id), args.output)
                if os.path.isfile(output_path):
                    job.status = JobStatus.completed
                    job.progress_phase = "done"
                    job.error_message = None
                    job.output_path = args.output
                else:
                    job.status = JobStatus.failed
                    job.error_message = f"Pipeline completed without producing output: {args.output}"
            else:
                job.status = JobStatus.failed
                job.error_message = f"Pipeline returned exit code {exit_code}"
        except SystemExit as e:
            job.status = JobStatus.failed
            job.error_message = (
                "; ".join(bridge.captured_errors)
                if bridge.captured_errors
                else f"Pipeline exited with code {e.code}"
            )
        except Exception as e:
            job.status = JobStatus.failed
            job.error_message = str(e)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            bridge.close()
            db_session.commit()

            # Publish terminal event
            import redis as redis_lib
            try:
                r = redis_lib.Redis.from_url(settings.REDIS_URL)
                r.publish(f"job:{job_id}:progress", json.dumps({
                    "job_id": job_id,
                    "status": job.status.value,
                    "phase": job.progress_phase or "done",
                    "current": job.progress_current,
                    "total": job.progress_total,
                    "message": job.error_message or "",
                }))
                r.close()
            except Exception:
                pass

        return {"status": job.status.value}

    finally:
        db_session.close()
