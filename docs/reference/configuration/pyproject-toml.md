# pyproject.toml

> Package metadata, dependencies, optional extras, and entry points.

**Source:** [`pyproject.toml`](https://github.com/ShaShekhar/screencastgen/blob/main/pyproject.toml)

---

## Package

| Field | Value |
|-------|-------|
| Name | `screencastgen` |
| Version | `2.0.0` |
| Requires Python | `>= 3.9` |

---

## Entry Points

| Command | Target |
|---------|--------|
| `screencastgen` | `screencastgen.cli:main` → [CLI](../core/cli.md) |
| `screencastgen-server` | `screencastgen.inference_server:main` → [Inference Server](../core/inference-server.md) |

---

## Optional Dependencies

| Extra | Packages | What It Enables |
|-------|----------|-----------------|
| `qwen` | qwen-tts, torch, soundfile | [Qwen Backend](../providers/qwen-backend.md) |
| `pydub` | pydub | [Concatenator](../core/concatenator.md) (preferred) |
| `client` | pydub, moviepy, Pillow, pymupdf | Document/media processing on a remote-GPU client without local ML models |
| `dev` | pytest, reportlab | Unit tests and PDF test fixtures |
| `docs` | mkdocs, mkdocs-material | Local documentation preview and strict site builds |
| `epub` | pydub, whisperx, torch, torchaudio, torchcodec | [EPUB Builder](../core/epub-builder.md) features |
| `highlight` | pydub, whisperx, moviepy, Pillow, torch, torchaudio, torchcodec, pymupdf | [Highlight Pipeline](../pipelines/highlight-pipeline.md) including PDF page-image rendering via [Page Renderer](../core/page-renderer.md) |
| `lipsync` | pydub, whisperx, moviepy, Pillow, torch, torchaudio, torchcodec, pymupdf | [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) + reader bundle / MP4 assembly. Lip-sync providers such as LatentSync are installed separately. |
| `server` | FastAPI, uvicorn, python-multipart, qwen, highlight, lipsync | [Inference Server](../core/inference-server.md) |
| `web` | FastAPI, uvicorn, SQLAlchemy, asyncpg, psycopg2, Alembic, Celery, Redis, sse-starlette, python-multipart, pydantic-settings | Web backend/API/worker |
| `gcs` | google-cloud-storage | [Storage Service](../web/backend/storage-service.md) GCS backend |
| `s3` | boto3 | [Storage Service](../web/backend/storage-service.md) S3 backend |
| `all` | client + highlight + lipsync + qwen + server + web | Full local Python stack |

---

## Core Dependency

| Package | Version | Used By |
|---------|---------|---------|
| PyPDF2 | >= 3.0 | [Extractor](../core/extractor.md) |

## External Tools Not Declared As Extras

| Tool | Used By | Note |
|------|---------|------|
| `manimgl` executable | [Visualization Pipeline](../pipelines/visualization-pipeline.md) / [ManimGL Renderer](../providers/manim-gl-renderer.md) | Must be installed separately and available on `PATH` |
| LatentSync sidecar env | [LatentSync Provider](../providers/latent-sync-provider.md) | Installed by the local-GPU [Setup Script](setup-script.md), directly via `scripts/install_latentsync.sh`, or configured with `LATENTSYNC_ROOT` / `LATENTSYNC_PYTHON` |

---

## See Also

- [Architecture](../../concepts/architecture.md) — How packages relate to features
- [Provider Overview](../../concepts/providers.md) — Which providers need which extras
- [Setup Script](setup-script.md) — How profiles select extras
