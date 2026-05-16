"""Celery tasks that execute screencastgen pipelines."""

from __future__ import annotations

import logging
import os
import subprocess
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
from screencastgen.pipelines import PipelineReporter
from screencastgen.pipelines.audio import run_audio_pipeline
from screencastgen.pipelines.highlight import run_highlight_pipeline
from screencastgen.pipelines.lipsync import run_lipsync_pipeline
from screencastgen.pipelines.visualization import run_visualization_pipeline
from screencastgen.pipelines.types import (
    AudioPipelineRequest,
    HighlightPipelineRequest,
    LipsyncPipelineRequest,
    VisualizationPipelineRequest,
)

from .celery_app import celery_app
from .progress import JobProgressReporter
from ..config import settings
from ..models import Job, JobStatus, UploadedFile
from ..services.storage import get_upload_abs_path, get_output_dir, upload_output
from ..services.transcribe_client import transcribe_upload

logger = logging.getLogger(__name__)


def _upload_reader_assets(job_id: uuid.UUID, output_dir: str) -> None:
    """Best-effort upload of reader manifest/audio/page images to storage."""
    from screencastgen.reader_assets import AUDIO_NAME, MANIFEST_NAME, PAGES_DIR

    candidates = [MANIFEST_NAME, AUDIO_NAME]
    pages_abs = os.path.join(output_dir, PAGES_DIR)
    if os.path.isdir(pages_abs):
        for name in sorted(os.listdir(pages_abs)):
            candidates.append(f"{PAGES_DIR}/{name}")

    for rel in candidates:
        abs_path = os.path.join(output_dir, rel)
        if not os.path.isfile(abs_path):
            continue
        try:
            upload_output(job_id, rel)
        except Exception as exc:
            logger.warning("Reader asset upload failed for %s: %s", rel, exc)


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
        tts_server_url=cfg.get("tts_server_url") or settings.TTS_SERVER_URL,
        tts_concurrency=int(cfg.get("tts_concurrency", settings.TTS_CONCURRENCY)),
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
                return (
                    get_upload_abs_path(uploaded.stored_path),
                    cfg.get("ref_text") or uploaded.ref_text,
                )

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
        tts_server_url=cfg.get("tts_server_url") or settings.TTS_SERVER_URL,
        tts_concurrency=int(cfg.get("tts_concurrency", settings.TTS_CONCURRENCY)),
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
    ref_text = cfg.get("ref_text")
    ref_video_path = ""
    if job.ref_audio_file_id:
        ref_audio = db_session.get(UploadedFile, job.ref_audio_file_id)
        if ref_audio:
            ref_audio_path = get_upload_abs_path(ref_audio.stored_path)
            ref_text = ref_text or ref_audio.ref_text
    if job.ref_video_file_id:
        ref_video = db_session.get(UploadedFile, job.ref_video_file_id)
        if ref_video:
            ref_video_path = get_upload_abs_path(ref_video.stored_path)

    if not ref_audio_path and ref_video_path:
        ref_audio_path = _extract_reference_audio_from_video(ref_video_path, output_dir)
        ref_text = ref_text or transcribe_upload(
            cfg.get("tts_server_url") or settings.TTS_SERVER_URL,
            ref_audio_path,
            language=cfg.get("language", DEFAULT_LANGUAGE),
        )

    return LipsyncPipelineRequest(
        pdf=pdf_path,
        output=output_filename,
        format="mp4",
        output_dir=output_dir,
        backend=cfg.get("backend", "remote"),
        voice=cfg.get("voice"),
        language=cfg.get("language", DEFAULT_LANGUAGE),
        model=cfg.get("model"),
        tts_server_url=cfg.get("tts_server_url") or settings.TTS_SERVER_URL,
        tts_concurrency=int(cfg.get("tts_concurrency", settings.TTS_CONCURRENCY)),
        status_file=DEFAULT_STATUS_FILE,
        clean=False,
        verbose=True,
        ref_audio=ref_audio_path,
        ref_video=ref_video_path,
        ref_text=ref_text,
        device="auto",
        aligner=cfg.get("aligner", get_default_alignment_provider()),
        lipsync_provider="latentsync",
        face_position=cfg.get("face_position", "bottom-right"),
        face_scale=cfg.get("face_scale", 0.22),
        latentsync_preset=cfg.get("latentsync_preset", "quality"),
        font_size=cfg.get("font_size", DEFAULT_FONT_SIZE),
        resolution=f"{cfg.get('width', DEFAULT_VIDEO_WIDTH)}x{cfg.get('height', DEFAULT_VIDEO_HEIGHT)}",
        fps=cfg.get("fps", DEFAULT_VIDEO_FPS),
    )


