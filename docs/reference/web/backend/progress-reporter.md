# Progress Reporter

> Database + Redis pubsub progress bridge for web jobs.

**Source:** [`web/backend/tasks/progress.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/tasks/progress.py)

---

## Overview

`JobProgressReporter` subscribes to [PipelineEvent](../../pipelines/pipeline-events.md) callbacks and bridges them to:
1. **Database** — Updates the Job record with current progress
2. **Redis pubsub** — Publishes events to `job:{id}:progress` channel
3. **Cancellation** — Checks and clears a Redis stop flag for long-running jobs

The [Events Router](events-router.md) subscribes to the same Redis channel and streams events to the browser via SSE.

---

## Class: `JobProgressReporter`

### Constructor
```python
JobProgressReporter(job_id: str, db_session)
```

### Behavior

On each `PipelineEvent`:
1. Update [Job](db-models.md) record:
   - `progress_current`
   - `progress_total`
   - `progress_phase`
   - `lipsync_progress` in `config_json` when a `page_done` event includes per-page timing
2. Publish [ProgressEvent](schemas.md) JSON to Redis pubsub channel `job:{job_id}:progress`

On terminal events (completed/failed):
- Publish final event with terminal status
- The [Events Router](events-router.md) will close the SSE connection

### Cancellation

| Method | Behavior |
|--------|----------|
| `is_cancelled()` | Reads `job:{job_id}:cancel` from Redis |
| `clear_cancel()` | Deletes stale stop flags after a task exits |
| `publish_terminal()` | Emits a final progress event using the same DB/Redis path |

---

## Event Flow

```
Pipeline Runner
    │ emits PipelineEvent
    ▼
JobProgressReporter
    ├── UPDATE Job SET progress_current=..., progress_phase=...
    └── PUBLISH job:{id}:progress → Redis
                                      │
                                      ▼
                              Events Router
                                      │ SSE
                                      ▼
                                   Browser
                              useJobProgress Hook
```

---

## Dependencies

```
Progress Reporter
├── Redis               (pubsub publish)
├── Web Database     (sync session)
├── DB Models        (Job)
├── Schemas          (ProgressEvent)
├── Pipeline Events  (PipelineEvent callback)
└──▶ consumed by Pipeline Tasks
```

---

## See Also

- [Pipeline Events](../../pipelines/pipeline-events.md) — Source of events
- [Events Router](events-router.md) — SSE delivery to browser
- [Pipeline Tasks](pipeline-tasks.md) — Creates and uses this reporter
- [useJobProgress Hook](../frontend/use-job-progress-hook.md) — Frontend SSE consumer
