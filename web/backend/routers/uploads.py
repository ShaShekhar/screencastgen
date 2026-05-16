"""File upload endpoint."""

import logging
import mimetypes
import os
import uuid
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import settings
from ..database import async_session_factory
from ..models import UploadedFile
from ..schemas import UploadResponse
from ..services.storage import get_upload_abs_path, save_upload
from ..services.transcribe_client import transcribe_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["uploads"])

PREVIEW_EXTENSIONS = {".pdf", ".txt", ".epub"}


def _looks_like_audio(filename: str, content_type: str) -> bool:
    if content_type and content_type.lower().startswith("audio/"):
        return True
    lower = (filename or "").lower()
    return lower.endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"))


def _preview_media_type(filename: str, content_type: str) -> str:
    guessed, _encoding = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    if content_type and content_type != "application/octet-stream":
        return content_type
    return "application/octet-stream"


@router.post("/uploads", response_model=UploadResponse)
async def upload_file(file: UploadFile):
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    content = await file.read()
    size = len(content)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(413, f"File too large (max {settings.MAX_UPLOAD_SIZE_MB} MB)")

    file_id = uuid.uuid4()
    try:
        stored_path = save_upload(content, file.filename, file_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    content_type = file.content_type or "application/octet-stream"

    ref_text: str | None = None
    if _looks_like_audio(file.filename, content_type):
        try:
            local_path = get_upload_abs_path(stored_path)
            ref_text = transcribe_upload(settings.TTS_SERVER_URL, local_path)
        except Exception:  # noqa: BLE001
            logger.exception("Auto-transcription failed; continuing without ref_text")

    db_file = UploadedFile(
        id=file_id,
        original_name=file.filename,
        stored_path=stored_path,
        size_bytes=size,
        content_type=content_type,
        ref_text=ref_text,
    )

    async with async_session_factory() as session:
        session.add(db_file)
        await session.commit()

    return UploadResponse(
        id=file_id,
        original_name=file.filename,
        size_bytes=size,
        content_type=db_file.content_type,
        ref_text=ref_text,
    )


@router.get("/uploads/{file_id}/preview")
async def preview_upload(file_id: uuid.UUID):
    async with async_session_factory() as session:
        uploaded = await session.get(UploadedFile, file_id)
        if not uploaded:
            raise HTTPException(404, "Uploaded file not found")

    ext = os.path.splitext(uploaded.original_name)[1].lower()
    if ext not in PREVIEW_EXTENSIONS:
        raise HTTPException(400, "Preview is only available for PDF, TXT, and EPUB uploads")

    try:
        local_path = get_upload_abs_path(uploaded.stored_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if not os.path.isfile(local_path):
        raise HTTPException(404, "Uploaded file not found on disk")

    response = FileResponse(
        local_path,
        media_type=_preview_media_type(uploaded.original_name, uploaded.content_type),
    )
    response.headers["Content-Disposition"] = (
        f"inline; filename*=UTF-8''{quote(uploaded.original_name)}"
    )
    return response
