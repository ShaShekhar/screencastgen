# Getting started

The managed setup script selects a supported environment profile, installs the
matching dependencies, and verifies the result. Local CUDA models are supported
on Linux and WSL2 with an accessible NVIDIA GPU. Other environments can run the
development stack or connect to a remote GPU server.

## 1. Install

Follow the complete [installation guide](installation.md). For the default
automatic setup on Linux or macOS:

```bash
git clone https://github.com/ShaShekhar/screencastgen.git
cd screencastgen
python3 scripts/setup.py --profile auto
source .venv/bin/activate
```

On Windows PowerShell, use `py scripts/setup.py` and activate with
`.venv\Scripts\Activate.ps1`.

## 2. Verify the environment

```bash
screencastgen doctor --profile auto
```

Use an explicit profile when diagnosing a specific deployment:

```bash
screencastgen doctor --profile local-gpu --model 1.7B
screencastgen doctor --profile remote-client --server-url http://gpu-vm:8100
screencastgen doctor --profile dev
```

Warnings do not fail the command. Missing requirements for the selected profile
produce a nonzero exit code.

## 3. Run a pipeline

```bash
screencastgen audio book.pdf
screencastgen highlight book.pdf --format epub
screencastgen lipsync book.pdf --ref-audio voice.wav --ref-video face.mp4
```

Continue with a [workflow guide](../guides/index.md) for inputs, outputs, and
deployment-specific options.
