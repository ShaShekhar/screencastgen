# Remote TTS

> HTTP proxy TTS backend that delegates synthesis to a GPU inference server.

**Source:** [`screencastgen/providers/tts/remote_tts.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/tts/remote_tts.py)

---

## Overview

Implements the [TTSBackend](../core/types.md) protocol by proxying requests to a [GPU inference server](../core/inference-server.md) over HTTP. This is the TTS piece of the CPU/GPU split architecture.

At startup it queries `GET /health` to discover:
- `output_format`
- `max_chunk_bytes`

Those values are then used by local chunking and output handling.

---

## Class: `RemoteTTS`

### Properties

| Property | Source | Description |
|----------|--------|-------------|
| `max_chunk_bytes` | Server `/health` | Remote backend chunk limit |
| `output_format` | Server `/health` | Remote backend output format |

### Constructor
```python
RemoteTTS(
    server_url="http://localhost:8100",
    language="en-US",
    timeout=300,
    ref_audio_path=None,
    ref_text=None,
)
```

On init, the backend:
- normalizes `server_url`
- optionally reads and caches reference audio bytes
- queries `GET /health`

### Methods

| Method | Description |
|--------|-------------|
| `synthesize(text, output_path)` | Send one request to `/synthesize` and write returned audio bytes |

---

## Request Formats

### Without voice cloning

Sends `application/json`:
- `text`
- `language`

### With voice cloning

Sends `multipart/form-data`:
- `text`
- `language`
- `ref_audio`
- `ref_text` when available

The server is responsible for batching compatible requests.

---

## BackendSpec

| Field | Value |
|-------|-------|
| **Name** | `remote` |
| **Contexts** | `cli` |
| **Capabilities** | `remote`, `server_managed_reference` |

### Extra Args

| Arg | Type | Default | Description |
|-----|------|---------|-------------|
| `--tts-server-url` | `str` | `http://localhost:8100` | GPU server URL |

---

## Dependencies

```
Remote TTS
├── urllib.request      (HTTP)
├── TTS Base        (BackendSpec, BackendArg)
└──▶ registered in TTS Registry
     └──▶ talks to Inference Server
```

---

## See Also

- [Inference Server](../core/inference-server.md) — The server this connects to
- [Remote GPU Client](../core/remote-gpu-client.md) — Alignment and lip-sync remote calls
- [Qwen Backend](qwen-backend.md) — Direct local/server backend
- [Architecture](../../concepts/architecture.md) — CPU/GPU split design
