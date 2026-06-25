# Installation Guide

This guide covers the managed installer, supported platforms, manual dependency
selection, model weights, local and remote GPU setup, and the web application.

## Platform Support

All platforms need Git, [uv](https://docs.astral.sh/uv/getting-started/installation/),
Node.js/npm, and FFmpeg (`ffmpeg` and `ffprobe` on `PATH`). The setup program
checks these tools and prints platform-specific guidance; it never installs
system packages or requests administrator privileges.

Local Qwen, WhisperX, and LatentSync execution additionally needs Linux or WSL2
with an NVIDIA GPU and a working driver.

| Platform | Development and web UI | Remote GPU client | Full local GPU stack |
|----------|------------------------|-------------------|----------------------|
| Linux + NVIDIA | Yes | Yes | Yes |
| Windows + WSL2/NVIDIA | Yes | Yes | Yes, inside WSL2 |
| Native Windows | Yes | Yes | No; use WSL2 |
| macOS | Yes | Yes | No CUDA support |

## System Prerequisites

Install system tools before running the managed setup. The setup program checks
for these commands and reports anything missing, but it does not install system
packages or request administrator privileges.

On Debian or Ubuntu VMs:

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates git nodejs npm ffmpeg build-essential
curl -LsSf https://astral.sh/uv/install.sh | sh
exec "$SHELL"

# From the cloned screencastgen directory:
python3 scripts/setup.py --check
python3 scripts/setup.py
```

`build-essential` provides `gcc`, `g++`, and `make`. The `ffmpeg` package
provides both `ffmpeg` and `ffprobe`. `nodejs` and `npm` are required for the
React frontend build, and `uv` creates the Python environment used by setup.

For a local GPU install, the VM also needs an NVIDIA driver that makes
`nvidia-smi` work before setup runs. Install the driver using your cloud image,
distribution, or NVIDIA instructions; the repository installer does not manage
GPU drivers.

Other common platforms:

```bash
# Fedora/RHEL
sudo dnf install git nodejs npm ffmpeg gcc-c++ make
curl -LsSf https://astral.sh/uv/install.sh | sh
exec "$SHELL"

# macOS with Homebrew
brew install git uv node ffmpeg

# Windows PowerShell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Gyan.FFmpeg -e
```

## Managed Setup

Linux or macOS:

```bash
git clone https://github.com/ShaShekhar/screencastgen.git
cd screencastgen
python3 scripts/setup.py
source .venv/bin/activate
```

Windows PowerShell:

```powershell
git clone https://github.com/ShaShekhar/screencastgen.git
cd screencastgen
py scripts/setup.py
.venv\Scripts\Activate.ps1
```

The automatic profile installs the full local stack and downloads model weights
when it detects Linux/WSL2 with NVIDIA. Native Windows, macOS, and non-GPU Linux
receive the development and remote-client stack without CUDA models.

Inspect prerequisites without changing anything, or select a profile explicitly:

```bash
python3 scripts/setup.py --check
python3 scripts/setup.py --profile local-gpu
python3 scripts/setup.py --profile local-gpu --model 1.7B
python3 scripts/setup.py --profile remote-client --server-url http://gpu-vm:8100
python3 scripts/setup.py --profile dev
```

Setup creates a Python 3.10 environment, installs the selected Python and
frontend dependencies, verifies a frontend build, and runs the environment
doctor. The `local-gpu` profile also creates the isolated LatentSync environment
and downloads Qwen 0.6B, WhisperX, and LatentSync weights. Downloads are cached,
so rerunning setup is safe.

Verify an installation at any time:

```bash
screencastgen doctor --profile auto
screencastgen doctor --profile local-gpu --model 1.7B
screencastgen doctor --profile remote-client --server-url http://gpu-vm:8100
```

## Manual Installation

Use manual extras when you do not want the managed setup profiles:

```bash
pip install -e .                    # Core document/audio orchestration
pip install -e ".[client]"         # Remote client and video composition
pip install -e ".[qwen]"           # Local Qwen3-TTS
pip install -e ".[highlight]"       # Local WhisperX highlighting
pip install -e ".[lipsync]"         # Local lip-sync pipeline dependencies
pip install -e ".[server]"          # GPU inference server
pip install -e ".[web]"             # Web backend and worker
pip install -e ".[dev]"             # Tests and development helpers
pip install -e ".[all]"             # Supported local stack
```

Optional cloud integrations:

```bash
pip install -e ".[gcs]"             # Google Cloud Storage
pip install -e ".[s3]"              # Amazon S3
```

## Model Weights

The default Qwen 0.6B model typically needs 4–6 GB of VRAM. The larger 1.7B
model typically needs 6–8 GB. The bundled LatentSync 1.6 integration has a
higher requirement: upstream lists 18 GB as the minimum VRAM for inference.

```bash
screencastgen download-models --backend qwen
screencastgen download-models --backend qwen --model 1.7B
screencastgen download-models --package whisperx
screencastgen download-models --package latentsync
```

LatentSync must be installed before downloading its weights. Requested downloads
return a nonzero exit code if any model cannot be prepared.

## LatentSync Sidecar

LatentSync uses a separate Python 3.10 environment so its pinned Torch stack does
not conflict with WhisperX. This local path is supported on Linux and WSL2.

```bash
scripts/install_latentsync.sh
```

Default locations:

- `external/LatentSync` for the upstream repository
- `.venvs/latentsync` for its environment

Custom locations can be configured before running the pipeline:

```bash
export LATENTSYNC_ROOT=/path/to/LatentSync
export LATENTSYNC_PYTHON=/path/to/.venvs/latentsync/bin/python
```

The provider runs LatentSync through a persistent sidecar subprocess and does
not import it into the main screencastgen environment.

## Remote GPU Setup

The GPU host runs TTS, alignment, and lip-sync. The client handles document
extraction, orchestration, and final media composition.

GPU host:

```bash
python3 scripts/setup.py --profile local-gpu
source .venv/bin/activate
screencastgen-server --backend qwen --device cuda \
  --aligner whisperx --lipsync-provider latentsync
```

Client:

```bash
python3 scripts/setup.py --profile remote-client --server-url http://gpu-vm:8100
source .venv/bin/activate
screencastgen audio MyBook.pdf --backend remote --tts-server-url http://gpu-vm:8100
screencastgen highlight MyBook.pdf --backend remote --tts-server-url http://gpu-vm:8100
```

On Windows PowerShell, use `py scripts/setup.py` and
`.venv\Scripts\Activate.ps1` instead.

## Web Application Setup

The simplest full-stack launch uses Docker:

```bash
cd web
docker compose up --build
```

The frontend is available at `http://localhost:5173` and the API at
`http://localhost:8000`.

For local development on Linux, macOS, or WSL2, start PostgreSQL and Redis,
then run:

```bash
cd web
cp .env.example .env
make install
make migrate
# In separate terminals:
make backend
make worker
make frontend
```

Native Windows users can use Docker Desktop or run the equivalent commands from
PowerShell after activating `.venv`.

Configure the remote GPU and storage in `web/.env`:

```dotenv
P2A_TTS_SERVER_URL=http://gpu-vm:8100
P2A_STORAGE_BACKEND=local
# P2A_STORAGE_BUCKET=my-bucket
# P2A_STORAGE_PREFIX=screencastgen
# P2A_STORAGE_REGION=us-east-1
```

Storage can be `local`, `gcs`, or `s3`. Pipelines work in local directories;
the storage layer downloads inputs and uploads completed outputs as needed.

## WhisperX CUDA Troubleshooting

WhisperX may fall back to CPU when CUDA is visible but the cuDNN 8 runtime it
expects is unavailable. A common error is:

```text
Could not load library libcudnn_ops_infer.so.8
```

Diagnose the active environment on a Linux GPU host:

```bash
ldconfig -p | grep cudnn
find "$VIRTUAL_ENV" -name 'libcudnn_ops_infer.so*' 2>/dev/null
python -c "import torch; print(torch.__version__, torch.version.cuda)"
```

If the library exists inside the environment, expose its directory before
starting the server:

```bash
export CUDNN_LIB_DIR="$VIRTUAL_ENV/lib/python3.10/site-packages/nvidia/cudnn/lib"
export LD_LIBRARY_PATH="$CUDNN_LIB_DIR:$LD_LIBRARY_PATH"
python -c "import ctypes; ctypes.CDLL('libcudnn_ops_infer.so.8'); print('ok')"
```

If it is absent, install a compatible runtime:

```bash
uv pip install "nvidia-cudnn-cu12<9"
```

The built-in fallback keeps transcription and alignment working on CPU until
the GPU runtime is corrected.

## Dependencies by Feature

| Feature | Key packages |
|---------|--------------|
| Core | PyPDF2 |
| Remote client | pydub, moviepy, Pillow, pymupdf |
| Qwen3 TTS | qwen-tts, torch, soundfile |
| Highlight video | whisperx, moviepy, Pillow, torch, pymupdf |
| Lip-sync video | highlight dependencies, LatentSync, ffmpeg |
| GPU server | fastapi, uvicorn, python-multipart |
| Web app | fastapi, sqlalchemy, celery, redis, asyncpg |
| Web frontend | React, React Router, Axios, Tailwind CSS |
| Cloud storage | google-cloud-storage or boto3 |
| Development | pytest, reportlab |

See [Model Dependencies and References](https://github.com/ShaShekhar/screencastgen#model-dependencies-and-references)
for upstream repositories, model cards, licenses, and citation information.
