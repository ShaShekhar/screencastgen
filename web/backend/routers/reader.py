"""In-browser reader endpoints: manifest, audio, and page images."""

from __future__ import annotations

import json
import mimetypes
import os
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from screencastgen.reader_assets import AUDIO_NAME, MANIFEST_NAME, PAGES_DIR

from ..database import async_session_factory
from ..models import Job, JobStatus
from ..services.storage import get_output_local_path

router = APIRouter(tags=["reader"])


async def _load_job(job_id: UUID) -> Job:
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


async def _load_ready_job(job_id: UUID) -> Job:
    job = await _load_job(job_id)
    if job.status != JobStatus.completed:
        raise HTTPException(400, "Job output not available")
    return job


def _safe_page_filename(name: str) -> str:
    """Reject paths with traversal characters — only plain basenames allowed."""
    if "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise HTTPException(400, "Invalid page filename")
    return name


def _resolve_reader_asset(job_id: UUID, rel_path: str) -> str | None:
    try:
        path = get_output_local_path(job_id, rel_path)
    except (FileNotFoundError, ValueError):
        return None
    return path if os.path.isfile(path) else None


@router.get("/jobs/{job_id}/reader/status")
async def reader_status(job_id: UUID):
    job = await _load_job(job_id)
    if job.status != JobStatus.completed:
        return JSONResponse(
            {
                "available": False,
                "message": "Job output not available yet.",
            }
        )
    if job.pipeline_type.value != "highlight":
        return JSONResponse(
            {
                "available": False,
                "message": "Browser reader is only available for highlight jobs.",
            }
        )

    path = _resolve_reader_asset(job_id, MANIFEST_NAME)
    if path:
        return JSONResponse({"available": True, "message": "Reader ready."})
    return JSONResponse(
        {
            "available": False,
            "message": "Reader assets were not generated for this job.",
        }
    )


@router.get("/jobs/{job_id}/reader/manifest")
async def reader_manifest(job_id: UUID):
    await _load_ready_job(job_id)
    path = _resolve_reader_asset(job_id, MANIFEST_NAME)
    if not path:
        raise HTTPException(404, "Reader manifest not available for this job")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return JSONResponse(data)


@router.get("/jobs/{job_id}/reader/audio")
async def reader_audio(job_id: UUID):
    await _load_ready_job(job_id)
    path = _resolve_reader_asset(job_id, AUDIO_NAME)
    if not path:
        raise HTTPException(404, "Reader audio not available for this job")
    return FileResponse(path, media_type="audio/mpeg", filename=AUDIO_NAME)


@router.get("/jobs/{job_id}/reader/pages/{filename}")
async def reader_page_image(job_id: UUID, filename: str):
    await _load_ready_job(job_id)
    safe = _safe_page_filename(filename)
    path = _resolve_reader_asset(job_id, f"{PAGES_DIR}/{safe}")
    if not path:
        raise HTTPException(404, "Page image not found")
    media_type, _ = mimetypes.guess_type(safe)
    return FileResponse(path, media_type=media_type or "image/jpeg")
