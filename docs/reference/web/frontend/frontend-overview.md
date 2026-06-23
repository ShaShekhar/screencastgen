# Frontend Overview

> React + TypeScript + Tailwind single-page application.

**Source:** [`web/frontend/src/`](https://github.com/ShaShekhar/screencastgen/tree/main/web/frontend/src/)

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| React 18 | UI framework |
| TypeScript | Type safety |
| React Router | Client-side routing |
| Axios | HTTP client |
| Tailwind CSS | Styling |
| Vite | Build tool + dev server |

---

## Routing (App.tsx)

| Path | Page | Description |
|------|------|-------------|
| `/` | [Dashboard Page](dashboard-page.md) | Job list with filtering |
| `/jobs/new` | [NewJob Page](new-job-page.md) | Upload + configure + submit |
| `/jobs/:id` | [JobDetail Page](job-detail-page.md) | Live progress + download |
| `/jobs/:id/read` | [Reader Page](reader-page.md) | Full-screen browser reader for completed highlight/lip-sync jobs |

`/`, `/jobs/new`, and `/jobs/:id` are wrapped in a `Layout` component ([Navbar](navbar.md) + content area).
`/jobs/:id/read` renders outside that layout as a dedicated full-screen reading view.

---

## Architecture

```
┌────────────────────────────────────────────┐
│                  Pages                     │
│  Dashboard Page NewJob Page JobDetail Page Reader Page│
├────────────────────────────────────────────┤
│              Components                    │
│  FileUploader VoiceSettings           │
│  LipsyncSettings LipsyncPreviewFrame  │
│  LipsyncRunPanel VideoSettings        │
│  PipelineSelector ProgressBar Component│
│  JobCard Navbar                       │
├────────────────────────────────────────────┤
│           Hooks                            │
│  useJobProgress Hook                     │
├────────────────────────────────────────────┤
│           API Client Layer                 │
│  API Client Jobs API Uploads API    │
│  Voices API Reader API                 │
├────────────────────────────────────────────┤
│           Types                            │
│  types/index.ts                            │
└────────────────────────────────────────────┘
```

---

## Key Data Flows

### Job Creation
```
NewJob Page
    ├── FileUploader → Uploads API → POST /api/uploads
    ├── PipelineSelector (lipsync by default, highlight, or visualization)
    ├── VoiceSettings / LipsyncSettings → config
    ├── VideoSettings → config
    └── Submit → Jobs API → POST /api/jobs
         └── navigate to /jobs/:id
```

### Real-Time Progress
```
JobDetail Page
    └── useJobProgress Hook
         └── EventSource → GET /api/jobs/:id/events (SSE)
              ├── updates ProgressBar Component
              └── updates LipsyncRunPanel page timings
```

For active lip-sync jobs, [LipsyncRunPanel](lipsync-run-panel.md) requires a second confirmation
before [Jobs API](jobs-api.md).stopJob() sends the stop request. Cancelling the confirmation
keeps the job running.

### Browser Reader
```
JobDetail Page
    └── Reader API.getReaderStatus()
         └── navigate to /jobs/:id/read
              └── Reader Page
                   ├── Reader API.getReaderManifest()
                   ├── Reader API.getReaderAudioUrl()
                   ├── Reader API.getReaderPresenterUrl()
                   ├── Reader API.getReaderPageUrl()
                   ├── Jobs API offline-reader download
                   └── Jobs API MP4 and EPUB export helpers
```

### Job Listing
```
Dashboard Page
    └── Jobs API.listJobs() (every 5s)
         └── renders JobCard grid
```

---

## See Also

- [Web Overview](../../../concepts/web-architecture.md) — Full-stack architecture
- [FastAPI App](../backend/fast-api-app.md) — Backend API
- [Schemas](../backend/schemas.md) — API data shapes
