# Setup Script

> Cross-platform bootstrap for a managed `.venv` and frontend dependencies.

**Source:** [`scripts/setup.py`](https://github.com/ShaShekhar/screencastgen/blob/main/scripts/setup.py)
**User guide:** [Installation](../../getting-started/installation.md)

---

## Overview

The setup script performs prerequisite checks, creates `.venv` with Python 3.10,
installs the selected editable extras with `uv`, installs locked frontend
dependencies, validates the result with [Doctor](../core/doctor.md), and builds the frontend.
`--check` stops after the non-mutating prerequisite pass.

## Profiles

| Profile | Python extras | Additional work |
|---------|---------------|-----------------|
| `local-gpu` | `all,dev` | Install LatentSync sidecar and download Qwen/WhisperX models |
| `remote-client` | `client,web,dev` | Optionally validate a remote GPU server |
| `dev` | `client,web,dev` | Development environment without local GPU models |
| `auto` | Resolves to one of the profiles above | Select `local-gpu` only on Linux/WSL2 with an accessible NVIDIA GPU; otherwise select `remote-client` |

Native Windows and macOS reject `local-gpu`; Windows users can use WSL2 for the
local CUDA stack. Profile resolution intentionally matches [Doctor](../core/doctor.md).

## Command-Line Interface

| Option | Default | Description |
|--------|---------|-------------|
| `--profile auto|local-gpu|remote-client|dev` | `auto` | Installation capability profile |
| `--model 0.6B|1.7B` | `0.6B` | Qwen model downloaded and checked for `local-gpu` |
| `--server-url URL` | none | Remote GPU server passed to the final doctor run |
| `--check` | false | Check prerequisites without creating or changing the environment |

```bash
python3 scripts/setup.py --check
python3 scripts/setup.py --profile auto
py scripts/setup.py --profile remote-client --server-url http://gpu-vm:8100
```

The prerequisite pass requires Git, uv, Node/npm, ffmpeg, and ffprobe. The local
GPU profile additionally requires the compiler toolchain, Bash, and a working
`nvidia-smi` command. Failures include platform-specific installation guidance
and return a nonzero exit code.

## Installation Flow

1. Create `.venv` with `uv venv --python 3.10`.
2. Install the selected editable Python extras.
3. Run `npm ci` when `package-lock.json` exists.
4. For `local-gpu`, install LatentSync and preload Qwen/WhisperX models.
5. Run [Doctor](../core/doctor.md) with the resolved profile.
6. Run the production frontend build.

## See Also

- [Doctor](../core/doctor.md) — Non-mutating post-install validation
- [pyproject.toml](pyproject-toml.md) — Extras installed by each profile
- [Web Makefile](web-makefile.md) — Individual web development commands
