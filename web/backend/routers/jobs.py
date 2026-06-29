"""Job CRUD and download endpoints."""

import json
import logging
import os
from uuid import UUID

import redis
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from ..config import settings
from ..database import async_session_factory
from ..models import Job, JobStatus, PipelineType, UploadedFile
from ..schemas import JobCreateRequest, JobListResponse, JobResponse
from screencastgen.offline_reader import build_offline_reader_archive
from screencastgen.reader_assets import MANIFEST_NAME, refresh_manifest_source

from ..services.storage import (
    delete_job_files,
    get_download_response,
    get_output_local_path,
    get_upload_abs_path,
    upload_output,
)

router = APIRouter(tags=["jobs"])
logger = logging.getLogger(__name__)


def _build_config(req: JobCreateRequest) -> dict:
    """Build config_json dict from the request."""
    if req.pipeline_type == "audio" and req.audio_config:
        return req.audio_config.model_dump()
    elif req.pipeline_type == "highlight" and req.highlight_config:
        cfg = req.highlight_config.model_dump()
        if cfg.get("ref_audio_file_id") is not None:
            cfg["ref_audio_file_id"] = str(cfg["ref_audio_file_id"])
        return cfg
    elif req.pipeline_type == "lipsync" and req.lipsync_config:
        cfg = req.lipsync_config.model_dump()
        if cfg.get("ref_audio_file_id") is not None:
            cfg["ref_audio_file_id"] = str(cfg["ref_audio_file_id"])
        if cfg.get("ref_video_file_id") is not None:
            cfg["ref_video_file_id"] = str(cfg["ref_video_file_id"])
        return cfg
    elif req.pipeline_type == "visualization" and req.visualization_config:
        cfg = req.visualization_config.model_dump()
        if cfg.get("iteration_of_job_id") is not None:
            cfg["iteration_of_job_id"] = str(cfg["iteration_of_job_id"])
        return cfg
    # Use defaults
    return {}


def _refresh_reader_archive_for_download(job: Job, uploaded: UploadedFile | None) -> None:
    """Rebuild reader ZIPs so downloads use the current offline reader HTML."""
    if (
        job.pipeline_type not in (PipelineType.highlight, PipelineType.lipsync)
        or not job.output_path
        or not job.output_path.lower().endswith(".zip")
    ):
        return

    try:
        manifest_path = get_output_local_path(job.id, MANIFEST_NAME)
    except FileNotFoundError:
        return
    if not os.path.isfile(manifest_path):
        return

    if uploaded:
        try:
            if refresh_manifest_source(manifest_path, get_upload_abs_path(uploaded.stored_path)):
                upload_output(job.id, MANIFEST_NAME)
            with open(manifest_path, "r", encoding="utf-8") as fh:
                source_file = (json.load(fh) or {}).get("source_file")
            if source_file:
                upload_output(job.id, str(source_file))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Reader source refresh failed for job %s: %s", job.id, exc)

    try:
        archive_path = get_output_local_path(job.id, job.output_path)
    except FileNotFoundError:
        return
    build_offline_reader_archive(manifest_path, archive_path)
    upload_output(job.id, job.output_path)


@router.post("/jobs", response_model=JobResponse)
async def create_job(req: JobCreateRequest):
    async with async_session_factory() as session:
        try:
            pipeline_type = PipelineType(req.pipeline_type)
        except ValueError as exc:
            raise HTTPException(400, f"Unknown pipeline type: {req.pipeline_type}") from exc

        if pipeline_type != PipelineType.visualization:
            uploaded = await session.get(UploadedFile, req.uploaded_file_id)
            if not uploaded:
                raise HTTPException(404, "Uploaded file not found")

        ref_audio_id = None
        ref_video_id = None
        if req.pipeline_type == "lipsync" and req.lipsync_config:
            if req.lipsync_config.preset_id:
                from ..services.lipsync_presets import get_lipsync_preset

                preset = get_lipsync_preset(req.lipsync_config.preset_id)
                if not preset:
                    raise HTTPException(404, "Lip-sync preset not found")
                if not preset.exists:
                    raise HTTPException(
                        404,
                        f"Lip-sync preset '{preset.id}' is missing its backing files",
                    )
            else:
                ref_audio_id = req.lipsync_config.ref_audio_file_id
                ref_video_id = req.lipsync_config.ref_video_file_id
                refs = [(ref_video_id, "Reference video")]
                if ref_audio_id:
                    refs.append((ref_audio_id, "Reference audio"))
                for fid, label in refs:
                    f = await session.get(UploadedFile, fid)
                    if not f:
                        raise HTTPException(404, f"{label} file not found")
        elif req.pipeline_type == "highlight" and req.highlight_config:
            if req.highlight_config.ref_audio_file_id:
                ref_audio_id = req.highlight_config.ref_audio_file_id
                f = await session.get(UploadedFile, ref_audio_id)
                if not f:
                    raise HTTPException(404, "Reference audio file not found")

        config = _build_config(req)

        job = Job(
            pipeline_type=pipeline_type,
            status=JobStatus.pending,
            config_json=config,
            uploaded_file_id=req.uploaded_file_id,
            ref_audio_file_id=ref_audio_id,
            ref_video_file_id=ref_video_id,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        # Dispatch Celery task
        from ..tasks.pipelines import run_pipeline_task
        task = run_pipeline_task.delay(str(job.id))
        job.celery_task_id = task.id
        await session.commit()
        await session.refresh(job)

    return JobResponse.model_validate(job)


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    async with async_session_factory() as session:
        q = select(Job).order_by(Job.created_at.desc())
        count_q = select(func.count(Job.id))

        if status:
            q = q.where(Job.status == JobStatus(status))
            count_q = count_q.where(Job.status == JobStatus(status))

        total = (await session.execute(count_q)).scalar() or 0
        result = await session.execute(q.offset(offset).limit(limit))
        jobs = result.scalars().all()

    return JobListResponse(
        jobs=[JobResponse.model_validate(j) for j in jobs],
        total=total,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return JobResponse.model_validate(job)


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: UUID):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")

        # Revoke Celery task if running
        if job.status in (JobStatus.pending, JobStatus.running) and job.celery_task_id:
            from ..tasks.celery_app import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)

        delete_job_files(job_id)
        await session.delete(job)
        await session.commit()

    return {"detail": "deleted"}


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: UUID):
    """Request that a running lip-sync job stop.

    The page currently generating on the GPU is abandoned; the worker then
    builds the reader output from the pages already completed.
    """
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.pipeline_type != PipelineType.lipsync:
            raise HTTPException(400, "Stop is only supported for lip-sync jobs")
        if job.status not in (JobStatus.pending, JobStatus.running):
            raise HTTPException(400, "Job is not running")

    # The running worker polls this Redis flag between/within pages.
    client = redis.Redis.from_url(settings.REDIS_URL)
    try:
        client.set(f"job:{job_id}:cancel", "1", ex=86400)
    finally:
        client.close()
    return {"detail": "stop requested"}


