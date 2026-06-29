# PipelineSelector

> Pipeline type chooser, prioritizing the full LipSync Reader workflow.

**Source:** [`web/frontend/src/components/PipelineSelector.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/components/PipelineSelector.tsx)

---

## Props

```typescript
{
  selected: PipelineType
  onChange: (type: PipelineType) => void
}
```

---

## Options

| Value | Label | Description |
|-------|-------|-------------|
| `lipsync` | LipSync Reader | Synchronized document, narration, and lip-synced presenter |
| `highlight` | Read-Along EPUB | Secondary accessibility export with synchronized text and narration |
| `visualization` | Concept Visualization | Prompt-driven math animation rendered as a standalone MP4 |

---

## Used By

- [NewJob Page](new-job-page.md)

---

## See Also

- [Pipeline Overview](../../../concepts/pipelines.md) — Pipeline design
- [Highlight Pipeline](../../pipelines/highlight-pipeline.md) — What highlight produces
- [Lipsync Pipeline](../../pipelines/lipsync-pipeline.md) — What lipsync produces
- [Visualization Pipeline](../../pipelines/visualization-pipeline.md) — What visualization produces
