# Qwen Backend

> Local Qwen3-TTS backend used directly by the CLI or behind the inference server.

**Source:** [`screencastgen/providers/tts/qwen_backend.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/tts/qwen_backend.py)

---

## Overview

Implements the [TTSBackend](../core/types.md) protocol using Qwen3-TTS for local text-to-speech synthesis. It supports:

- multi-language generation
- optional voice cloning with `ref_audio_path` and `ref_text`
- batched synthesis through `synthesize_batch(...)` for the inference server

---

## Class: `QwenTTS`

### Properties

| Property | Value | Description |
|----------|-------|-------------|
| `max_chunk_bytes` | `1500` | Conservative text limit exposed to chunking and validation |
| `output_format` | `"wav"` | Output audio format |

### Constructor
```python
QwenTTS(
    model_name=None,
    ref_audio_path=None,
    ref_text=None,
    language="en-US",
    device="auto",
)
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `model_name` | `str \| None` | `None` | Model alias or full Hugging Face model name |
| `ref_audio_path` | `str \| None` | `None` | Reference audio file for voice cloning |
| `ref_text` | `str \| None` | `None` | Transcript for the reference audio |
| `language` | `str` | `"en-US"` | Language code mapped to Qwen language labels |
| `device` | `str` | `"auto"` | Compute device |

### Methods

| Method | Description |
|--------|-------------|
| `synthesize(text, output_path)` | Generate one audio clip and write it to disk |
| `synthesize_batch(texts, language=None, ref_audio_path=None, ref_text=None)` | Generate multiple WAV payloads in one model call |

---

## Models

Default model:
- `Qwen/Qwen3-TTS-12Hz-0.6B-Base`

Built-in aliases:
- `0.6b`
- `0.6B`
- `1.7b`
- `1.7B`

Supported language map includes:
- English
- Chinese
- Japanese
- Korean
- German
- French
- Russian
- Portuguese
- Spanish
- Italian

---

## BackendSpec

Registered in [TTS Registry](tts-registry.md) with:
- **Contexts:** `cli`, `server`
- **Capabilities:** `local`, `voice_clone`
- **Extra args:** `--model`

The inference server currently expects this backend to provide `synthesize_batch(...)`.

The model download hook uses `huggingface_hub.snapshot_download()` to populate the cache without constructing the Qwen model. If the selected model value resolves to a local path, the download step leaves it unchanged.

---

## Dependencies

```
Qwen Backend
├── qwen-tts            (deferred import)
├── torch               (deferred import)
├── soundfile           (deferred import)
├── TTS Base        (resolve_device, BackendSpec)
└──▶ registered in TTS Registry
```

---

## See Also

- [Inference Server](../core/inference-server.md) — Uses the batched synthesis path
- [Remote TTS](remote-tts.md) — HTTP proxy frontend to the server
- [TTS Registry](tts-registry.md) — Backend registration
- [Types](../core/types.md) — `TTSBackend` protocol
