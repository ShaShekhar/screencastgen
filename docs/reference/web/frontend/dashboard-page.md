# Dashboard Page

> Job list with status filtering and auto-refresh.

**Source:** [`web/frontend/src/pages/Dashboard.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/pages/Dashboard.tsx)
**Route:** `/`

---

## Features

- **Status filters:** All, Running, Completed, Failed
- **Auto-refresh:** Fetches job list every 5 seconds
- **Job count:** Shows total matching jobs
- **Empty state:** "Create your first job" CTA linking to [NewJob Page](new-job-page.md)
- **Grid layout:** Renders [JobCard](job-card.md) components

---

## State

| State | Type | Description |
|-------|------|-------------|
| `jobs` | `Job[]` | Current job list |
| `total` | `number` | Total matching count |
| `filter` | `string \| undefined` | Active status filter |
| `loading` | `boolean` | Fetch in progress |

---

## API Calls

- `listJobs(filter)` from [Jobs API](jobs-api.md) — called on mount and every 5 seconds

---

## Components Used

- [JobCard](job-card.md) — Renders each job as a clickable card
- [Navbar](navbar.md) — Via Layout wrapper

---

## See Also

- [Jobs API](jobs-api.md) — API client
- [JobCard](job-card.md) — Job summary component
- [NewJob Page](new-job-page.md) — Create new job
- [JobDetail Page](job-detail-page.md) — View job details
