# screencastgen

Convert text documents (PDF, EPUB, plain text, and more) to audio files, highlighted-text videos, or lip-synced talking-head videos.

Supports pluggable TTS backends, alignment providers, and lip-sync providers. The default implementations are Qwen for TTS, WhisperX for alignment, and LatentSync or Wav2Lip for lip-sync.

## Installation

```bash
# Core (no TTS backend — install at least one below)
pip install -e .

# Qwen3-TTS (local, requires GPU)
pip install -e ".[qwen]"

# Highlighted-text video / PDF page highlighting (+ WhisperX, moviepy, PyMuPDF)
pip install -e ".[highlight]"

# Lip-sync video (+ WhisperX, LatentSync, PDF page highlighting)
pip install -e ".[lipsync]"

# Optional F5-TTS backend. Do not install with the default Python 3.10
# WhisperX stack unless you intentionally manage the NumPy conflict.
pip install -e ".[f5]"

# GPU inference server (for CPU/GPU VM split)
pip install -e ".[server]"

# Web backend API/worker dependencies
pip install -e ".[web]"

# Cloud storage backends (optional, for web app)
pip install -e ".[gcs]"             # Google Cloud Storage
pip install -e ".[s3]"              # Amazon S3

# Everything, including web backend deps
pip install -e ".[all]"
```

## Quick Start

```bash
# Using Qwen3-TTS locally (default)
screencastgen audio MyBook.pdf --device cuda

# Using a remote GPU server
screencastgen audio MyBook.pdf --backend remote --tts-server-url http://gpu-vm:8100

# Highlighted-text video
screencastgen highlight MyBook.pdf --backend remote --tts-server-url http://gpu-vm:8100

# Lip-sync video
screencastgen lipsync MyBook.pdf --ref-video face.mp4
screencastgen lipsync MyBook.pdf --ref-video face.mp4 --lipsync-provider latentsync

# Pre-download model weights
screencastgen download-models --backend qwen
screencastgen download-models --backend qwen --model 1.7B
# Requires LATENTSYNC_ROOT and LATENTSYNC_PYTHON, or the default install paths.
screencastgen download-models --package whisperx --package latentsync
screencastgen download-models --all
```

## TTS Backends

| Backend  | Flag              | Voice Cloning | GPU Required | License     |
|----------|-------------------|---------------|--------------|-------------|
| Qwen3    | `--backend qwen`  | Yes (3s ref)  | Yes (4GB+)   | Apache 2.0  |
| F5-TTS   | `--backend f5`    | Yes           | Yes          | Open source |
| Remote   | `--backend remote`| Server-side   | No (client)  | N/A         |

### Qwen3-TTS

Self-hosted open-source TTS. 10 languages, 24kHz WAV output, Apache 2.0 license.

```bash
pip install -e ".[qwen]"

# Default 0.6B model (4-6GB VRAM)
screencastgen audio MyBook.pdf --backend qwen --device cuda

# Higher quality 1.7B model (6-8GB VRAM)
screencastgen audio MyBook.pdf --backend qwen --model 1.7B

# With voice cloning
screencastgen audio MyBook.pdf --backend qwen --ref-audio voice.wav
```

### Remote GPU Server

Split GPU workloads onto a separate machine. The GPU VM runs all ML models (TTS, alignment, lip-sync). The CPU VM handles everything else (web app, DB, orchestration).

**GPU VM:**
```bash
pip install -e ".[server]"
screencastgen-server --backend qwen --device cuda
screencastgen-server --backend qwen --device cuda --aligner whisperx --lipsync-provider latentsync

# With voice cloning
screencastgen-server --backend qwen --device cuda --ref-audio voice.wav --model 1.7B
```

**CPU VM:**
```bash
pip install -e .
screencastgen audio MyBook.pdf --backend remote --tts-server-url http://gpu-vm:8100
screencastgen highlight MyBook.pdf --backend remote --tts-server-url http://gpu-vm:8100
```

The inference server exposes these endpoints:

| Method and path | Purpose |
|-----------------|---------|
| `POST /synthesize` | Convert text to audio with the selected TTS backend |
| `POST /transcribe` | Transcribe uploaded audio |
| `POST /align` | Align audio and text to word-level timestamps |
| `POST /lipsync` | Upload audio and a reference video, queue a lip-sync job, and return its ID |
| `GET /lipsync/{id}` | Read job status, elapsed generation time, and any error |
| `GET /lipsync/{id}/result` | Download the completed MP4 |
| `POST /lipsync/{id}/cancel` | Request cancellation and discard an in-flight result |
| `DELETE /lipsync/{id}` | Remove the job record and its generated output |
| `GET /health` | Read backend information and readiness |

