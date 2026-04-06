# screencastgen

Convert text documents (PDF, EPUB, plain text, and more) to audio files, highlighted-text videos, or lip-synced talking-head videos.

Supports multiple TTS backends (local or remote GPU inference server) with optional voice cloning.

## Installation

```bash
# Core (no TTS backend — install at least one below)
pip install -e .

# Qwen3-TTS (local, requires GPU)
pip install -e ".[qwen]"

# Highlighted-text video (+ WhisperX, moviepy)
pip install -e ".[highlight]"

# Lip-sync video (+ F5-TTS, LatentSync)
pip install -e ".[lipsync]"

# GPU inference server (for CPU/GPU VM split)
pip install -e ".[server]"

# Everything
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

# Lip-sync video with voice cloning
screencastgen lipsync MyBook.pdf --backend f5 --ref-audio voice.wav --ref-video face.mp4

# Pre-download model weights
screencastgen download-models --qwen
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

Split GPU workloads onto a separate machine. The GPU VM runs all ML models (TTS, WhisperX alignment, lip-sync). The CPU VM handles everything else (web app, DB, orchestration).

**GPU VM:**
```bash
pip install -e ".[server]"
screencastgen-server --backend qwen --device cuda

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
- `POST /synthesize` — Text to audio (TTS)
- `POST /align` — Audio + text to word-level timestamps (WhisperX)
- `POST /lipsync` — Audio + reference video to lip-synced video (LatentSync)
- `GET /health` — Backend info and readiness

```
CPU VM                                        GPU VM (screencastgen-server)
+--------------------------+   HTTP :8100  +--------------------------+
| PDF extraction           |               | POST /synthesize         |
| Chunking & validation    | ------------> |   Qwen3-TTS on CUDA     |
| RemoteTTS.synthesize()   |               |                          |
| remote_align_chunk()     | ------------> | POST /align              |
| remote_generate_lipsync()| <------------ |   WhisperX on CUDA       |
| Video compositing        |               | POST /lipsync            |
| Audio concatenation      |               |   LatentSync on CUDA     |
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

PDF to highlighted-text video with synchronized audio.

```bash
pip install -e ".[highlight]"
screencastgen highlight MyBook.pdf -o output.mp4
```

### Lip-sync (`screencastgen lipsync`)

PDF to talking-head video with voice cloning and lip synchronization.

```bash
pip install -e ".[lipsync]"
screencastgen lipsync MyBook.pdf --ref-audio voice.wav --ref-video face.mp4
```

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

Video options (highlight, lipsync):
  --font-size             Font size (default: 32)
  --resolution            Video resolution WxH (default: 1280x720)
  --fps                   Frame rate (default: 24)
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
- **Align** audio with WhisperX for word-level timestamps
- **Render** highlighted text video or lip-synced talking-head video

The status file makes the process fully resumable -- if interrupted, re-run the same command and only unprocessed chunks will be re-synthesized.

## Web Application

Full-stack web UI wrapping all three pipelines. Stack: FastAPI + PostgreSQL + Celery/Redis + React/Tailwind.

```bash
cd web
docker compose up --build    # starts postgres, redis, backend, worker, frontend
# Frontend: http://localhost:5173  |  API: http://localhost:8000
```

Configure the GPU server URL in `.env`:
```
P2A_TTS_SERVER_URL=http://gpu-vm:8100
```

See [CLAUDE.md](CLAUDE.md) for local dev setup and architecture details.

## Project Structure

```
screencastgen/
  __init__.py           Package version
  __main__.py           python -m entry point
  cli.py                Argparse CLI and pipeline runners
  extractor.py          PDF text extraction
  text_processing.py    Preprocess, split, chunk, validate
  tts_clone.py          F5-TTS voice cloning backend
  tracker.py            Resumable processing state (JSON)
  concatenator.py       Audio merge (pydub / ffmpeg fallback)
  constants.py          All defaults and limits
  types.py              TTSBackend protocol, WordTiming, AlignedChunk
  aligner.py            WhisperX word-level alignment
  lipsync.py            LatentSync / Wav2Lip lip-sync generation
  inference_server.py   FastAPI GPU inference server
  remote_gpu.py         HTTP client for remote alignment and lip-sync
  models.py             Model download and cache management
  backends/
    __init__.py         Backend registry and factory
    qwen_tts.py         Qwen3-TTS backend
    f5_tts.py           F5-TTS backend
    remote_tts.py       Remote TTS backend (HTTP client)
  highlight_renderer.py Text highlight frame renderer
  video_composer.py     Video composition (highlight + lipsync)
web/                    Full-stack web application
pyproject.toml          Package metadata and entry points
```

## Dependencies by Feature

| Feature         | Key packages                                    |
|-----------------|-------------------------------------------------|
| Core            | PyPDF2                                          |
| Qwen3 TTS      | qwen-tts, torch, soundfile                      |
| Concatenation   | pydub (preferred) or ffmpeg CLI                 |
| Highlight video | whisperx, moviepy, Pillow, torch                |
| Lip-sync video  | f5-tts, latentsync (or wav2lip), ffmpeg/ffprobe |
| GPU server      | fastapi, uvicorn, python-multipart              |
| Web app         | fastapi, sqlalchemy, celery, redis, asyncpg     |
| Web frontend    | react, react-router-dom, axios, tailwindcss     |