def _extract_reference_audio_from_video(video_path: str, output_dir: str) -> str:
    """Extract a short mono WAV from a reference video for voice cloning."""
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, "reference_video_audio.wav")
    if os.path.isfile(audio_path) and os.path.getsize(audio_path) > 0:
        return audio_path

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-t",
        "30",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(audio_path) or os.path.getsize(audio_path) == 0:
        detail = (result.stderr or result.stdout or "").strip()
        msg = "Reference video does not contain usable audio. Upload a reference audio override."
        if detail:
            logger.warning("Reference audio extraction failed: %s", detail[-1000:])
        raise ValueError(msg)
    return audio_path


def _build_visualization_request(job: Job, output_dir: str) -> VisualizationPipelineRequest:
    cfg = job.config_json or {}
    output_filename = "visualization.mp4"

    return VisualizationPipelineRequest(
        prompt=cfg.get("prompt", ""),
        output=cfg.get("output") or output_filename,
        output_dir=output_dir,
        provider=cfg.get("provider", "manimgl"),
        duration_seconds=int(cfg.get("duration_seconds", 30)),
        resolution=f"{cfg.get('width', DEFAULT_VIDEO_WIDTH)}x{cfg.get('height', DEFAULT_VIDEO_HEIGHT)}",
        fps=int(cfg.get("fps", DEFAULT_VIDEO_FPS)),
        style=cfg.get("style", "clean"),
        audience_level=cfg.get("audience_level", "general"),
        iteration_of_job_id=cfg.get("iteration_of_job_id"),
        clean=False,
        verbose=True,
    )


def _build_pipeline_dispatch(
    job: Job,
    pdf_path: Optional[str],
    output_dir: str,
    db_session,
):
    pipeline_type = job.pipeline_type.value
    if pipeline_type == "audio":
        if not pdf_path:
            raise ValueError("Uploaded file path is required for audio jobs")
        return _build_audio_request(job, pdf_path, output_dir), run_audio_pipeline
    if pipeline_type == "highlight":
        if not pdf_path:
            raise ValueError("Uploaded file path is required for highlight jobs")
        return _build_highlight_request(job, pdf_path, output_dir, db_session), run_highlight_pipeline
    if pipeline_type == "lipsync":
        if not pdf_path:
            raise ValueError("Uploaded file path is required for lipsync jobs")
        return _build_lipsync_request(job, pdf_path, output_dir, db_session), run_lipsync_pipeline
    if pipeline_type == "visualization":
        return _build_visualization_request(job, output_dir), run_visualization_pipeline
    raise ValueError(f"Unknown pipeline type: {pipeline_type}")


@celery_app.task(bind=True, max_retries=0)
def run_pipeline_task(self, job_id: str):
    """Execute the appropriate screencastgen pipeline for a job."""
    from ..database import get_sync_session

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

        pdf_path = None
        if job.pipeline_type.value != "visualization":
            uploaded_file = db_session.get(UploadedFile, job.uploaded_file_id)
            if not uploaded_file:
                job.status = JobStatus.failed
                job.error_message = "Uploaded file record not found"
                db_session.commit()
                return {"error": "File not found"}
            pdf_path = get_upload_abs_path(uploaded_file.stored_path)
        output_dir = get_output_dir(uuid.UUID(job_id))

        try:
            request, pipeline_func = _build_pipeline_dispatch(job, pdf_path, output_dir, db_session)
        except ValueError as exc:
            job.status = JobStatus.failed
            job.error_message = str(exc)
            db_session.commit()
            return {"error": str(exc)}

        pipeline_type = job.pipeline_type.value

        progress = JobProgressReporter(job_id=job_id, db_session=db_session)
        reporter = PipelineReporter(stream=sys.stdout, on_event=progress.handle_event)

        logger.info(
            "Dispatching %s pipeline for job %s (pdf=%s, output_dir=%s)",
            pipeline_type, job_id, pdf_path, output_dir,
        )
        try:
            result = pipeline_func(request, reporter=reporter)
            if result.metadata:
                cfg = dict(job.config_json or {})
                cfg["visualization_result" if pipeline_type == "visualization" else "pipeline_result"] = result.metadata
                job.config_json = cfg
            if result.exit_code == 0 and result.output_path and os.path.isfile(result.output_path):
                upload_output(uuid.UUID(job_id), result.output_name)
                if pipeline_type == "highlight":
                    _upload_reader_assets(uuid.UUID(job_id), output_dir)
                if pipeline_type == "visualization":
                    for rel in ("generated_visualization.py", "visualization_metadata.json"):
                        if os.path.isfile(os.path.join(output_dir, rel)):
                            try:
                                upload_output(uuid.UUID(job_id), rel)
                            except Exception as exc:
                                logger.warning("Visualization artefact upload failed for %s: %s", rel, exc)
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
