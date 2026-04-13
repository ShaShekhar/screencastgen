"""Celery tasks that execute screencastgen pipelines."""

from __future__ import annotations

import logging
import os
import sys
import traceback
import uuid
from typing import Optional

from screencastgen.aligner import get_default_alignment_provider
from screencastgen.constants import (
    DEFAULT_FONT_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_STATUS_FILE,
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
)
from screencastgen.lipsync import get_default_lipsync_provider
from screencastgen.pipelines import PipelineReporter
from screencastgen.pipelines.audio import run_audio_pipeline
from screencastgen.pipelines.highlight import run_highlight_pipeline
from screencastgen.pipelines.lipsync import run_lipsync_pipeline
from screencastgen.pipelines.types import (
    AudioPipelineRequest,
    HighlightPipelineRequest,
    LipsyncPipelineRequest,
)

from .celery_app import celery_app
from .progress import JobProgressReporter
from ..config import settings
from ..database import get_sync_session
from ..models import Job, JobStatus, UploadedFile
from ..services.storage import get_upload_abs_path, get_output_dir, upload_output

logger = logging.getLogger(__name__)


def _build_audio_request(job: Job, pdf_path: str, output_dir: str) -> AudioPipelineRequest:
    cfg = job.config_json or {}
    output_filename = os.path.splitext(os.path.basename(pdf_path))[0] + ".wav"

    return AudioPipelineRequest(
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
        no_concat=False,
    )


def _resolve_highlight_voice(
    cfg: dict, job: Job, db_session
) -> tuple[Optional[str], Optional[str]]:
    """Resolve the (ref_audio_path, ref_text) to use for the highlight job.

    Priority:
        1. Bundled voice id (``voice_id`` in cfg) — looks up the manifest.
        2. Uploaded reference audio file (``ref_audio_file_id`` in cfg or
           ``job.ref_audio_file_id``).
        3. None — backend uses its built-in default voice.
    """
    voice_id = cfg.get("voice_id")
    if voice_id:
        # Imported lazily so the worker doesn't pull voices on import.
        from ..services.voices import get_voice

        voice = get_voice(voice_id)
        if voice and voice.exists:
            return voice.abs_path, cfg.get("ref_text") or voice.ref_text
        logger.warning("Bundled voice '%s' not found or missing audio", voice_id)

    ref_id = cfg.get("ref_audio_file_id") or job.ref_audio_file_id
    if ref_id:
        try:
            ref_uuid = uuid.UUID(str(ref_id))
        except ValueError:
            ref_uuid = None
        if ref_uuid:
            uploaded = db_session.get(UploadedFile, ref_uuid)
            if uploaded:
                return get_upload_abs_path(uploaded.stored_path), cfg.get("ref_text")

    return None, cfg.get("ref_text")


def _build_highlight_request(
    job: Job,
    pdf_path: str,
    output_dir: str,
    db_session,
) -> HighlightPipelineRequest:
    cfg = job.config_json or {}
    fmt = cfg.get("format", "epub")
    if fmt not in ("epub", "mp4"):
        fmt = "epub"
    output_filename = (
        os.path.splitext(os.path.basename(pdf_path))[0] + f"_highlight.{fmt}"
    )

    ref_audio_path, ref_text = _resolve_highlight_voice(cfg, job, db_session)

    return HighlightPipelineRequest(
        pdf=pdf_path,
        output=output_filename,
        format=fmt,
        output_dir=output_dir,
        backend=cfg.get("backend", "remote"),
        voice=cfg.get("voice"),
        language=cfg.get("language", DEFAULT_LANGUAGE),
        model=cfg.get("model"),
        ref_audio=ref_audio_path,
        ref_text=ref_text,
        device=cfg.get("device", "auto"),
        tts_server_url=cfg.get("tts_server_url", settings.TTS_SERVER_URL),
        aligner=cfg.get("aligner", get_default_alignment_provider()),
        status_file=DEFAULT_STATUS_FILE,
        clean=False,
        verbose=True,
        font_size=cfg.get("font_size", DEFAULT_FONT_SIZE),
        resolution=f"{cfg.get('width', DEFAULT_VIDEO_WIDTH)}x{cfg.get('height', DEFAULT_VIDEO_HEIGHT)}",
        fps=cfg.get("fps", DEFAULT_VIDEO_FPS),
    )


