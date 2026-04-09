"""Job CRUD and download endpoints."""

import os
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from ..database import async_session_factory
from ..models import Job, JobStatus, PipelineType, UploadedFile
from ..schemas import JobCreateRequest, JobListResponse, JobResponse
from ..services.storage import delete_job_files, get_output_abs_path

router = APIRouter(tags=["jobs"])


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
        cfg["ref_audio_file_id"] = str(cfg["ref_audio_file_id"])
        cfg["ref_video_file_id"] = str(cfg["ref_video_file_id"])
        return cfg
    # Use defaults
    return {}


@router.post("/jobs", response_model=JobResponse)
async def create_job(req: JobCreateRequest):
    async with async_session_factory() as session:
        uploaded = await session.get(UploadedFile, req.uploaded_file_id)
        if not uploaded:
            raise HTTPException(404, "Uploaded file not found")

        ref_audio_id = None
        ref_video_id = None
        if req.pipeline_type == "lipsync" and req.lipsync_config:
            ref_audio_id = req.lipsync_config.ref_audio_file_id
            ref_video_id = req.lipsync_config.ref_video_file_id
            for fid, label in [(ref_audio_id, "Reference audio"), (ref_video_id, "Reference video")]:
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
            pipeline_type=PipelineType(req.pipeline_type),
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


@router.get("/jobs/{job_id}/download")
async def download_job(job_id: UUID):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.status != JobStatus.completed or not job.output_path:
            raise HTTPException(400, "Job output not available")

        try:
            abs_path = get_output_abs_path(job_id, job.output_path)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if not os.path.isfile(abs_path):
            raise HTTPException(404, "Output file not found on disk")

        return FileResponse(abs_path, filename=os.path.basename(abs_path))
