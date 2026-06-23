# Inference Batcher

> Coalesces concurrent `/synthesize` requests into batched backend calls on the inference server.

**Source:** [`screencastgen/inference_batcher.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/inference_batcher.py)

---

## Overview

`BatchingSynthesizer` sits behind [Inference Server](inference-server.md) `/synthesize`. The server still accepts individual HTTP requests, but the batcher groups compatible requests and calls `backend.synthesize_batch(...)` once.

Compatibility is based on normalized language plus reference voice inputs. Voice-clone requests only batch together when their reference audio bytes, reference text, and file suffix match.

---

## Flow

```
/synthesize request
    │
    ▼
submit(text, language, ref_audio, ref_text)
    │
    ▼
QueueItem + Future
    │
    ▼
worker waits up to batch_window_ms for compatible items
    │
    ▼
backend.synthesize_batch(texts=[...])
    │
    ▼
resolve each Future with its audio bytes
```

---

## Tuning

| Setting | Default | Effect |
|---------|---------|--------|
| `max_batch` | `8` | Maximum compatible requests in one model call |
| `batch_window_ms` | `30` | Wait time for more compatible requests before dispatch |

The web worker's `tts_concurrency` feeds the server enough parallel requests for batching to matter.

---

## See Also

- [Inference Server](inference-server.md) — Owns the batcher lifecycle
- [Remote TTS](../providers/remote-tts.md) — Client that submits synthesis requests
- [Pipeline Common](../pipelines/pipeline-common.md) — Parallel chunk synthesis
