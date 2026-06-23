# LipsyncPreviewFrame

> New-job preview of how the lip-sync reader will combine the document with the presenter video.

**Source:** [`web/frontend/src/components/LipsyncPreviewFrame.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/components/LipsyncPreviewFrame.tsx)

---

## Props

```typescript
{
  uploadedFile?: UploadedFile | null
  config: LipsyncConfig
}
```

---

## Behavior

- Renders a compact reader-like frame using the same persisted `reader-theme` preference as [Reader Page](reader-page.md).
- Uses upload preview URLs for the document and reference video.
- Shows text files as fetched text; non-text documents are embedded with native viewer chrome suppressed where supported.
- Seeds the presenter position from `face_position`, scales it from `face_scale`, and lets the user drag it inside the preview frame.
- Requires both a document upload and a reference video upload before showing the preview.

---

## Used By

- [NewJob Page](new-job-page.md) — Lip-sync configuration section

---

## See Also

- [Reader Page](reader-page.md) — Runtime reader experience
- [LipsyncSettings](lipsync-settings.md) — Inputs that drive the preview
