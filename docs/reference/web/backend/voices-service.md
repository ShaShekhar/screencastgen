# Voices Service

> Bundled voice manifest loader.

**Source:** [`web/backend/services/voices.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/services/voices.py)

---

## Overview

Reads a `manifest.json` file from `web/backend/voices/` that defines bundled voice samples. Each voice has a reference audio file and metadata.

---

## Class: `BundledVoice`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique voice identifier |
| `name` | `str` | Display name |
| `language` | `str` | Language code |
| `description` | `str` | Voice description |
| `file` | `str` | Reference audio filename |
| `ref_text` | `str` | Reference transcript |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `abs_path` | `Path` | Absolute path to audio file |
| `exists` | `bool` | Whether the audio file exists on disk |

---

## Functions

| Function | Description |
|----------|-------------|
| `load_voices() -> List[BundledVoice]` | Load all voices from manifest.json |
| `get_voice(voice_id) -> BundledVoice` | Look up a voice by ID |

---

## Dependencies

```
Voices Service
├── manifest.json     (voice definitions)
└──▶ consumed by Voices Router
     └──▶ consumed by Pipeline Tasks (voice resolution)
```

---

## See Also

- [Voices Router](voices-router.md) — Exposes voices via API
- [Pipeline Tasks](pipeline-tasks.md) — Resolves voice_id to ref_audio path
- [VoiceSettings](../frontend/voice-settings.md) — Frontend voice picker
