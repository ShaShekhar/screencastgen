# Aligner

> Facade for word-level audio-text alignment.

**Source:** [`screencastgen/aligner.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/aligner.py)

---

## Overview

Thin facade that delegates to alignment providers registered in [Alignment Registry](../providers/alignment-registry.md). Provides a stable API that the rest of the codebase imports.

---

## Functions

### `align_chunk(audio_path, text, provider, language, device) -> List[WordTiming]`
Aligns audio with text to produce word-level timing data.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `audio_path` | `str` | — | Path to audio file |
| `text` | `str` | — | Transcript text |
| `provider` | `str` | `"whisperx"` | Alignment provider name |
| `language` | `str` | `"en-US"` | Language code |
| `device` | `str` | `"auto"` | Compute device |

**Returns:** `List[`[WordTiming](types.md)`]`

### Re-exported from [Alignment Registry](../providers/alignment-registry.md)
- `get_alignment_provider_names()`
- `get_default_alignment_provider()`

---

## Dependencies

```
Aligner
├── Alignment Registry   (provider dispatch)
├── Types                 (WordTiming)
└──▶ consumed by Pipeline Common
     └──▶ or Remote GPU Client (remote mode)
```

---

## See Also

- [WhisperX Provider](../providers/whisper-x-provider.md) — The default alignment implementation
- [Alignment Registry](../providers/alignment-registry.md) — Provider registration and dispatch
- [Remote GPU Client](remote-gpu-client.md) — Remote alignment via HTTP
- [Pipeline Common](../pipelines/pipeline-common.md) — `align_chunks()` helper
