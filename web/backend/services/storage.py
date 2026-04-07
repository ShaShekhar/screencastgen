"""Local file storage helpers."""

import os
import shutil
import uuid

from ..config import settings


def _resolve_under_root(root: str, *parts: str) -> str:
    """Resolve *parts* under *root* and reject path traversal."""
    root_abs = os.path.abspath(root)
    path_abs = os.path.abspath(os.path.join(root_abs, *parts))
    if os.path.commonpath([root_abs, path_abs]) != root_abs:
        raise ValueError("Path escapes configured storage root")
    return path_abs


def _stored_upload_name(original_name: str) -> str:
    """Generate a safe server-side filename while preserving a simple extension."""
    basename = original_name.replace("\\", "/").rsplit("/", 1)[-1]
    _, ext = os.path.splitext(basename)
    safe_ext = "".join(ch for ch in ext.lower() if ch.isalnum() or ch == ".")
    if not safe_ext.startswith("."):
        safe_ext = ""
    if len(safe_ext) > 16:
        safe_ext = safe_ext[:16]
    return f"upload{safe_ext}"


def save_upload(content: bytes, original_name: str, file_id: uuid.UUID) -> str:
    """Save uploaded file bytes and return the stored relative path."""
    dir_name = str(file_id)
    dir_path = _resolve_under_root(settings.UPLOAD_DIR, dir_name)
    os.makedirs(dir_path, exist_ok=True)

    stored_path = os.path.join(dir_name, _stored_upload_name(original_name))
    abs_path = _resolve_under_root(settings.UPLOAD_DIR, stored_path)
    with open(abs_path, "wb") as f:
        f.write(content)
    return stored_path


def get_upload_abs_path(stored_path: str) -> str:
    return _resolve_under_root(settings.UPLOAD_DIR, stored_path)


def get_output_dir(job_id: uuid.UUID) -> str:
    path = _resolve_under_root(settings.OUTPUT_DIR, str(job_id))
    os.makedirs(path, exist_ok=True)
    return path


def get_output_abs_path(job_id: uuid.UUID, output_path: str) -> str:
    """Resolve a job output path under the job's output directory."""
    return _resolve_under_root(settings.OUTPUT_DIR, str(job_id), output_path)


def delete_job_files(job_id: uuid.UUID) -> None:
    path = _resolve_under_root(settings.OUTPUT_DIR, str(job_id))
    if os.path.isdir(path):
        shutil.rmtree(path)
