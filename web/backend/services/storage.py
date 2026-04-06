"""Local file storage helpers."""

import os
import shutil
import uuid

from ..config import settings


def save_upload(content: bytes, original_name: str, file_id: uuid.UUID) -> str:
    """Save uploaded file bytes and return the stored relative path."""
    dir_path = os.path.join(settings.UPLOAD_DIR, str(file_id))
    os.makedirs(dir_path, exist_ok=True)
    stored_path = os.path.join(str(file_id), original_name)
    abs_path = os.path.join(settings.UPLOAD_DIR, stored_path)
    with open(abs_path, "wb") as f:
        f.write(content)
    return stored_path


def get_upload_abs_path(stored_path: str) -> str:
    return os.path.join(settings.UPLOAD_DIR, stored_path)


def get_output_dir(job_id: uuid.UUID) -> str:
    path = os.path.join(settings.OUTPUT_DIR, str(job_id))
    os.makedirs(path, exist_ok=True)
    return path


def delete_job_files(job_id: uuid.UUID) -> None:
    path = os.path.join(settings.OUTPUT_DIR, str(job_id))
    if os.path.isdir(path):
        shutil.rmtree(path)
