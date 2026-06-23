# Lipsync Facade

> Facade for lip-sync video generation from audio + reference video.

**Source:** [`screencastgen/lipsync.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/lipsync.py)

---

## Overview

Provides a stable API for lip-sync generation, delegating to providers in [Lipsync Registry](../providers/lipsync-registry.md). Handles video looping to match audio duration.

---

## Functions

### `generate_lipsync_video(audio_path, reference_video_path, output_path, provider, device, latentsync_preset) -> str`
Generates a lip-synced video from audio and a reference face video.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `audio_path` | `str` | — | Path to audio file |
| `reference_video_path` | `str` | — | Path to face reference video |
| `output_path` | `str` | — | Output video path |
| `provider` | `str` | `"auto"` | Lipsync provider name |
| `device` | `str` | `"auto"` | Compute device |
| `latentsync_preset` | `str` | `"quality"` | LatentSync quality preset |

### `_get_audio_duration(audio_path) -> float`
Returns duration of an audio file in seconds.

### `_loop_video_to_duration(video_path, duration, output_path) -> str`
Loops a reference video to match the target audio duration using ffmpeg.

---

## Dependencies

```
Lipsync Facade
├── Lipsync Registry       (provider dispatch)
├── TTS Base               (resolve_device)
├── ffmpeg CLI                 (video looping)
└──▶ consumed by Lipsync Pipeline
     └──▶ or Remote GPU Client (remote mode)
```

---

## See Also

- [LatentSync Provider](../providers/latent-sync-provider.md) — Primary lip-sync implementation
- [Lipsync Registry](../providers/lipsync-registry.md) — Provider registration
- [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) — Pipeline that uses this facade
