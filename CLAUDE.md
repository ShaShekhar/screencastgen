# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

screencastgen converts text documents (PDF, EPUB, plain text, and more) into audio files, highlighted-text videos, or lip-synced talking-head videos. It has three pipelines accessible via subcommands:

- **`audio`** — document → text → TTS → concatenated audio file (default, also works without subcommand for backward compat)
- **`highlight`** — Same as audio, plus WhisperX alignment → word-highlighted video (moviepy). For PDF inputs, highlights words on the actual page images; for other inputs, renders text on a plain background.
- **`lipsync`** — document → text → voice cloning TTS → WhisperX alignment → LatentSync/Wav2Lip face animation → composite video with highlighted text. Face overlay composited on PDF page images (or plain text frames).

## Commands

```bash
# Install (editable)
pip install -e .                    # core only (PyPDF2)
pip install -e ".[qwen]"           # + Qwen3-TTS, torch, soundfile
pip install -e ".[highlight]"       # + WhisperX, moviepy, Pillow, torch
pip install -e ".[lipsync]"         # + F5-TTS
pip install -e ".[server]"          # GPU inference server (all ML deps + FastAPI)
pip install -e ".[gcs]"            # + Google Cloud Storage backend
pip install -e ".[s3]"             # + Amazon S3 backend
pip install -e ".[all]"             # everything

# Run (local GPU)
screencastgen audio MyBook.pdf --backend qwen --device cuda
screencastgen highlight MyBook.pdf --backend qwen
screencastgen lipsync MyBook.pdf --backend f5 --ref-audio x.wav --ref-video face.mp4

# Run (remote GPU server)
screencastgen audio MyBook.pdf --backend remote --tts-server-url http://gpu-vm:8100
screencastgen highlight MyBook.pdf --backend remote --tts-server-url http://gpu-vm:8100

# GPU inference server
screencastgen-server --backend qwen --device cuda

# Pre-download models
screencastgen download-models --qwen
screencastgen download-models --all

# Module invocation
python -m screencastgen audio MyBook.pdf
```

No test suite exists yet. No linter configuration is present.

## Architecture

The shared pipeline (steps 1–5 in `cli.py`) is: extract → preprocess → split → chunk → validate. These steps are in `_extract_and_chunk()` and `_validate_and_collect()`. Each subcommand runner then handles synthesis and output differently.

**Key design patterns:**

- **Deferred imports**: Heavy deps (torch, whisperx, moviepy, f5-tts, qwen-tts, latentsync, pymupdf) are imported inside functions, not at module top. This lets `screencastgen --help` work without all deps installed. Maintain this pattern.
- **Page-image rendering**: For PDF inputs, `PageRenderer` rasterises actual PDF pages and highlights words at their real bounding-box positions. `WordMatcher` maps WhisperX-aligned words back to PDF bounding boxes via sequential normalised matching. Falls back to `HighlightRenderer` (plain text on dark background) for non-PDF inputs or when PyMuPDF is not installed.
- **Resumable processing**: `ProcessingTracker` persists state to a JSON file (`processing_status.json`). Chunks are keyed by number + MD5 hash, so re-runs skip already-completed work. The tracker also stores alignment and video rendering state.
- **TTSBackend protocol**: `types.py` defines a `TTSBackend` Protocol with `synthesize(text, output_path)`, `max_chunk_bytes`, and `output_format` properties. TTS providers (`QwenTTS`, `F5TTSBackend`, `RemoteTTS`) live under `screencastgen/providers/tts/`.
- **TTS registry**: `providers/tts/__init__.py` has a lazy-import registry. `create_backend(name, **kwargs)` instantiates any backend by name (`qwen`, `f5`, `remote`).
- **Byte-based limits**: All chunk/sentence sizing uses UTF-8 byte length (not character count). Each backend declares its own `max_chunk_bytes` property. Constants in `constants.py` provide defaults.
- **CPU/GPU VM split**: The `remote` backend delegates TTS, WhisperX alignment, and lip-sync generation to a GPU inference server (`inference_server.py`) over HTTP. Lip-sync uses an asynchronous submit/status/result/delete protocol; the server serializes GPU generation, while `remote_gpu.py` polls without an overall generation timeout and supports cooperative cancellation. The CPU VM only needs PyPDF2 + stdlib.
- **Structured pipeline events**: `PipelineReporter` emits phase/current/total/message fields plus an optional `data` payload. Lip-sync uses the payload for page start, elapsed-time progress, page completion, and accumulated timings. Hosts can also provide `should_cancel`; pipeline code polls it at safe cancellation points.
- **Partial lip-sync output**: A stopped lip-sync run builds from the completed prefix of pages when at least one page is available. Result metadata records whether it stopped early, completed/total counts, and per-page timings. A run stopped before its first completed page fails instead of creating an empty output.

