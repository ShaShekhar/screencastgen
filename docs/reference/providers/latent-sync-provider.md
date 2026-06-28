# LatentSync Provider

> High-quality lip-sync video generation using LatentSync.

**Source:** [`screencastgen/providers/lipsync/latentsync_provider.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/lipsync/latentsync_provider.py)

---

## Overview

Generates lip-synced face videos by running LatentSync in a subprocess. Supports multiple quality presets and manages session caching for performance.

---

## Presets

### `LatentSyncPreset` (Dataclass)

| Preset | Resolution | Description |
|--------|-----------|-------------|
| `small` | 256px | Fast, suitable for small face overlays |
| `balanced_256` | 256px | Refined 256px path using guidance 1.5 and 30 inference steps |
| `quality` | 512px | High quality, larger face overlays |

Each preset specifies:
- `config_candidates` — Config file paths to search
- `checkpoint_candidates` — Model checkpoint paths
- `guidance_scale` — Diffusion guidance scale
- `inference_steps` — Number of inference steps

---

## Function

### `run_latentsync(video_path, audio_path, output_path, device="auto", preset="quality")`

1. Finds the LatentSync installation directory (via env var or path search)
2. Selects config and checkpoint for the preset
3. Spawns a worker subprocess (`latentsync_worker.py`)
4. Manages session caching and timeouts

### `download_latentsync_checkpoints(args)`
Downloads LatentSync model checkpoints. Called by [Models](../core/models.md).

---

## LatentSync Discovery

Finds the LatentSync root directory by:
1. Checking `LATENTSYNC_ROOT` environment variable
2. Searching common paths

---

## Dependencies

```
LatentSync Provider
├── latentsync         (external installation)
├── subprocess         (worker process)
├── TTS Base        (resolve_device)
└──▶ registered in Lipsync Registry
     └──▶ called by Lipsync Facade
```

---

## See Also

- [Lipsync Registry](lipsync-registry.md) — Provider registration
- [Lipsync Facade](../core/lipsync-facade.md) — Facade API
- [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) — Pipeline that uses lip-sync
- [Models](../core/models.md) — Checkpoint download