@router.get("/jobs/{job_id}/download")
async def download_job(job_id: UUID):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.status != JobStatus.completed or not job.output_path:
            raise HTTPException(400, "Job output not available")

        try:
            uploaded = (
                await session.get(UploadedFile, job.uploaded_file_id)
                if job.uploaded_file_id
                else None
            )
            _refresh_reader_archive_for_download(job, uploaded)
            return get_download_response(job_id, job.output_path)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except FileNotFoundError:
            raise HTTPException(404, "Output file not found")


@router.post("/jobs/{job_id}/export-mp4")
async def export_lipsync_mp4(job_id: UUID):
    """Trigger an on-demand baked-MP4 export for a completed lip-sync job."""
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.pipeline_type != PipelineType.lipsync:
            raise HTTPException(400, "MP4 export is only available for lip-sync jobs")
        if job.status != JobStatus.completed:
            raise HTTPException(400, "Job output not available")

        cfg = dict(job.config_json or {})
        if cfg.get("export_status") == "running":
            return {"export_status": "running"}

        cfg["export_status"] = "running"
        cfg.pop("export_error", None)
        cfg.pop("export_output", None)
        job.config_json = cfg
        await session.commit()

        from ..tasks.pipelines import run_lipsync_export_task

        run_lipsync_export_task.delay(str(job_id))
        return {"export_status": "running"}


@router.get("/jobs/{job_id}/export-mp4/status")
async def export_lipsync_mp4_status(job_id: UUID):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        cfg = job.config_json or {}
        return {
            "export_status": cfg.get("export_status"),
            "export_output": cfg.get("export_output"),
            "export_error": cfg.get("export_error"),
        }


@router.get("/jobs/{job_id}/export-mp4/download")
async def export_lipsync_mp4_download(job_id: UUID):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        cfg = job.config_json or {}
        output = cfg.get("export_output")
        if cfg.get("export_status") != "done" or not output:
            raise HTTPException(400, "Exported MP4 not available")

        try:
            return get_download_response(job_id, output)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except FileNotFoundError:
            raise HTTPException(404, "Exported file not found")


@router.post("/jobs/{job_id}/export-epub")
async def export_lipsync_epub(job_id: UUID):
    """Trigger an on-demand narration-and-text EPUB export."""
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.pipeline_type != PipelineType.lipsync:
            raise HTTPException(400, "EPUB export is only available for lip-sync jobs")
        if job.status != JobStatus.completed:
            raise HTTPException(400, "Job output not available")

        cfg = dict(job.config_json or {})
        if cfg.get("epub_export_status") == "running":
            return {"export_status": "running"}

        cfg["epub_export_status"] = "running"
        cfg.pop("epub_export_error", None)
        cfg.pop("epub_export_output", None)
        job.config_json = cfg
        await session.commit()

        from ..tasks.pipelines import run_lipsync_epub_export_task

        run_lipsync_epub_export_task.delay(str(job_id))
        return {"export_status": "running"}


@router.get("/jobs/{job_id}/export-epub/status")
async def export_lipsync_epub_status(job_id: UUID):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        cfg = job.config_json or {}
        return {
            "export_status": cfg.get("epub_export_status"),
            "export_output": cfg.get("epub_export_output"),
            "export_error": cfg.get("epub_export_error"),
        }


@router.get("/jobs/{job_id}/export-epub/download")
async def export_lipsync_epub_download(job_id: UUID):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        cfg = job.config_json or {}
        output = cfg.get("epub_export_output")
        if cfg.get("epub_export_status") != "done" or not output:
            raise HTTPException(400, "Exported EPUB not available")

        try:
            return get_download_response(job_id, output)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except FileNotFoundError:
            raise HTTPException(404, "Exported file not found")
