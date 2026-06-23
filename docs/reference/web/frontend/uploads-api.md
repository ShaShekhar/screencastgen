# Uploads API

> File upload with progress tracking.

**Source:** [`web/frontend/src/api/uploads.ts`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/api/uploads.ts)

---

## Function

### `uploadFile(file: File, onProgress?: (pct: number) => void): Promise<UploadedFile>`

Uploads a file as `multipart/form-data` to `POST /api/uploads`.

**Features:**
- progress callback receiving percentage `0-100`
- returns uploaded-file metadata including:
  - `id`
  - `original_name`
  - `size_bytes`
  - `content_type`

**Used by:** [FileUploader](file-uploader.md)

### `getUploadPreviewUrl(id: string): string`

Returns `/api/uploads/{id}/preview` for document/video previews in [FileUploader](file-uploader.md) and [LipsyncPreviewFrame](lipsync-preview-frame.md).

---

## Backend

Calls the [Uploads Router](../backend/uploads-router.md) endpoint.

---

## See Also

- [API Client](api-client.md) — Base Axios instance
- [FileUploader](file-uploader.md) — Component that uses this
- [Uploads Router](../backend/uploads-router.md) — Backend endpoint