Lip-sync submissions return immediately with a JSON handle such as
`{"lipsync_id": "...", "status": "queued"}`. Clients poll until the job is
`done`, `failed`, or `cancelled`, then download and delete the result. GPU
generation is serialized on the server so concurrent submissions queue instead
of competing for VRAM. The client has no overall generation deadline; individual
HTTP operations still have timeouts, and transient polling failures are retried.

Cancellation is cooperative. A queued job is skipped. If model inference has
already started, it may continue on the GPU, but its result is discarded and the
calling pipeline can proceed using pages that completed earlier. The remote
client remains compatible with older servers that return the generated MP4
directly from `POST /lipsync`.

`GET /health` also reports the loaded TTS backend plus the server defaults for `aligner` and `lipsync_provider`.

### WhisperX on GPU VMs

WhisperX can fail on GPU VMs when the Python environment has PyTorch/CUDA installed, but the dynamic loader cannot find the cuDNN runtime expected by WhisperX or one of its native dependencies. A common error looks like:

```text
Could not load library libcudnn_ops_infer.so.8
```

This means the process can see CUDA, but the required cuDNN 8 library is missing from the runtime search path. On GCP GPU VMs this often happens when the VM image has cuDNN 9 installed globally while the WhisperX stack still expects cuDNN 8.

To diagnose the issue in the active virtual environment:

```bash
ldconfig -p | grep cudnn
find "$VIRTUAL_ENV" -name 'libcudnn_ops_infer.so*' 2>/dev/null
python -c "import torch; print(torch.__version__, torch.version.cuda)"
```

If `libcudnn_ops_infer.so.8` exists inside the venv, point `LD_LIBRARY_PATH` at the containing directory before starting `screencastgen-server`:

```bash
export CUDNN_LIB_DIR="$VIRTUAL_ENV/lib/python3.10/site-packages/nvidia/cudnn/lib"
export LD_LIBRARY_PATH="$CUDNN_LIB_DIR:$LD_LIBRARY_PATH"
python -c "import ctypes; ctypes.CDLL('libcudnn_ops_infer.so.8'); print('ok')"
```

If the library is not present, install a cuDNN 8 runtime compatible with the WhisperX environment, for example:

```bash
uv pip install "nvidia-cudnn-cu12<9"
```

The codebase also includes a WhisperX-specific CPU fallback when CUDA is selected but `libcudnn_ops_infer.so.8` cannot be loaded. That keeps `/align` and `/transcribe` working, but WhisperX will run on CPU until the GPU runtime is fixed.

```
CPU VM                                        GPU VM (screencastgen-server)
+--------------------------+   HTTP :8100  +--------------------------+
| PDF extraction           |               | POST /synthesize         |
| Chunking & validation    | ------------> |   Qwen3-TTS on CUDA     |
| RemoteTTS.synthesize()   |               |                          |
| remote_align_chunk()     | ------------> | POST /align              |
| remote_generate_lipsync()| <-----------> |   Alignment provider     |
| Video compositing        |               | POST /lipsync            |
| Audio concatenation      |               | GET status/result        |
| Per-page progress/stop   |               |   Lip-sync provider      |
| Web app / Celery / DB    |               +--------------------------+
+--------------------------+
```

## Pipelines

### Audio (`screencastgen audio`)

PDF to concatenated audio file.

```bash
screencastgen audio MyBook.pdf
screencastgen audio MyBook.pdf --backend qwen --device cuda
```

### Highlight (`screencastgen highlight`)

PDF to synchronized video with word highlighting. For PDF inputs, the preferred path highlights words on the actual PDF page images using PyMuPDF word bounding boxes. For non-PDF inputs, or if PyMuPDF is unavailable, it falls back to a plain text-on-background renderer.

```bash
pip install -e ".[highlight]"
screencastgen highlight MyBook.pdf -o output.mp4
screencastgen highlight MyBook.pdf -o output.mp4 --aligner whisperx
```

### Lip-sync (`screencastgen lipsync`)

PDF to talking-head video with voice cloning and lip synchronization. For PDF inputs, the highlighted content is rendered from actual PDF page images using matched word bounding boxes before the face video is composited. Non-PDF inputs fall back to the plain text renderer.

```bash
pip install -e ".[lipsync]"

# Install LatentSync into a separate uv-managed env.
# This keeps LatentSync's pinned torch stack isolated from WhisperX.
scripts/install_latentsync.sh

# Optional if you use custom paths instead of the defaults above:
export LATENTSYNC_ROOT=/path/to/LatentSync
export LATENTSYNC_PYTHON=/path/to/.venvs/latentsync/bin/python

# Re-download checkpoints later if needed:
python -m screencastgen download-models --package latentsync

screencastgen lipsync MyBook.pdf --ref-audio voice.wav --ref-video face.mp4
screencastgen lipsync MyBook.pdf --ref-audio voice.wav --ref-video face.mp4 --lipsync-provider wav2lip
```

