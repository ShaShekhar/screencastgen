# LipsyncRunPanel

> Running lip-sync progress panel with per-page timing and early stop control.

**Source:** [`web/frontend/src/components/LipsyncRunPanel.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/components/LipsyncRunPanel.tsx)

---

## Props

```typescript
{
  jobId: string
  progress: ProgressEvent | null
  initialPageTimes?: LipsyncPageTime[]
}
```

---

## Behavior

- Reads structured `progress.data` from lip-sync page events.
- Displays completed page timings from `page_done` events.
- Shows a ticking elapsed timer while the current page is on the GPU.
- Recovers current-page state from `page_progress` if `page_start` was missed.
- Uses a two-step stop flow to prevent an accidental click from cancelling a long run:
  1. **Stop & build from completed pages** opens an inline warning.
  2. **Yes, stop and build** calls `stopJob(jobId)`; **Keep running** closes the warning without changing the job.
- The warning states that the active page may be discarded and the final video contains only completed pages.
- Disables both confirmation actions while the stop request is being sent and displays a retryable error if the API call fails.

`initialPageTimes` lets the panel show persisted progress after a browser reload.

## Local State

| State | Purpose |
|-------|---------|
| `pageTimes` | Completed page durations |
| `currentPage` / `pageStartRef` | Active-page timer |
| `showStopConfirm` | Whether the inline confirmation is visible |
| `stopping` | Prevents duplicate stop requests |
| `stopError` | User-facing API failure message |

---

## Used By

- [JobDetail Page](job-detail-page.md) — Running lip-sync jobs

---

## See Also

- [Progress Reporter](../backend/progress-reporter.md) — Persists `lipsync_progress`
- [Jobs API](jobs-api.md) — `stopJob()`
- [Lipsync Pipeline](../../pipelines/lipsync-pipeline.md) — Emits page events and builds partial reader outputs
