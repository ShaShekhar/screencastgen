# Uploads Router

> File upload endpoint for documents and reference media.

**Source:** [`web/backend/routers/uploads.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/routers/uploads.py)

---

## Endpoints

### `POST /api/uploads`

Upload a document file or reference audio/video file.

**Request:** `multipart/form-data` with `file`

### Validation

- file must have a filename
- file size must be under `MAX_UPLOAD_SIZE_MB` from [Web Config](web-config.md)

### Process

1. Read the uploaded bytes.
2. Persist the file through [Storage Service](storage-service.md).
3. Create an [UploadedFile](db-models.md) row with `ref_text` unset.
4. Return an [UploadResponse](schemas.md).

The upload endpoint never calls or enqueues `/transcribe`. Pipeline workers transcribe
reference audio on demand when a submitted job actually uses it.

### Response

```json
{
  "id": "uuid",
  "original_name": "voice.wav",
  "size_bytes": 123456,
  "content_type": "audio/wav"
}
```

### `GET /api/uploads/{file_id}/preview`

Streams an uploaded file inline for new-job previews.

Preview is allowed for:

- PDF, TXT, and EPUB documents
- common browser video formats (`.mp4`, `.mov`, `.m4v`, `.webm`, `.ogg`, `.ogv`)
- uploads whose content type starts with `video/`

The response sets `Content-Disposition: inline` and uses a guessed media type when possible.

---

## Dependencies

```
Uploads Router
├── Web Database         (async session)
├── DB Models            (UploadedFile)
├── Schemas              (UploadResponse)
├── Storage Service      (save_upload, get_upload_abs_path)
└── Web Config           (MAX_UPLOAD_SIZE_MB)
```

---

## See Also

- [Jobs Router](jobs-router.md) — References uploaded files by ID
- [Storage Service](storage-service.md) — File I/O implementation
- [Uploads API](../frontend/uploads-api.md) — Frontend API client