The default install locations used by `scripts/install_latentsync.sh` are:

- `external/LatentSync` for the upstream repo clone
- `.venvs/latentsync` for the dedicated Python 3.10 environment

The local LatentSync provider runs as a persistent sidecar subprocess through `LATENTSYNC_PYTHON`, so it does not import LatentSync into the main screencastgen environment.

## Provider Model

The runtime is now split into three independently selectable layers:

- TTS backend: selected with `--backend` and implemented under `screencastgen/providers/tts/`
- Alignment provider: selected with `--aligner` and dispatched from `screencastgen/aligner.py`
- Lip-sync provider: selected with `--lipsync-provider` and dispatched from `screencastgen/lipsync.py`

The central pipeline code no longer hardcodes constructor branches for individual TTS models, and it now passes alignment/lip-sync provider names through both local execution and the remote GPU server.

Current built-in providers:

| Layer      | Choices |
|------------|---------|
| TTS        | `qwen`, `f5`, `remote` |
| Alignment  | `whisperx` |
| Lip-sync   | `auto`, `latentsync`, `wav2lip` |

## CLI Options

```
Common options (all subcommands):
  pdf                     Path to the input PDF file
  -o, --output            Output filename
  --output-dir            Directory for chunk files (default: audio)
  --language              Language code (default: en-US)
  --status-file           Resume-state JSON file (default: processing_status.json)
  --clean                 Ignore previous state and start fresh
  -v, --verbose           Verbose output

TTS backend options (audio, highlight, lipsync):
  --backend               TTS backend: qwen, f5, remote (default: qwen)
  --device                Device for local models: auto, cpu, cuda (default: auto)
  --voice                 Voice name (backend-specific)
  --model                 Model name/path (e.g. 0.6B, 1.7B for qwen)
  --ref-audio             Reference audio for voice cloning backends
  --ref-text              Transcript of reference audio
  --tts-server-url        URL of GPU inference server (for --backend remote)
  --aligner               Alignment provider (default: whisperx)

Video options (highlight, lipsync):
  --font-size             Font size (default: 32)
  --resolution            Video resolution WxH (default: 1280x720)
  --fps                   Frame rate (default: 24)
  --lipsync-provider      Lip-sync provider: auto, latentsync, wav2lip (default: auto)

Model download options:
  --backend               Backend whose models should be downloaded; repeat as needed
  --package               Downloadable package/model family to preload; repeat as needed
  --all                   Download all registered models/packages
  --model                 Backend-specific model selector (for qwen)
```

## How It Works

1. **Extract** text from every page of the PDF (PyPDF2)
2. **Preprocess** to fix common PDF artefacts (run-together words, missing spaces)
3. **Split** into sentences, breaking any that exceed the per-sentence byte limit
4. **Chunk** sentences into groups that fit within the backend's limit (backend-specific)
5. **Validate** every chunk before synthesis
6. **Synthesize** each chunk via the selected TTS backend, tracking progress in a JSON file
7. **Concatenate** all chunk files into a single output file (pydub or ffmpeg)

For highlight/lipsync pipelines, additional steps run after synthesis:
- **Align** audio with the selected alignment provider for word-level timestamps
- **PDF inputs**: extract PyMuPDF word bounding boxes, match aligned words back to page positions, and render highlighted PDF page images
- **Other inputs / fallback**: render highlighted text on a plain background
- **Lip-sync**: generate each page with the selected face animation provider, reporting per-page elapsed time, then build the final output

The lip-sync pipeline accepts a cooperative stop request from its host. With a
remote GPU, the page currently in progress is abandoned from the pipeline's
perspective; with local inference, cancellation is observed between pages. If at
least one page has completed, the final reader/video is built from that completed
prefix and result metadata records the completed and total page counts plus page
timings. Stopping before any page completes produces a failed run because there
is no usable output to build.

The remote GPU path preserves the same abstraction: the CPU-side client sends provider names to the server, and the server executes its configured default provider or an explicit per-request override.

The status file makes the process fully resumable -- if interrupted, re-run the same command and only unprocessed chunks will be re-synthesized.

## Web Application

Full-stack web UI wrapping all three pipelines. Stack: FastAPI + PostgreSQL + Celery/Redis + React/Tailwind.

```bash
cd web
docker compose up --build    # starts postgres, redis, backend, worker, frontend
# Frontend: http://localhost:5173  |  API: http://localhost:8000
```

Configure the GPU server URL and storage backend in `.env`:
```
P2A_TTS_SERVER_URL=http://gpu-vm:8100

# Storage backend: local (default), gcs, or s3
P2A_STORAGE_BACKEND=local
# P2A_STORAGE_BUCKET=my-bucket
# P2A_STORAGE_PREFIX=screencastgen
# P2A_STORAGE_REGION=us-east-1          # S3 only
```

