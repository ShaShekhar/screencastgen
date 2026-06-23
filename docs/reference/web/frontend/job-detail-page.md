# JobDetail Page

> Job monitoring with real-time progress and download.

**Source:** [`web/frontend/src/pages/JobDetail.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/pages/JobDetail.tsx)
**Route:** `/jobs/:id`

---

## Features

- **Job metadata** — ID, pipeline type, creation date
- **Real-time progress** — [ProgressBar Component](progress-bar-component.md) updated via [SSE](use-job-progress-hook.md)
- **Reader entry point** — Completed highlight/lip-sync jobs show an `Open in Reader` CTA while availability is ready or still being checked
- **Lip-sync run details** — Running lip-sync jobs show per-page timings and a confirmed stop control via [LipsyncRunPanel](lipsync-run-panel.md)
- **Partial-run result** — A completed job that was stopped early shows the completed and total page counts from pipeline result metadata
- **Visualization output** — Completed visualization jobs show an inline MP4 preview, generated source, and render log excerpts
- **Download** — Non-reader outputs, or reader jobs without reader availability, fall back to the direct download link
- **Error display** — Error message when failed
- **Delete** — With confirmation dialog
- **Auto-refresh** — Re-fetches job data on completion/failure

---

## State

| State | Type | Description |
|-------|------|-------------|
| `job` | `Job \| null` | Job data |
| `loading` | `boolean` | Initial fetch in progress |
| `deleting` | `boolean` | Delete in progress |
| `showConfirm` | `boolean` | Delete confirmation dialog |

---

## Status-Based Display

| Status | Shows |
|--------|-------|
| `pending` | [ProgressBar Component](progress-bar-component.md) (waiting) |
| `running` | [ProgressBar Component](progress-bar-component.md) (animated, with phase) |
| `completed` | Visualization preview, reader CTA for highlight/lip-sync jobs when available or pending verification, partial lip-sync notice when applicable, otherwise output path + download link |
| `failed` | Error message |

---

## API Calls

- `getJob(id)` from [Jobs API](jobs-api.md) — initial fetch + on completion
- `deleteJob(id)` from [Jobs API](jobs-api.md) — on delete confirmation
- `getDownloadUrl(id)` from [Jobs API](jobs-api.md) — download link
- `getReaderStatus(id)` from [Reader API](reader-api.md) — checks browser reader availability for completed highlight/lip-sync jobs
- [useJobProgress Hook](use-job-progress-hook.md) — SSE real-time updates

---

## Components Used

- [ProgressBar Component](progress-bar-component.md) — Progress display
- [LipsyncRunPanel](lipsync-run-panel.md) — Per-page lip-sync progress and early stop

---

## See Also

- [useJobProgress Hook](use-job-progress-hook.md) — SSE connection
- [Events Router](../backend/events-router.md) — Backend SSE endpoint
- [Dashboard Page](dashboard-page.md) — Back navigation
- [Reader Page](reader-page.md) — Full-screen browser reader destination
