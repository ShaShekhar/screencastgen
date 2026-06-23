# Transcribe Client

> Best-effort HTTP client for the GPU server `/transcribe` endpoint.

**Source:** [`web/backend/services/transcribe_client.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/services/transcribe_client.py)

---

## Function

### `transcribe_upload(server_url, audio_path, language="en-US", timeout=300) -> str | None`

Posts an audio file to `{server_url}/transcribe` as multipart form data and returns the trimmed `text` field.

Failures are logged and return `None`:

- audio file cannot be read
- server is unreachable
- response is not valid JSON
- transcript is empty

Job creation is unaffected because this client runs inside the Celery worker. Pipeline
request builders treat a `None` result as a clear job error when reference text is required.

---

## Used By

- [Pipeline Tasks](pipeline-tasks.md) — Generates missing `ref_text` on demand for uploaded highlight/lip-sync reference audio and extracted reference-video audio

---

## See Also

- [Inference Server](../../core/inference-server.md) — `/transcribe`
- [Transcription](../../core/transcription.md) — Server-side helper
