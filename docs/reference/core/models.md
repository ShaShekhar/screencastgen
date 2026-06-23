# Models

> Model download management for ML dependencies.

**Source:** [`screencastgen/models.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/models.py)

---

## Overview

Manages downloading and caching of ML model checkpoints. Supports pre-downloading models so that pipeline runs don't need network access.

---

## Dataclass

### `ModelPackageSpec`
Metadata for a downloadable model package.

---

## Functions

### `register_model_download_args(parser)`
Registers repeatable `--backend` and `--package` selectors, `--all`, and target-specific download arguments. Current packages are `whisperx` and `latentsync`; Qwen is selected as a backend.

### `download_selected_models(args) -> int`
Main orchestrator. Downloads models based on CLI flags.

### `_get_cache_dir() -> str`
Returns the model cache directory.

### `_download_whisperx(args)`
Downloads WhisperX model checkpoints.

### `_download_latentsync(args)`
Downloads LatentSync checkpoints via [LatentSync Provider](../providers/latent-sync-provider.md).

---

## Dependencies

```
Models
├── TTS Registry            (get_backend_spec, download registration)
├── TTS Base                (BackendArg)
├── LatentSync Provider     (download_latentsync_checkpoints)
└──▶ consumed by CLI (download-models subcommand)
```

---

## Usage

```bash
screencastgen download-models --backend qwen --model 1.7B
screencastgen download-models --package whisperx --package latentsync
screencastgen download-models --all
```

Qwen downloads use Hugging Face snapshot caching without loading the TTS model into memory. A local path supplied through `--model` is accepted without downloading.

---

## See Also

- [CLI](cli.md) — `download-models` subcommand
- [Qwen Backend](../providers/qwen-backend.md) — Has its own `download_models` function
- [LatentSync Provider](../providers/latent-sync-provider.md) — Has checkpoint download logic