def _build_lipsync_request(
    job: Job,
    pdf_path: str,
    output_dir: str,
    db_session,
) -> LipsyncPipelineRequest:
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

    return LipsyncPipelineRequest(
        pdf=pdf_path,
        output=output_filename,
        format="mp4",
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
        face_position=cfg.get("face_position", "bottom-right"),
        face_scale=cfg.get("face_scale", 0.22),
        latentsync_preset=cfg.get("latentsync_preset", "quality"),
        font_size=cfg.get("font_size", DEFAULT_FONT_SIZE),
        resolution=f"{cfg.get('width', DEFAULT_VIDEO_WIDTH)}x{cfg.get('height', DEFAULT_VIDEO_HEIGHT)}",
        fps=cfg.get("fps", DEFAULT_VIDEO_FPS),
    )


@celery_app.task(bind=True, max_retries=0)
def run_pipeline_task(self, job_id: str):
    """Execute the appropriate screencastgen pipeline for a job."""
    logger.info("Starting pipeline task for job %s", job_id)
    db_session = get_sync_session()

    try:
        job = db_session.get(Job, uuid.UUID(job_id))
        if not job:
            logger.error("Job %s not found in database", job_id)
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

        pipeline_type = job.pipeline_type.value
        if pipeline_type == "audio":
            request = _build_audio_request(job, pdf_path, output_dir)
            pipeline_func = run_audio_pipeline
        elif pipeline_type == "highlight":
            request = _build_highlight_request(job, pdf_path, output_dir, db_session)
            pipeline_func = run_highlight_pipeline
        elif pipeline_type == "lipsync":
            request = _build_lipsync_request(job, pdf_path, output_dir, db_session)
            pipeline_func = run_lipsync_pipeline
        else:
            job.status = JobStatus.failed
            job.error_message = f"Unknown pipeline type: {pipeline_type}"
            db_session.commit()
            return {"error": "Unknown pipeline"}

        progress = JobProgressReporter(job_id=job_id, db_session=db_session)
        reporter = PipelineReporter(stream=sys.stdout, on_event=progress.handle_event)

        logger.info(
            "Dispatching %s pipeline for job %s (pdf=%s, output_dir=%s)",
            pipeline_type, job_id, pdf_path, output_dir,
        )
        try:
            result = pipeline_func(request, reporter=reporter)
            if result.exit_code == 0 and result.output_path and os.path.isfile(result.output_path):
                upload_output(uuid.UUID(job_id), result.output_name)
                job.status = JobStatus.completed
                job.progress_phase = "done"
                job.error_message = None
                job.output_path = result.output_name
                logger.info(
                    "Job %s completed -> %s", job_id, result.output_path
                )
            else:
                job.status = JobStatus.failed
                job.error_message = result.error_message or f"Pipeline returned exit code {result.exit_code}"
                logger.error(
                    "Job %s failed (exit=%s): %s",
                    job_id, result.exit_code, job.error_message,
                )
        except Exception as exc:
            tb = traceback.format_exc()
            logger.exception("Pipeline crashed for job %s", job_id)
            job.status = JobStatus.failed
            job.error_message = f"{exc}\n\n{tb}"
        finally:
            db_session.commit()
            progress.publish_terminal(
                status=job.status.value,
                phase=job.progress_phase or "done",
                current=job.progress_current,
                total=job.progress_total,
                message=job.error_message or "",
            )
            progress.close()

        return {"status": job.status.value}
    finally:
        db_session.close()
