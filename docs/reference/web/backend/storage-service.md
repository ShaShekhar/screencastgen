# Storage Service

> Pluggable file storage with local, GCS, and S3 backends.

**Source:** [`web/backend/services/storage.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/services/storage.py), [`web/backend/services/storage_backend.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/services/storage_backend.py)

---

## Overview

The storage layer is split into two files:

- **`storage_backend.py`** — Defines the `StorageBackend` ABC and three concrete implementations (local, GCS, S3).
- **`storage.py`** — Thin delegation module. Creates a singleton backend from config and exposes convenience functions that preserve the original module-level API.

Pipelines always work against **local directories** for intermediate files. Remote backends download uploads to a local cache before pipeline execution and upload final outputs to the bucket after completion.

---

## StorageBackend ABC

All backends implement these methods:

| Method | Description |
|--------|-------------|
| `save_upload(content, original_name, file_id) -> str` | Persist uploaded bytes, return a `stored_path` key |
| `get_upload_local_path(stored_path) -> str` | Return a local filesystem path (downloads from bucket if remote) |
| `get_output_dir(job_id) -> str` | Create and return a local working directory for pipeline output |
| `get_output_local_path(job_id, output_path) -> str` | Resolve a relative output filename to a local absolute path |
| `upload_output(job_id, output_path)` | Copy completed output to remote storage (no-op for local) |
| `get_download_response(job_id, output_path)` | Return a Starlette `Response` for serving the file |
| `delete_job_files(job_id)` | Delete all stored artefacts for a job |

---

## Backends

### LocalStorageBackend

Default. Files live on disk under `UPLOAD_DIR` and `OUTPUT_DIR`.

- `save_upload` writes to `UPLOAD_DIR/{file_id}/upload.{ext}`
- `upload_output` is a no-op (file is already in place)
- `get_download_response` returns `FileResponse`
- `delete_job_files` removes `OUTPUT_DIR/{job_id}/` recursively

### GCSStorageBackend

Stores uploads and outputs in a Google Cloud Storage bucket. Requires `google-cloud-storage`.

- Uploads go to `gs://{bucket}/{prefix}/uploads/{file_id}/upload.{ext}`
- `get_upload_local_path` downloads to `STORAGE_LOCAL_CACHE_DIR` on first access
- `upload_output` pushes the file to `gs://{bucket}/{prefix}/outputs/{job_id}/{filename}`
- `get_download_response` returns `RedirectResponse` to a 1-hour signed URL
- Requires `iam.serviceAccounts.signBlob` permission for signed URL generation

### S3StorageBackend

Stores uploads and outputs in an Amazon S3 bucket. Requires `boto3`.

- Same key layout as GCS (`uploads/...`, `outputs/...`)
- `get_download_response` returns `RedirectResponse` to a 1-hour presigned URL
- Uses standard boto3 credential chain (env vars, IAM role, etc.)

---

## Module-Level Functions (`storage.py`)

These delegate to the configured singleton backend. Existing callers do not need to change their imports.

| Function | Delegates To |
|----------|-------------|
| `save_upload(content, original_name, file_id) -> str` | `backend.save_upload()` |
| `get_upload_abs_path(stored_path) -> str` | `backend.get_upload_local_path()` |
| `get_output_dir(job_id) -> str` | `backend.get_output_dir()` |
| `get_output_abs_path(job_id, output_path) -> str` | `backend.get_output_local_path()` |
| `upload_output(job_id, output_path)` | `backend.upload_output()` |
| `get_download_response(job_id, output_path)` | `backend.get_download_response()` |
| `delete_job_files(job_id)` | `backend.delete_job_files()` |
| `get_storage_backend() -> StorageBackend` | Returns the singleton instance |

---

## Configuration

Backend selection is controlled by [Web Config](web-config.md) environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `P2A_STORAGE_BACKEND` | `local` | `local`, `gcs`, or `s3` |
| `P2A_STORAGE_BUCKET` | `""` | Bucket name (required for gcs/s3) |
| `P2A_STORAGE_PREFIX` | `""` | Optional key prefix inside bucket |
| `P2A_STORAGE_REGION` | `""` | AWS region (S3 only) |
| `P2A_STORAGE_LOCAL_CACHE_DIR` | `/tmp/screencastgen_cache` | Local cache for remote downloads |

---

## Security

- **Local backend** uses `_resolve_under_root()` to prevent path traversal.
- **Remote backends** construct object keys programmatically from UUIDs, avoiding user-controlled path components.
- `get_download_response` raises `FileNotFoundError` if the artefact cannot be located.

---

## Dependencies

```
Storage Service
├── storage_backend.py
│   ├── LocalStorageBackend (stdlib only)
│   ├── GCSStorageBackend   (google-cloud-storage, deferred import)
│   └── S3StorageBackend    (boto3, deferred import)
├── storage.py (delegation + singleton)
├── Web Config          (all P2A_STORAGE_* + UPLOAD_DIR, OUTPUT_DIR)
└──▶ consumed by Uploads Router
     ├──▶ Jobs Router
     └──▶ Pipeline Tasks
```

---

## See Also

- [Uploads Router](uploads-router.md) — Calls `save_upload()`
- [Jobs Router](jobs-router.md) — Calls `get_download_response()`, `delete_job_files()`
- [Pipeline Tasks](pipeline-tasks.md) — Calls `get_output_dir()`, `get_upload_abs_path()`, `upload_output()`
- [Web Config](web-config.md) — Storage backend settings
