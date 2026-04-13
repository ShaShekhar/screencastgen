"""Pluggable storage backend abstraction.

Provides a ``StorageBackend`` interface with three implementations:

* **LocalStorageBackend** – files on the local filesystem (default).
* **GCSStorageBackend** – Google Cloud Storage (requires ``google-cloud-storage``).
* **S3StorageBackend** – Amazon S3 (requires ``boto3``).

Pipelines always work against local directories for intermediate files.
Remote backends download uploads to a local cache and upload final outputs
to the bucket after the pipeline completes.
"""

from __future__ import annotations

import abc
import os
import shutil
import uuid


# -------------------------------------------------------------------
# Abstract base
# -------------------------------------------------------------------

class StorageBackend(abc.ABC):
    """Abstract file-storage interface."""

    @abc.abstractmethod
    def save_upload(self, content: bytes, original_name: str, file_id: uuid.UUID) -> str:
        """Persist uploaded file bytes and return a ``stored_path`` key."""

    @abc.abstractmethod
    def get_upload_local_path(self, stored_path: str) -> str:
        """Return a local filesystem path for the stored upload.

        Local backend: returns the canonical path directly.
        Remote backends: downloads the object to a cache dir first.
        """

    @abc.abstractmethod
    def get_output_dir(self, job_id: uuid.UUID) -> str:
        """Return (and create) a local directory for pipeline working files."""

    @abc.abstractmethod
    def get_output_local_path(self, job_id: uuid.UUID, output_path: str) -> str:
        """Resolve a relative output filename to a local absolute path."""

    @abc.abstractmethod
    def upload_output(self, job_id: uuid.UUID, output_path: str) -> None:
        """Copy a completed output file to remote storage.

        No-op for the local backend (file is already in place).
        """

    @abc.abstractmethod
    def get_download_response(self, job_id: uuid.UUID, output_path: str):
        """Return a Starlette/FastAPI ``Response`` to serve the output file.

        Local backend returns ``FileResponse``; remote backends return a
        ``RedirectResponse`` to a time-limited signed URL.

        Raises ``FileNotFoundError`` if the artefact cannot be located.
        """

    @abc.abstractmethod
    def delete_job_files(self, job_id: uuid.UUID) -> None:
        """Delete all stored artefacts for a job."""


# -------------------------------------------------------------------
# Shared helpers
# -------------------------------------------------------------------

def _safe_ext(original_name: str) -> str:
    """Extract a sanitised file extension from *original_name*."""
    basename = original_name.replace("\\", "/").rsplit("/", 1)[-1]
    _, ext = os.path.splitext(basename)
    safe = "".join(ch for ch in ext.lower() if ch.isalnum() or ch == ".")
    if not safe.startswith("."):
        safe = ""
    if len(safe) > 16:
        safe = safe[:16]
    return safe


def _resolve_under_root(root: str, *parts: str) -> str:
    """Resolve *parts* under *root*, rejecting path-traversal attempts."""
    root_abs = os.path.abspath(root)
    path_abs = os.path.abspath(os.path.join(root_abs, *parts))
    if os.path.commonpath([root_abs, path_abs]) != root_abs:
        raise ValueError("Path escapes configured storage root")
    return path_abs


def _upload_object_key(file_id: uuid.UUID, original_name: str, prefix: str = "") -> str:
    """Build the remote object key for an uploaded file."""
    name = f"upload{_safe_ext(original_name)}"
    key = f"uploads/{file_id}/{name}"
    if prefix:
        key = f"{prefix.strip('/')}/{key}"
    return key


def _output_object_key(job_id: uuid.UUID, output_path: str, prefix: str = "") -> str:
    """Build the remote object key for a job output file."""
    key = f"outputs/{job_id}/{output_path}"
    if prefix:
        key = f"{prefix.strip('/')}/{key}"
    return key


# -------------------------------------------------------------------
# Local
# -------------------------------------------------------------------

