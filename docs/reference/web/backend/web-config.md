# Web Config

> Application settings from environment variables.

**Source:** [`web/backend/config.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/config.py)

---

## Class: `Settings`

All environment variables use the `P2A_` prefix.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `P2A_DATABASE_URL` | `str` | — | PostgreSQL async connection string |
| `P2A_SYNC_DATABASE_URL` | `str` | — | PostgreSQL sync connection for Celery |
| `P2A_REDIS_URL` | `str` | — | Redis URL for broker/results |
| `P2A_UPLOAD_DIR` | `str` | `"./uploads"` | Upload file storage path (local backend) |
| `P2A_OUTPUT_DIR` | `str` | `"./outputs"` | Job output and pipeline working directory |
| `P2A_MAX_UPLOAD_SIZE_MB` | `int` | `200` | Maximum upload file size |
| `P2A_TTS_SERVER_URL` | `str` | `http://localhost:8100` | GPU inference server URL |
| `P2A_TTS_CONCURRENCY` | `int` | `8` | Number of synthesis requests the worker submits in parallel to the TTS server |
| `P2A_ALLOWED_ORIGINS` | `List[str]` | `["http://localhost:5173"]` | CORS allowed origins |
| `P2A_STORAGE_BACKEND` | `str` | `"local"` | Storage backend: `local`, `gcs`, or `s3` |
| `P2A_STORAGE_BUCKET` | `str` | `""` | Bucket name for GCS/S3 backends |
| `P2A_STORAGE_PREFIX` | `str` | `""` | Optional key prefix inside the bucket |
| `P2A_STORAGE_REGION` | `str` | `""` | AWS region for S3 |
| `P2A_STORAGE_LOCAL_CACHE_DIR` | `str` | `"/tmp/screencastgen_cache"` | Local cache for remote storage downloads |

---

## Notes

- `TTS_CONCURRENCY` works with the inference server's batcher: the web worker sends multiple chunk requests concurrently, and the GPU server coalesces compatible requests into a single batched forward pass.

---

## Usage

```python
from web.backend.config import settings

server_url = settings.TTS_SERVER_URL
tts_concurrency = settings.TTS_CONCURRENCY
```

Singleton instance `settings` is created at import time.

---

## Dependencies

```
Web Config
├── pydantic-settings
└──▶ consumed by FastAPI App
     ├──▶ Web Database
     ├──▶ Uploads Router
     ├──▶ Events Router
     ├──▶ Pipeline Tasks
     └──▶ Storage Service
```

---

## See Also

- [FastAPI App](fast-api-app.md) — Uses settings for CORS and startup
- [Inference Server](../../core/inference-server.md) — GPU-side batching counterpart
- [Docker Compose](../../configuration/docker-compose.md) — Sets these env vars for containers
