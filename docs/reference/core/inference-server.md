# Inference Server

> FastAPI-based GPU inference server for TTS, transcription, alignment, and lip-sync.

**Source:** [`screencastgen/inference_server.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/inference_server.py)
**Entry point:** `screencastgen-server`

---

## Overview

Runs on a GPU machine and exposes ML capabilities over HTTP. This enables a CPU/GPU split architecture where the [CLI](cli.md) or [web worker](../web/backend/pipeline-tasks.md) runs on a CPU-only machine and offloads ML work here.

The server loads a TTS backend eagerly at startup, exposes HTTP endpoints for runtime inference, and batches compatible `/synthesize` requests into a single GPU forward pass.

---

## Endpoints

### `POST /synthesize`
Text-to-speech synthesis.

Accepts either:
- `application/json` with `text` and `language`
- `multipart/form-data` with `text`, `language`, optional `ref_audio`, and optional `ref_text`

Compatible concurrent requests are coalesced by the background batcher when they share:
- normalized language
- the same reference voice inputs, if cloning is used

**Response:** audio bytes using the backend's `output_format`

### `POST /transcribe`
Audio-to-text transcription.

| Field | Type | Description |
|-------|------|-------------|
| `audio` | file | Audio file to transcribe |
| `language` | form | Language code, default `en-US` |

Used by Celery pipeline workers to generate missing `ref_text` when a submitted highlight
or lip-sync job actually consumes reference audio. Upload requests never call this endpoint.

**Response:** JSON object with `text`

### `POST /align`
Word-level audio-text alignment.

| Field | Type | Description |
|-------|------|-------------|
| `audio` | file | Audio file |
| `text` | form | Transcript |
| `language` | form | Language code |
| `provider` | form | Alignment provider override (optional) |

**Response:** JSON object with `words: [{word, start, end}]`

### `POST /lipsync`
Submit a lip-sync video generation job.

| Field | Type | Description |
|-------|------|-------------|
| `audio` | file | Audio file |
| `reference_video` | file | Reference face video |
| `provider` | form | Provider name override |
| `latentsync_preset` | form | LatentSync preset |

**Response:** JSON job handle, e.g. `{ "lipsync_id": "...", "status": "queued" }`

### `GET /lipsync/{job_id}`
Return lip-sync job status and elapsed generation time.

### `GET /lipsync/{job_id}/result`
Download the finished MP4. Returns `409` if the job is not done.

### `POST /lipsync/{job_id}/cancel`
Request cancellation. Queued jobs are marked cancelled immediately; running jobs discard their result after the active generation call exits.

### `DELETE /lipsync/{job_id}`
Discard the server-side job record and output file.

### `GET /health`
Server status and runtime capabilities.

**Response shape:**
```json
{
  "status": "ok",
  "backend": "qwen",
  "output_format": "wav",
  "max_chunk_bytes": 1500,
  "device": "cuda",
  "aligner": "whisperx",
  "lipsync_provider": "auto",
  "capabilities": ["synthesize", "transcribe", "align", "lipsync"]
}
```

---

## Runtime Behavior

### TTS Batching

- The server requires a backend that implements `synthesize_batch(...)`.
- `BatchingSynthesizer` groups compatible `/synthesize` requests into batches.
- Reference-audio clone requests preserve the uploaded file suffix when materialized to temp files.
- Batch size and coalescing delay are configured by CLI flags.

### Async Lip-Sync Jobs

- `/lipsync` returns quickly with a job ID so long GPU runs do not hold an HTTP socket open.
- A background thread runs generation while a GPU lock serializes work to avoid VRAM contention.
- Clients poll `/lipsync/{id}` for `queued`, `running`, `done`, `failed`, or `cancelled`.
- Status responses include elapsed generation seconds and an error string when applicable.
- Cancellation is cooperative: queued work is skipped, while an active provider call may finish but its output is discarded.
- Clients should call `DELETE /lipsync/{id}` after downloading or abandoning the result.
- Uploaded audio/reference-video temp files are removed when generation exits; deleting a completed job also removes its output MP4.

### Transcription Model Reuse

- WhisperX transcription is loaded lazily on first `/transcribe` request.
- Loaded transcribers are cached by `(model_name, device, compute_type)`.
- Inference on a cached transcriber is serialized with a lock for safe reuse.

### WhisperX GPU Runtime Requirements

- `/align` and `/transcribe` can use WhisperX on GPU when the server is started with `--device cuda`.
- On some GPU VM images, PyTorch reports CUDA as available but the process cannot load the cuDNN 8 runtime required by WhisperX dependencies.
- The failure usually appears as `Could not load library libcudnn_ops_infer.so.8`.
- In that case, the WhisperX compatibility layer falls back to CPU for WhisperX-specific work so the server stays up.
- To restore GPU execution for WhisperX, install a cuDNN 8 runtime and ensure the server process inherits an `LD_LIBRARY_PATH` that includes the directory containing `libcudnn_ops_infer.so.8`.

Example verification:

```bash
export CUDNN_LIB_DIR="$VIRTUAL_ENV/lib/python3.10/site-packages/nvidia/cudnn/lib"
export LD_LIBRARY_PATH="$CUDNN_LIB_DIR:$LD_LIBRARY_PATH"
python -c "import ctypes; ctypes.CDLL('libcudnn_ops_infer.so.8'); print('ok')"
```

---

## Startup Options

In addition to the normal backend and provider arguments, the server exposes:

| Arg | Default | Description |
|-----|---------|-------------|
| `--max-batch` | `8` | Maximum number of compatible `/synthesize` requests coalesced into one model call |
| `--batch-window-ms` | `30` | Milliseconds to wait for more compatible requests before dispatching a partial batch |

---

## Dependencies

```
Inference Server
├── FastAPI + uvicorn        (HTTP server)
├── python-multipart         (file uploads)
├── TTS Registry         (create backend)
├── Alignment Registry   (alignment providers)
├── Lipsync Registry     (lip-sync providers)
├── Pipeline Common      (indirect runtime contract via backend limits)
├── Inference Batcher    (request coalescing for /synthesize)
└── Transcription        (WhisperX transcription helper)
```

---

## Usage

```bash
screencastgen-server --backend qwen --device cuda
screencastgen-server --backend qwen --device cuda --max-batch 8 --batch-window-ms 30
screencastgen-server --backend qwen --device cuda --host 0.0.0.0 --port 8100
```

---

## See Also

- [Remote TTS](../providers/remote-tts.md) — Client for `/synthesize`
- [Remote GPU Client](remote-gpu-client.md) — Client for `/align` and async `/lipsync`
- [Architecture](../../concepts/architecture.md) — CPU/GPU split design
- [Data Flow](../../concepts/data-flow.md) — Remote GPU flow diagram
