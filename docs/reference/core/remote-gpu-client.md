# Remote GPU Client

> HTTP client for offloading ML work to a GPU inference server.

**Source:** [`screencastgen/remote_gpu.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/remote_gpu.py)

---

## Overview

When the `remote` backend is selected, all ML-intensive operations (TTS, alignment, lip-sync) are offloaded to a [GPU inference server](inference-server.md) over HTTP. This module provides the client-side functions for alignment and lip-sync. TTS is handled by [Remote TTS](../providers/remote-tts.md).

---

## Functions

### `remote_align_chunk(audio_path, text, server_url, language, provider, timeout) -> List[WordTiming]`
Sends audio + text to the GPU server for word-level alignment.

**Endpoint:** `POST /align`
**Content-Type:** `multipart/form-data`
**Response:** JSON array of word timings

### `remote_generate_lipsync(audio_path, reference_video_path, output_path, server_url, provider, latentsync_preset, poll_interval, request_timeout, should_cancel, on_status)`
Submits audio + reference video to the GPU server for lip-sync generation, polls the returned job handle, downloads the final video, and requests cleanup.

**Endpoints:** `POST /lipsync`, `GET /lipsync/{id}`, `GET /lipsync/{id}/result`, `POST /lipsync/{id}/cancel`, `DELETE /lipsync/{id}`
**Content-Type:** `multipart/form-data`
**Response:** Writes video bytes to `output_path`

`poll_interval` defaults to 5 seconds and `request_timeout` defaults to 120
seconds per HTTP operation; there is no overall generation timeout. Up to four
transient polling failures are tolerated, with the fifth consecutive failure
reported as lost server contact.

If `should_cancel()` returns true while polling, the client sends a best-effort
cancel request and raises `LipsyncCancelled`. `on_status(elapsed)` receives
elapsed seconds from each successful poll. Cleanup with `DELETE` runs in a
`finally` block whether the job succeeds, fails, or is cancelled.

For backward compatibility, a server that returns video bytes directly from the
initial `POST /lipsync` is treated as the legacy synchronous protocol and the
bytes are written without polling.

---

## Dependencies

```
Remote GPU Client
├── urllib.request   (HTTP, no requests dependency)
├── Types         (WordTiming)
└──▶ consumed by Pipeline Common (remote alignment)
     └──▶ consumed by Lipsync Pipeline (remote lipsync)
```

---

## See Also

- [Inference Server](inference-server.md) — The server that receives these requests
- [Remote TTS](../providers/remote-tts.md) — TTS-specific remote client (separate module)
- [Pipeline Common](../pipelines/pipeline-common.md) — `align_chunks()` uses remote alignment when GPU server URL is set
- [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) — Uses `remote_generate_lipsync()` when backend is remote
- [Data Flow](../../concepts/data-flow.md) — Remote GPU flow diagram
