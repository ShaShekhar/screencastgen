"""File upload endpoint."""

import logging
import uuid

from fastapi import APIRouter, HTTPException, UploadFile

from ..config import settings
from ..database import async_session_factory
from ..models import UploadedFile
from ..schemas import UploadResponse
from ..services.storage import get_upload_abs_path, save_upload
from ..services.transcribe_client import transcribe_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["uploads"])


def _looks_like_audio(filename: str, content_type: str) -> bool:
    if content_type and content_type.lower().startswith("audio/"):
        return True
    lower = (filename or "").lower()
    return lower.endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"))


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
