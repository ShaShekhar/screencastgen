# ProgressBar Component

> Phase label + percentage progress bar with status coloring.

**Source:** [`web/frontend/src/components/ProgressBar.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/components/ProgressBar.tsx)

---

## Props

```typescript
{
  current: number      // Progress numerator
  total: number        // Progress denominator
  phase: string        // Current phase label
  status: JobStatus    // Job status for coloring
}
```

---

## Behavior

- Displays phase name and percentage (e.g., "Synthesis — 45%")
- Percentage: `(current / total) * 100`

### Status Colors

| Status | Color | Animation |
|--------|-------|-----------|
| `running` | Indigo | Pulse |
| `pending` | Indigo | Pulse |
| `completed` | Green | None |
| `failed` | Red | None |

---

## Used By

- [JobDetail Page](job-detail-page.md) — Main progress display
- [JobCard](job-card.md) — Inline progress for running jobs

---

## See Also

- [useJobProgress Hook](use-job-progress-hook.md) — Provides the progress data
- [Pipeline Events](../../pipelines/pipeline-events.md) — Source of progress events