By default files are stored on the local filesystem. Set `P2A_STORAGE_BACKEND` to `gcs` or `s3` to store uploads and outputs in a cloud bucket. Pipelines always work against local directories; the storage layer handles downloading inputs and uploading outputs to the bucket.

### Lip-sync progress and stopping

The Job Detail page displays completed-page timings, a live timer for the page
currently generating, and total time spent. Completed timing data is persisted
with the job so it survives a browser reload; live events continue over SSE.

Selecting **Stop & build from completed pages** first opens an inline
confirmation warning to prevent accidental clicks. The user can either keep the
job running or confirm the stop. The worker stores the request in Redis, the
pipeline stops at the next supported cancellation point, and the output is built
from completed pages. A successfully shortened result is marked **Stopped early**
with its completed and total page counts.

The lip-sync setup screen also includes a reader-style preview. It uses the saved
reader theme and lets the presenter picture-in-picture be dragged within the
preview; the configured face position remains its initial placement.

See [CLAUDE.md](CLAUDE.md) for local dev setup and architecture details.

## Project Structure

```
screencastgen/
  __init__.py             Package version
  __main__.py             python -m entry point
  cli.py                  Argparse CLI, subcommand dispatch, compat wrappers
  constants.py            All defaults and byte limits
  types.py                TTSBackend protocol, WordTiming, AlignedChunk
  pipelines/
    __init__.py           Public re-exports for all pipeline entry points
    types.py              Request dataclasses (Audio/Highlight/Lipsync) + PipelineRunResult
    events.py             PipelineReporter — structured progress + console logging
    common.py             Shared steps: extract, chunk, validate, synthesize, align
    audio.py              Audio pipeline runner
    highlight.py          Highlight video/EPUB pipeline runner
    lipsync.py            Lip-sync video/EPUB pipeline runner
  providers/
    tts/
      __init__.py         TTS registry, spec loading, and factory
      base.py             BackendSpec/BackendArg dataclasses, resolve_device()
      qwen_backend.py     Qwen3-TTS backend + spec
      f5_tts.py           F5-TTS backend shim + spec
      remote_tts.py       Remote TTS backend + spec (HTTP client)
    align/
      __init__.py         Alignment provider registry
      base.py             AlignmentProviderSpec dataclass
      whisperx_provider.py  WhisperX alignment implementation
    lipsync/
      __init__.py         Lip-sync provider registry
      base.py             LipsyncProviderSpec dataclass
      latentsync_provider.py  LatentSync implementation
      wav2lip_provider.py     Wav2Lip implementation
  extractor.py            PDF/TXT/EPUB text extraction + PyMuPDF bbox/page-image helpers
  text_processing.py      Preprocess, sentence split, chunking (byte-based)
  tracker.py              ProcessingTracker — resumable state (JSON)
  concatenator.py         Audio/video merge (pydub / ffmpeg fallback)
  aligner.py              Thin facade over providers/align
  lipsync.py              Thin facade over providers/lipsync
  highlight_renderer.py   Plain-text fallback video frame renderer (Pillow)
  page_renderer.py        PDF page-image renderer using matched word bounding boxes
  word_matcher.py         Sequential matcher from aligned words to PDF word positions
  video_composer.py       Video composition (highlight + lipsync)
  epub_builder.py         EPUB3 output with embedded audio/video + SMIL overlays
  inference_server.py     FastAPI GPU inference server
  remote_gpu.py           HTTP client helpers for remote TTS, alignment, lip-sync
  models.py               Model download and cache management
  tts_clone.py            Voice cloning helpers
tests/                    Test stubs
web/                      Full-stack web application
pyproject.toml            Package metadata and entry points
```

## Dependencies by Feature

| Feature         | Key packages                                    |
|-----------------|-------------------------------------------------|
| Core            | PyPDF2                                          |
| Qwen3 TTS      | qwen-tts, torch, soundfile                      |
| Concatenation   | pydub (preferred) or ffmpeg CLI                 |
| Highlight video | alignment provider deps (currently whisperx), moviepy, Pillow, torch, pymupdf |
| Lip-sync video  | alignment provider deps, moviepy, Pillow, torch, pymupdf, lip-sync provider deps (currently [LatentSync](https://github.com/bytedance/LatentSync) in a separate env, or Wav2Lip), ffmpeg/ffprobe |
| GPU server      | fastapi, uvicorn, python-multipart              |
| Web app         | fastapi, sqlalchemy, celery, redis, asyncpg     |
| Web frontend    | react, react-router-dom, axios, tailwindcss     |
| GCS storage     | google-cloud-storage (optional)                  |
| S3 storage      | boto3 (optional)                                 |
