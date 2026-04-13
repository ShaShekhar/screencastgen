"""Storage service – delegates to the configured backend.

The module-level convenience functions preserve the existing API so that
callers (routers, tasks) do not need to change their import lines.
"""

from __future__ import annotations

import uuid

from .storage_backend import (
    GCSStorageBackend,
    LocalStorageBackend,
    S3StorageBackend,
    StorageBackend,
)
from ..config import settings


def _create_backend() -> StorageBackend:
    kind = settings.STORAGE_BACKEND.lower()
    if kind == "gcs":
        return GCSStorageBackend(
            bucket_name=settings.STORAGE_BUCKET,
            prefix=settings.STORAGE_PREFIX,
            local_cache_dir=settings.STORAGE_LOCAL_CACHE_DIR,
            output_dir=settings.OUTPUT_DIR,
        )
    if kind == "s3":
        return S3StorageBackend(
            bucket_name=settings.STORAGE_BUCKET,
            prefix=settings.STORAGE_PREFIX,
            region=settings.STORAGE_REGION,
            local_cache_dir=settings.STORAGE_LOCAL_CACHE_DIR,
            output_dir=settings.OUTPUT_DIR,
        )
    return LocalStorageBackend(
        upload_dir=settings.UPLOAD_DIR,
        output_dir=settings.OUTPUT_DIR,
    )


_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """Return the singleton ``StorageBackend`` instance."""
    global _backend
    if _backend is None:
        _backend = _create_backend()
    return _backend


# ------------------------------------------------------------------
# Convenience wrappers (same signatures the rest of the app uses)
# ------------------------------------------------------------------

def save_upload(content: bytes, original_name: str, file_id: uuid.UUID) -> str:
    return get_storage_backend().save_upload(content, original_name, file_id)


def get_upload_abs_path(stored_path: str) -> str:
    return get_storage_backend().get_upload_local_path(stored_path)


def get_output_dir(job_id: uuid.UUID) -> str:
    return get_storage_backend().get_output_dir(job_id)


def get_output_abs_path(job_id: uuid.UUID, output_path: str) -> str:
    return get_storage_backend().get_output_local_path(job_id, output_path)


def get_output_local_path(job_id: uuid.UUID, output_path: str) -> str:
    """Return a local path for a job output, downloading from remote storage if needed."""
    return get_storage_backend().get_output_local_path(job_id, output_path)


def upload_output(job_id: uuid.UUID, output_path: str) -> None:
    return get_storage_backend().upload_output(job_id, output_path)


def get_download_response(job_id: uuid.UUID, output_path: str):
    return get_storage_backend().get_download_response(job_id, output_path)


def delete_job_files(job_id: uuid.UUID) -> None:
    return get_storage_backend().delete_job_files(job_id)
