"""File upload endpoint."""

import uuid

from fastapi import APIRouter, HTTPException, UploadFile

from ..config import settings
from ..database import get_async_session, async_session_factory
from ..models import UploadedFile
from ..schemas import UploadResponse
from ..services.storage import save_upload

router = APIRouter(tags=["uploads"])


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
    stored_path = save_upload(content, file.filename, file_id)

    db_file = UploadedFile(
        id=file_id,
        original_name=file.filename,
        stored_path=stored_path,
        size_bytes=size,
        content_type=file.content_type or "application/octet-stream",
    )

    async with async_session_factory() as session:
        session.add(db_file)
        await session.commit()

    return UploadResponse(
        id=file_id,
        original_name=file.filename,
        size_bytes=size,
        content_type=db_file.content_type,
    )
