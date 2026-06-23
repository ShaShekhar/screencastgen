# Reader API

> Client helpers for the browser reader experience attached to completed highlight/lip-sync jobs.

**Source:** [`web/frontend/src/api/reader.ts`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/api/reader.ts)

---

## Functions

| Function | HTTP | Endpoint | Description |
|----------|------|----------|-------------|
| `getReaderStatus(jobId)` | GET | `/api/jobs/{jobId}/reader/status` | Check whether the browser reader is available and return a status message |
| `getReaderManifest(jobId)` | GET | `/api/jobs/{jobId}/reader/manifest` | Fetch the reader manifest with chunk timing, page mapping, and metadata |
| `getReaderAudioUrl(jobId)` | — | `/api/jobs/{jobId}/reader/audio` | Returns the reader audio URL string |
| `getReaderPresenterUrl(jobId)` | — | `/api/jobs/{jobId}/reader/presenter` | Returns the presenter video URL string for lip-sync reader jobs |
| `getReaderPageUrl(jobId, filename)` | — | `/api/jobs/{jobId}/reader/pages/{filename}` | Returns the rendered page image URL string |

---

## Types Used

- `ReaderStatus` — Availability flag plus user-facing status message
- `ReaderManifest` — Reader metadata, page image map, and aligned chunks

All types are defined in `web/frontend/src/types/index.ts`.

---

## Consumers

- [JobDetail Page](job-detail-page.md) — `getReaderStatus()`
- [Reader Page](reader-page.md) — `getReaderManifest()`, `getReaderAudioUrl()`, `getReaderPresenterUrl()`, `getReaderPageUrl()`

---

## Backend

Calls browser reader endpoints under [Reader Router](../backend/reader-router.md).

---

## See Also

- [Reader Page](reader-page.md) — Full-screen browser reader UI
- [Reader Router](../backend/reader-router.md) — Backend reader endpoints
- [Schemas](../backend/schemas.md) — API payload shapes
