# FileUploader

> Drag-and-drop file upload with progress indicator.

**Source:** [`web/frontend/src/components/FileUploader.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/components/FileUploader.tsx)

---

## Props

```typescript
{
  accept: string                        // MIME types (e.g., ".pdf,.txt,.epub")
  label: string                         // Display label
  onUploaded: (file: UploadedFile) => void  // Callback on success
  showPreview?: boolean                 // Show an inline preview link after upload
}
```

---

## Features

- **Drag-and-drop** zone with visual feedback
- **Click to browse** fallback
- **Upload progress** percentage display
- **Optional preview link** using `getUploadPreviewUrl()` when `showPreview` is true
- **Error display** on failure
- Calls `uploadFile()` from [Uploads API](uploads-api.md)

---

## State

| State | Type | Description |
|-------|------|-------------|
| `dragOver` | `boolean` | Drag hover state |
| `uploading` | `boolean` | Upload in progress |
| `progress` | `number` | Upload percentage |
| `fileName` | `string \| null` | Selected file name |
| `uploadedFile` | `UploadedFile \| null` | Uploaded file metadata used for preview links |
| `error` | `string \| null` | Error message |

---

## Used By

- [NewJob Page](new-job-page.md) — Document upload
- [LipsyncSettings](lipsync-settings.md) — Reference audio/video uploads

---

## See Also

- [Uploads API](uploads-api.md) — `uploadFile()` function
- [Uploads Router](../backend/uploads-router.md) — Backend endpoint
