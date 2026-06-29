# Jobs API

> Client functions for job CRUD operations.

**Source:** [`web/frontend/src/api/jobs.ts`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/api/jobs.ts)

---

## Functions

| Function | HTTP | Endpoint | Description |
|----------|------|----------|-------------|
| `createJob(req)` | POST | `/api/jobs` | Create job + dispatch |
| `listJobs(status?, limit, offset)` | GET | `/api/jobs` | List with filter/pagination |
| `getJob(id)` | GET | `/api/jobs/{id}` | Get single job |
| `deleteJob(id)` | DELETE | `/api/jobs/{id}` | Delete job + files |
| `stopJob(id)` | POST | `/api/jobs/{id}/stop` | Request early stop for a running lip-sync job |
| `getDownloadUrl(id)` | — | `/api/jobs/{id}/download` | Returns URL string |
| `requestEpubExport(id)` | POST | `/api/jobs/{id}/export-epub` | Start a text-and-narration EPUB export |
| `getEpubExportStatus(id)` | GET | `/api/jobs/{id}/export-epub/status` | Poll EPUB export state |
| `getEpubExportDownloadUrl(id)` | — | `/api/jobs/{id}/export-epub/download` | Returns exported EPUB URL string |

---

## Types Used

- `JobCreateRequest` — Request body for `createJob()`
- `Job` — Response from `getJob()`
- `JobListResponse` — Response from `listJobs()`
- `EpubExportState` — Independent export status response

All types defined in `types/index.ts`.

---

## Consumers

- [Dashboard Page](dashboard-page.md) — `listJobs()`
- [NewJob Page](new-job-page.md) — `createJob()`
- [JobDetail Page](job-detail-page.md) — `getJob()`, `deleteJob()`, `getDownloadUrl()`
- [LipsyncRunPanel](lipsync-run-panel.md) — `stopJob()`
- [Reader Page](reader-page.md) — Offline-reader download and EPUB export helpers

---

## Backend

Calls [Jobs Router](../backend/jobs-router.md) endpoints.

---

## See Also

- [API Client](api-client.md) — Base Axios instance
- [Jobs Router](../backend/jobs-router.md) — Backend endpoints
- [Schemas](../backend/schemas.md) — API request/response shapes
