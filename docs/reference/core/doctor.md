# Doctor

> Non-mutating validation of installation and runtime capabilities.

**Source:** [`screencastgen/doctor.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/doctor.py)
**CLI:** `screencastgen doctor`

---

## Overview

The doctor command inspects the active environment without installing packages,
downloading models, or changing configuration. It reports each check as `OK`,
`WARN`, or `FAIL` and exits nonzero when at least one required check fails.
Warnings do not affect the exit code.

## Profiles

| Profile | Behavior |
|---------|----------|
| `auto` | Select `local-gpu` on Linux/WSL2 when `nvidia-smi -L` succeeds; otherwise select `remote-client` |
| `local-gpu` | Validate CUDA, cuDNN compatibility, Qwen/WhisperX imports and caches, build tools, and the LatentSync sidecar/checkpoints |
| `remote-client` | Validate the client/web environment and optionally verify a remote server's `/health` response |
| `dev` | Validate common development, media, Python, and frontend dependencies without requiring local ML models |

All profiles check Python, core command-line tools, document/media/web imports,
and `web/frontend/node_modules`. `--model` selects the Qwen cache check (`0.6B`
or `1.7B`), and `--server-url` enables remote capability validation.

## Public API

| Symbol | Description |
|--------|-------------|
| `CheckResult` | Immutable result containing `level`, `name`, and `detail` |
| `resolve_profile(profile)` | Apply the shared automatic profile-selection rules |
| `collect_checks(profile, model, server_url)` | Return all common and profile-specific results |
| `run_doctor(profile, model, server_url, emit=print)` | Print results and return `0` on success or `1` when failures exist |

## Usage

```bash
screencastgen doctor --profile auto
screencastgen doctor --profile local-gpu --model 1.7B
screencastgen doctor --profile remote-client --server-url http://gpu-vm:8100
screencastgen doctor --profile dev
```

The remote health check requires `status: "ok"` and the `synthesize`,
`transcribe`, `align`, and `lipsync` capabilities.

## See Also

- [Setup Script](../configuration/setup-script.md) — Creates and validates the managed environment
- [CLI](cli.md) — Command registration and dispatch
- [Inference Server](inference-server.md) — Remote `/health` contract
- [Installation Guide](../../getting-started/installation.md) — Platform and manual setup instructions
