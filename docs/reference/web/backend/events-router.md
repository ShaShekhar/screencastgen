# Events Router

> Server-Sent Events (SSE) stream for real-time job progress.

**Source:** [`web/backend/routers/events.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/routers/events.py)

---

## Endpoint

### `GET /api/jobs/{job_id}/events`
Opens an SSE connection that streams progress events for a job.

**Event types:**

| Event | Data | Description |
|-------|------|-------------|
| `progress` | `ProgressEvent` JSON ([Schemas](schemas.md)) | Periodic progress update |
| `done` | ProgressEvent JSON | Terminal status (closes connection) |
| `ping` | `""` | Keepalive (every ~15s) |

**Process:**
1. Subscribe to Redis pubsub channel `job:{job_id}:progress`
2. Yield progress events as SSE
3. On terminal status (`completed` or `failed`), yield `done` event and close
4. Send periodic pings to keep connection alive

**Connection lifecycle:**
```
Browser opens SSE
    │
    ├── receives: event: progress, data: {...}
    ├── receives: event: progress, data: {...}
    ├── receives: event: ping
    ├── receives: event: progress, data: {...}
    └── receives: event: done, data: {...}
         └── connection closed
```

---

## Dependencies

```
Events Router
├── sse-starlette      (SSE response)
├── Redis              (pubsub subscription)
├── Web Config      (REDIS_URL)
└──▶ fed by Progress Reporter (publishes to Redis)
```

---

## See Also

- [Progress Reporter](progress-reporter.md) — Publishes events to Redis pubsub
- [Pipeline Events](../../pipelines/pipeline-events.md) — Source of structured events
- [useJobProgress Hook](../frontend/use-job-progress-hook.md) — Frontend SSE consumer
- [JobDetail Page](../frontend/job-detail-page.md) — Displays real-time progress