## Dependencies by Feature

| Feature         | Key packages                                    |
| --------------- | ----------------------------------------------- |
| Core            | PyPDF2                                          |
| Qwen3 TTS      | qwen-tts, torch, soundfile                      |
| Concatenation   | pydub (preferred) or ffmpeg CLI                 |
| Highlight video | whisperx, moviepy, Pillow, torch, pymupdf       |
| Lip-sync video  | f5-tts, pymupdf, latentsync (or wav2lip), ffmpeg/ffprobe |
| GPU server      | fastapi, uvicorn, python-multipart              |
| Web app         | fastapi, sqlalchemy, celery, redis, asyncpg      |
| Web frontend    | react, react-router-dom, axios, tailwindcss       |
| GCS storage     | google-cloud-storage (optional)                  |
| S3 storage      | boto3 (optional)                                 |

## Web Application (`web/`)

Full-stack web UI wrapping all three pipelines. Stack: FastAPI + PostgreSQL + Celery/Redis + React/Tailwind.

### Running (Docker)

```bash
cd web
docker compose up --build    # starts postgres, redis, backend, worker, frontend
# Frontend: http://localhost:5173  |  API: http://localhost:8000
```

### Running (local dev)

```bash
# Prerequisites: PostgreSQL and Redis running locally
cd web
cp .env.example .env         # edit DB/Redis URLs and TTS_SERVER_URL
make install                 # install python + npm deps
make migrate                 # run alembic migrations
# Then in 3 terminals:
make backend                 # uvicorn on :8000
make worker                  # celery worker
make frontend                # vite dev server on :5173
```

### Web Architecture

- **Backend** (`web/backend/`): FastAPI app with async SQLAlchemy (PostgreSQL). Routers: `uploads.py` (file upload), `jobs.py` (CRUD, download, and lip-sync stop requests), `events.py` (SSE progress stream).
- **Celery tasks** (`web/backend/tasks/`): `pipelines.py` constructs pipeline request objects and calls the shared runners. `JobProgressReporter` persists progress to PostgreSQL, publishes structured events through Redis pubsub, and exposes the Redis cancellation flag through `PipelineReporter.should_cancel`. The flag is cleared when a task finishes. Default backend is `remote` — the worker calls the GPU inference server. After pipeline success, `upload_output()` pushes the result to remote storage (no-op for local).
- **Frontend** (`web/frontend/`): React + Tailwind SPA. Pages: Dashboard (job list), NewJob (upload, config, and draggable reader-style lip-sync preview), JobDetail (live SSE progress, per-page lip-sync timing, confirmed stop action, partial-run status, and download). Vite proxies `/api` to the backend in dev.
- **Database**: Two tables — `uploaded_files` and `jobs`. Job config is stored as JSONB. Each job gets an isolated output dir (`outputs/{job_id}/`) with its own `ProcessingTracker` JSON file for resumability.
- **Real-time progress**: SSE via `sse-starlette`. Backend publishes to Redis pubsub channel `job:{id}:progress`; the SSE endpoint subscribes and streams events to the browser. Completed lip-sync page timings are also saved in `jobs.config_json.lipsync_progress` so the UI can recover after a reload.
- **Lip-sync stopping**: `POST /jobs/{id}/stop` validates that the job is an active lip-sync run and writes `job:{id}:cancel` to Redis with a 24-hour expiry. The Job Detail UI requires inline confirmation before calling it. Remote generation can abandon the active page from the worker's perspective; local generation observes the request between pages.
- **Storage backends**: `StorageBackend` ABC in `web/backend/services/storage_backend.py` with local (default), GCS, and S3 implementations. Configured via `P2A_STORAGE_BACKEND` env var. Pipelines always work locally; remote backends handle upload/download to/from buckets. Cloud deps (`google-cloud-storage`, `boto3`) are deferred imports.
