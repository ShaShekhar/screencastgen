# Reader Router

> Serves browser-reader manifests, audio, presenter video, and PDF page images.

**Source:** [`web/backend/routers/reader.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/routers/reader.py)

---

## Endpoints

### `GET /api/jobs/{job_id}/reader/status`
Returns `{available, message}` for completed highlight/lip-sync jobs with a reader manifest.

### `GET /api/jobs/{job_id}/reader/manifest`
Loads and returns `reader_manifest.json`.

### `GET /api/jobs/{job_id}/reader/audio`
Streams `reader_audio.mp3`.

### `GET /api/jobs/{job_id}/reader/presenter`
Streams `presenter.mp4` for lip-sync reader jobs.

### `GET /api/jobs/{job_id}/reader/pages/{filename}`
Streams a rendered PDF page image from `pages/`. The filename is restricted to a plain basename to prevent traversal.

---

## Dependencies

```
Reader Router
├── Web Database        (job lookup)
├── DB Models           (Job, JobStatus)
├── Storage Service     (get_output_local_path)
└── Reader Assets       (asset filenames)
```

---

## See Also

- [Reader API](../frontend/reader-api.md) — Frontend client helpers
- [Reader Page](../frontend/reader-page.md) — Browser reader UI
- [Jobs Router](jobs-router.md) — Job lifecycle, primary downloads, and MP4/EPUB export endpoints
