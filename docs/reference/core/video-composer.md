# Video Composer

> MoviePy-based video assembly for highlight and lipsync outputs.

**Source:** [`screencastgen/video_composer.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/video_composer.py)

---

## Functions

### `compose_highlight_video(aligned_chunks, renderer, output_path, fps) -> str`
Composes a video with synchronized word-highlighted text and audio.

**Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `aligned_chunks` | `List[AlignedChunk]` | Chunks with word timings |
| `renderer` | `HighlightRenderer` or `PageRenderer` | Frame renderer |
| `output_path` | `str` | Output MP4 path |
| `fps` | `int` | Frames per second |

For each frame, determines the active word from the timeline and renders the highlighted frame. The renderer is polymorphic — when a [Page Renderer](page-renderer.md) is passed, frames show actual PDF pages; when a [Highlight Renderer](highlight-renderer.md) is passed, frames show plain text on a dark background.

The composer now passes `AlignedChunk.words` directly into `renderer.layout_words()`, so both renderers work from the same `WordTiming` objects. This lets [Page Renderer](page-renderer.md) consume matched bbox data without a separate text-only conversion step.

### `compose_lipsync_video(aligned_chunks, lipsync_clips, renderer, output_path, fps, face_position, face_scale) -> str`
Composes a video with highlighted text **and** a lip-synced face presenter.

**Additional Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `lipsync_clips` | `List[str]` | Paths to per-chunk lip-sync videos |
| `face_position` | `str` | Presenter position (see below) |
| `face_scale` | `float` | Face scale for docked corner layouts (0.12–0.4) |

**Face positions:** `left`, `right`, `center`, `top-left`, `top-right`, `bottom-left`, `bottom-right`

For corner positions, the face is docked into a side rail and the text/PDF page is rendered in the remaining reading pane. This keeps the presenter visible without covering highlighted text.

---

## Dependencies

```
Video Composer
├── moviepy         (deferred import)
├── Types        (AlignedChunk, WordTiming)
├── Highlight Renderer (plain-text frame rendering, fallback)
├── Page Renderer      (PDF page-image frame rendering, preferred)
└──▶ consumed by Highlight Pipeline
     └──▶ consumed by Lipsync Pipeline
```

---

## See Also

- [Highlight Renderer](highlight-renderer.md) — Plain-text frame renderer (fallback)
- [Page Renderer](page-renderer.md) — PDF page-image frame renderer (preferred for PDFs)
- [Highlight Pipeline](../pipelines/highlight-pipeline.md) — Calls `compose_highlight_video()`
- [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) — Calls `compose_lipsync_video()`
- [Types](types.md) — `AlignedChunk` dataclass
