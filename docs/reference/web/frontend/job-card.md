# JobCard

> Clickable job summary card for the dashboard grid.

**Source:** [`web/frontend/src/components/JobCard.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/components/JobCard.tsx)

---

## Props

```typescript
{
  job: Job
}
```

---

## Displays

- Pipeline type badge
- Status badge (colored)
- Job ID (first 8 characters)
- Progress bar (if running) via [ProgressBar Component](progress-bar-component.md)
- Creation date

Links to `/jobs/{id}` → [JobDetail Page](job-detail-page.md)

---

## Styling

- Hover shadow effect
- Rounded card with padding
- Status-colored badge

---

## Used By

- [Dashboard Page](dashboard-page.md) — Grid of job cards

---

## See Also

- [Dashboard Page](dashboard-page.md) — Parent page
- [JobDetail Page](job-detail-page.md) — Navigation target
- [ProgressBar Component](progress-bar-component.md) — Inline progress