class LocalStorageBackend(StorageBackend):
    """Store everything on the local filesystem (the default)."""

    def __init__(self, upload_dir: str, output_dir: str) -> None:
        self.upload_dir = upload_dir
        self.output_dir = output_dir

    def save_upload(self, content: bytes, original_name: str, file_id: uuid.UUID) -> str:
        dir_name = str(file_id)
        dir_path = _resolve_under_root(self.upload_dir, dir_name)
        os.makedirs(dir_path, exist_ok=True)

        stored_name = f"upload{_safe_ext(original_name)}"
        stored_path = os.path.join(dir_name, stored_name)
        abs_path = _resolve_under_root(self.upload_dir, stored_path)
        with open(abs_path, "wb") as f:
            f.write(content)
        return stored_path

    def get_upload_local_path(self, stored_path: str) -> str:
        return _resolve_under_root(self.upload_dir, stored_path)

    def get_output_dir(self, job_id: uuid.UUID) -> str:
        path = _resolve_under_root(self.output_dir, str(job_id))
        os.makedirs(path, exist_ok=True)
        return path

    def get_output_local_path(self, job_id: uuid.UUID, output_path: str) -> str:
        return _resolve_under_root(self.output_dir, str(job_id), output_path)

    def upload_output(self, job_id: uuid.UUID, output_path: str) -> None:
        pass  # Already on local disk.

    def get_download_response(self, job_id: uuid.UUID, output_path: str):
        from fastapi.responses import FileResponse

        abs_path = self.get_output_local_path(job_id, output_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Output file not found: {abs_path}")
        return FileResponse(abs_path, filename=os.path.basename(abs_path))

    def delete_job_files(self, job_id: uuid.UUID) -> None:
        path = _resolve_under_root(self.output_dir, str(job_id))
        if os.path.isdir(path):
            shutil.rmtree(path)


# -------------------------------------------------------------------
# Google Cloud Storage
# -------------------------------------------------------------------

class GCSStorageBackend(StorageBackend):
    """Store uploads and outputs in a GCS bucket.

    Requires the ``google-cloud-storage`` package and valid credentials
    (``GOOGLE_APPLICATION_CREDENTIALS`` env var or GCE default service
    account).  Signed-URL generation needs the ``iam.serviceAccounts.signBlob``
    permission on the service account.
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "",
        local_cache_dir: str = "/tmp/screencastgen_cache",
        output_dir: str = "/tmp/screencastgen_outputs",
    ) -> None:
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.local_cache_dir = local_cache_dir
        self.output_dir = output_dir
        self._client = None
        self._bucket = None

    @property
    def bucket(self):
        if self._bucket is None:
            from google.cloud import storage as gcs

            self._client = gcs.Client()
            self._bucket = self._client.bucket(self.bucket_name)
        return self._bucket

    # -- uploads ---------------------------------------------------------

    def save_upload(self, content: bytes, original_name: str, file_id: uuid.UUID) -> str:
        key = _upload_object_key(file_id, original_name, self.prefix)
        blob = self.bucket.blob(key)
        blob.upload_from_string(content)
        return key

    def get_upload_local_path(self, stored_path: str) -> str:
        local_path = os.path.join(self.local_cache_dir, stored_path)
        if os.path.isfile(local_path):
            return local_path
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob = self.bucket.blob(stored_path)
        blob.download_to_filename(local_path)
        return local_path

    # -- outputs ---------------------------------------------------------

    def get_output_dir(self, job_id: uuid.UUID) -> str:
        path = os.path.join(self.output_dir, str(job_id))
        os.makedirs(path, exist_ok=True)
        return path

    def get_output_local_path(self, job_id: uuid.UUID, output_path: str) -> str:
        local_path = os.path.join(self.output_dir, str(job_id), output_path)
        if os.path.isfile(local_path):
            return local_path
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        key = _output_object_key(job_id, output_path, self.prefix)
        blob = self.bucket.blob(key)
        if not blob.exists():
            raise FileNotFoundError(f"Object not found in GCS: {key}")
        blob.download_to_filename(local_path)
        return local_path

    def upload_output(self, job_id: uuid.UUID, output_path: str) -> None:
        local = self.get_output_local_path(job_id, output_path)
        key = _output_object_key(job_id, output_path, self.prefix)
        blob = self.bucket.blob(key)
        blob.upload_from_filename(local)

    def get_download_response(self, job_id: uuid.UUID, output_path: str):
        import datetime
        from fastapi.responses import RedirectResponse

        key = _output_object_key(job_id, output_path, self.prefix)
        blob = self.bucket.blob(key)
        if not blob.exists():
            raise FileNotFoundError(f"Object not found in GCS: {key}")
        url = blob.generate_signed_url(
            expiration=datetime.timedelta(hours=1),
            method="GET",
            response_disposition=f'attachment; filename="{output_path}"',
        )
        return RedirectResponse(url)

    def delete_job_files(self, job_id: uuid.UUID) -> None:
        # Remote objects
        prefix = _output_object_key(job_id, "", self.prefix)
        for blob in self.bucket.list_blobs(prefix=prefix):
            blob.delete()
        # Local working directory
        local_dir = os.path.join(self.output_dir, str(job_id))
        if os.path.isdir(local_dir):
            shutil.rmtree(local_dir)


# -------------------------------------------------------------------
# Amazon S3
# -------------------------------------------------------------------

class S3StorageBackend(StorageBackend):
    """Store uploads and outputs in an S3 bucket.

    Requires the ``boto3`` package and valid AWS credentials (env vars
    ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY``, an IAM instance
    profile, or any other mechanism supported by the boto3 credential
    chain).
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "",
        region: str = "",
        local_cache_dir: str = "/tmp/screencastgen_cache",
        output_dir: str = "/tmp/screencastgen_outputs",
    ) -> None:
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.region = region
        self.local_cache_dir = local_cache_dir
        self.output_dir = output_dir
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3

            kwargs = {}
            if self.region:
                kwargs["region_name"] = self.region
            self._client = boto3.client("s3", **kwargs)
        return self._client

    # -- uploads ---------------------------------------------------------

    def save_upload(self, content: bytes, original_name: str, file_id: uuid.UUID) -> str:
        key = _upload_object_key(file_id, original_name, self.prefix)
        self.client.put_object(Bucket=self.bucket_name, Key=key, Body=content)
        return key

    def get_upload_local_path(self, stored_path: str) -> str:
        local_path = os.path.join(self.local_cache_dir, stored_path)
        if os.path.isfile(local_path):
            return local_path
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self.client.download_file(self.bucket_name, stored_path, local_path)
        return local_path

    # -- outputs ---------------------------------------------------------

    def get_output_dir(self, job_id: uuid.UUID) -> str:
        path = os.path.join(self.output_dir, str(job_id))
        os.makedirs(path, exist_ok=True)
        return path

    def get_output_local_path(self, job_id: uuid.UUID, output_path: str) -> str:
        from botocore.exceptions import ClientError

        local_path = os.path.join(self.output_dir, str(job_id), output_path)
        if os.path.isfile(local_path):
            return local_path
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        key = _output_object_key(job_id, output_path, self.prefix)
        try:
            self.client.download_file(self.bucket_name, key, local_path)
        except ClientError as exc:
            raise FileNotFoundError(f"Object not found in S3: {key}") from exc
        return local_path

    def upload_output(self, job_id: uuid.UUID, output_path: str) -> None:
        local = self.get_output_local_path(job_id, output_path)
        key = _output_object_key(job_id, output_path, self.prefix)
        self.client.upload_file(local, self.bucket_name, key)

    def get_download_response(self, job_id: uuid.UUID, output_path: str):
        from botocore.exceptions import ClientError
        from fastapi.responses import RedirectResponse

        key = _output_object_key(job_id, output_path, self.prefix)
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
        except ClientError:
            raise FileNotFoundError(f"Object not found in S3: {key}")
        url = self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{output_path}"',
            },
            ExpiresIn=3600,
        )
        return RedirectResponse(url)

    def delete_job_files(self, job_id: uuid.UUID) -> None:
        prefix = _output_object_key(job_id, "", self.prefix)
        resp = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
        objects = resp.get("Contents", [])
        if objects:
            self.client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
            )
        # Local working directory
        local_dir = os.path.join(self.output_dir, str(job_id))
        if os.path.isdir(local_dir):
            shutil.rmtree(local_dir)
