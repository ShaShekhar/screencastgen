# useJobProgress Hook

> Real-time job progress tracking via Server-Sent Events.

**Source:** [`web/frontend/src/hooks/useJobProgress.ts`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/hooks/useJobProgress.ts)

---

## Signature

```typescript
useJobProgress(jobId: string | undefined, enabled: boolean): ProgressEvent | null
```

**Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `jobId` | `string \| undefined` | Job to track |
| `enabled` | `boolean` | Whether to open the SSE connection |

**Returns:** Current `ProgressEvent` or `null`

---

## Behavior

1. When `enabled` is true and `jobId` is set, opens an `EventSource` to `/api/jobs/{jobId}/events`
2. Listens for `progress` events — parses JSON and updates state
3. Listens for `done` events — final update, then closes connection
4. Closes on error
5. Cleans up connection on unmount or when disabled

---

## Event Types

| SSE Event | Action |
|-----------|--------|
| `progress` | Update `ProgressEvent` state |
| `done` | Update state + close connection |
| `error` | Close connection |

---

## ProgressEvent Shape

```typescript
{
  job_id: string
  status: string
  phase: string
  current: number
  total: number
  message: string
  data?: {
    event: "page_start" | "page_progress" | "page_done"
    page: number
    completed: number
    total: number
    elapsed?: number
    seconds?: number
    page_times?: Array<{ page: number; seconds: number }>
  } | null
}
```

---

## Consumer

Used by [JobDetail Page](job-detail-page.md) to show real-time progress.

---

## Backend

Connects to [Events Router](../backend/events-router.md) SSE endpoint.

---

## See Also

- [Events Router](../backend/events-router.md) — SSE server endpoint
- [Progress Reporter](../backend/progress-reporter.md) — Publishes events to Redis
- [JobDetail Page](job-detail-page.md) — Uses this hook
- [ProgressBar Component](progress-bar-component.md) — Displays the progress
