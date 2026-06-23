# VideoSettings

> Resolution, FPS, and font size configuration.

**Source:** [`web/frontend/src/components/VideoSettings.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/components/VideoSettings.tsx)

---

## Props

```typescript
{
  config: { font_size: number, width: number, height: number, fps: number }
  onChange: (config: VideoConfig) => void
}
```

---

## Controls

| Control | Type | Range | Default |
|---------|------|-------|---------|
| Resolution | select | 854x480, 1280x720, 1920x1080 | 1280x720 |
| FPS | slider | 1 – 60 | 24 |
| Font size | slider | 12 – 72 | 32 |

---

## Used By

- [NewJob Page](new-job-page.md) — Lip-sync pipeline settings

---

## See Also

- [Constants](../../core/constants.md) — Default video values
- [Highlight Renderer](../../core/highlight-renderer.md) — Uses these settings for rendering
