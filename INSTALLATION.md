# Installation Guide

This guide is intentionally focused on Ubuntu GPU VMs. Docker is the recommended
installation path for production-style use because it keeps CUDA, Python,
LatentSync, the API, the worker, and the frontend isolated from the host.

Source installation is still supported for development or for operators who want
to manage the Python environment directly.

## 1. Verify VM Prerequisites

Start with an Ubuntu VM that has an NVIDIA GPU and Docker installed.

Check the host GPU driver:

```bash
nvidia-smi
```

Check Docker and Compose:

```bash
docker --version
docker compose version
```

Check Docker GPU passthrough:

```bash
sudo docker run --rm --gpus all nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04 nvidia-smi
```

If this works, continue. On many GCP GPU VMs the NVIDIA container runtime may
already be configured.

If this fails, debug the VM's NVIDIA Docker runtime before installing
screencastgen. Follow your cloud image documentation and the official NVIDIA
Container Toolkit guide:

https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html

## 2. Docker Installation

Clone the repository:

```bash
git clone https://github.com/ShaShekhar/screencastgen.git
cd screencastgen
```

Build the GPU image:

```bash
sudo docker build -f Dockerfile.gpu -t screencastgen:gpu .
```

Confirm the image exists and can see the GPU:

```bash
sudo docker images screencastgen:gpu
sudo docker run --rm --gpus all screencastgen:gpu nvidia-smi
```

Download model weights into persistent Docker volumes:

```bash
sudo docker run --rm --gpus all \
  -v screencastgen-hf:/root/.cache/huggingface \
  -v screencastgen-torch:/root/.cache/torch \
  -v screencastgen-latentsync:/opt/latentsync/checkpoints \
  screencastgen:gpu \
  screencastgen download-models --backend qwen --package whisperx --package latentsync
```

### GPU Server Only

Use this mode when another machine or application will call the GPU inference
API.

```bash
sudo docker compose -f docker-compose.gpu.yml up
```

Check the server from another terminal:

```bash
curl http://localhost:8100/health
```

### Full Web UI Stack

Use this mode to run everything on the VM: PostgreSQL, Redis, GPU inference
server, FastAPI backend, Celery worker, and React frontend.

Choose the public web port before starting the stack. This example serves the UI
on port `8080`:

```bash
export WEB_PORT=8080
export API_PORT=8000
export GPU_PORT=8100
sudo docker compose -f docker-compose.gpu-web.yml up --build
```

Open the UI from your machine:

```text
http://YOUR_VM_IP:8080
```

The browser talks to the frontend container on `WEB_PORT`. The frontend nginx
container proxies `/api` to the backend container, so you normally only need to
open `WEB_PORT` in your VM or cloud firewall.

Optional direct checks from the VM:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8100/health
```

### Docker Doctor Output

The GPU image intentionally does not include Node.js, npm, or frontend
dependencies. These failures are expected if you run `screencastgen doctor
--profile local-gpu` inside `screencastgen:gpu`:

```text
[FAIL] node: not found in PATH
[FAIL] npm: not found in PATH
[FAIL] frontend dependencies: not installed; run npm install in web/frontend
```

They do not block the GPU server or the web UI. The frontend is built by the
separate `web/frontend` Docker image in the full web stack.

### Docker Operations

Stop the full web stack:

```bash
sudo docker compose -f docker-compose.gpu-web.yml down
```

Follow all logs:

```bash
sudo docker compose -f docker-compose.gpu-web.yml logs -f
```

Follow one service:

```bash
sudo docker compose -f docker-compose.gpu-web.yml logs -f worker
sudo docker compose -f docker-compose.gpu-web.yml logs -f gpu-server
```

Rebuild only the web images after code changes:

```bash
sudo docker compose -f docker-compose.gpu-web.yml build backend worker frontend
sudo docker compose -f docker-compose.gpu-web.yml up
```

## 3. Source Installation On Ubuntu

Use this path when you want to run the project directly on the VM instead of
inside Docker.

Install host dependencies:

```bash
sudo apt-get update
sudo apt-get install -y \
  curl ca-certificates git ffmpeg build-essential python3.10-dev \
  postgresql postgresql-contrib redis-server
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt-get install -y nodejs
curl -LsSf https://astral.sh/uv/install.sh | sh
exec "$SHELL"
```

Clone and install:

```bash
git clone https://github.com/ShaShekhar/screencastgen.git
cd screencastgen
python3 scripts/setup.py --check
python3 scripts/setup.py --profile local-gpu
source .venv/bin/activate
```

The `local-gpu` setup creates the main Python environment, installs frontend
dependencies, installs LatentSync into a sidecar environment, downloads the
default Qwen, WhisperX, and LatentSync model weights, runs doctor, and verifies
the frontend build.

Set up local PostgreSQL and Redis for the web app:

```bash
sudo systemctl enable --now postgresql redis-server
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='screencastgen'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE USER screencastgen WITH PASSWORD 'screencastgen';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='screencastgen'" | grep -q 1 \
  || sudo -u postgres createdb -O screencastgen screencastgen
```

Create the web app environment file:

```bash
cat > web/.env <<'EOF'
P2A_DATABASE_URL=postgresql+asyncpg://screencastgen:screencastgen@localhost:5432/screencastgen
P2A_SYNC_DATABASE_URL=postgresql+psycopg2://screencastgen:screencastgen@localhost:5432/screencastgen
P2A_REDIS_URL=redis://localhost:6379/0
P2A_TTS_SERVER_URL=http://localhost:8100
P2A_UPLOAD_DIR=./uploads
P2A_OUTPUT_DIR=./outputs
P2A_ALLOWED_ORIGINS=["http://localhost:5173"]
EOF

mkdir -p web/uploads web/outputs
```

Start the GPU inference server in one terminal:

```bash
screencastgen-server --backend qwen --device cuda \
  --aligner whisperx --lipsync-provider latentsync
```

Prepare the web app:

```bash
cd web
make install
make migrate
```

Then run the backend, worker, and frontend in separate terminals:

```bash
cd web
make backend
```

```bash
cd web
make worker
```

```bash
cd web
make frontend
```

The frontend runs on `http://localhost:5173` and the backend runs on
`http://localhost:8000`.

## 4. Troubleshooting

If Docker cannot see the GPU, rerun:

```bash
sudo docker run --rm --gpus all nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04 nvidia-smi
```

If this fails, fix the NVIDIA Docker runtime before continuing.

If the web UI is not reachable from your machine:

- Confirm the compose stack is running.
- Confirm your VM or cloud firewall allows inbound TCP traffic on `WEB_PORT`.
- Run `curl http://localhost:8000/api/health` on the VM.
- Run `curl http://localhost:8100/health` on the VM.

If a job fails, inspect the worker and GPU server logs:

```bash
sudo docker compose -f docker-compose.gpu-web.yml logs -f worker
sudo docker compose -f docker-compose.gpu-web.yml logs -f gpu-server
```

If WhisperX falls back to CPU or reports a cuDNN library error during source
installation, inspect the active environment:

```bash
ldconfig -p | grep cudnn
find "$VIRTUAL_ENV" -name 'libcudnn_ops_infer.so*' 2>/dev/null
python -c "import torch; print(torch.__version__, torch.version.cuda)"
```
