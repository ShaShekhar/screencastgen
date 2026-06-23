# Highlight Renderer

> PIL-based word-highlighted text frame renderer (plain-background fallback).

**Source:** [`screencastgen/highlight_renderer.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/highlight_renderer.py)

---

## Overview

Renders individual video frames showing text with the currently-spoken word highlighted on a plain dark background. Uses PIL/Pillow for drawing with system fonts and handles word wrapping, scrolling, and per-word color highlighting.

This is the **fallback renderer** used when the input is not a PDF or PyMuPDF is not installed. For PDF inputs, [Page Renderer](page-renderer.md) is preferred — it highlights words on the actual PDF page images.

---

## Class: `HighlightRenderer`

### Constructor
```python
HighlightRenderer(width=1280, height=720, font_size=32)
```

### Methods

| Method | Description |
|--------|-------------|
| `layout_words(words) -> List[dict]` | Computes pixel positions for each word. Accepts `List[str]` or `List[WordTiming]`. |
| `render_frame(layout, active_index, scroll_offset) -> Image` | Renders a single frame with the active word highlighted |
| `compute_scroll_offset(layout, active_index) -> int` | Calculates vertical scroll position to keep active word visible |
| `get_active_word_index(words, time) -> Optional[int]` | Finds which word is active at a given timestamp |

### Rendering Details

- **Font:** System sans-serif (DejaVu Sans, Liberation Sans, etc.)
- **Background:** Dark gray (30, 30, 30)
- **Text:** White (255, 255, 255)
- **Highlight:** Yellow background (255, 255, 0) on active word
- **Scrolling:** Auto-scrolls to keep the active word in the viewport
- **Word wrapping:** Breaks lines at word boundaries based on frame width

---

## Dependencies

```
Highlight Renderer
├── Pillow (PIL)     (deferred import)
├── Types         (WordTiming for timing data)
└──▶ consumed by Highlight Pipeline
     └──▶ consumed by Video Composer
```

---

## Data Flow

```
List[WordTiming]
    │
    ▼  layout_words()
List[dict] positions (x, y per word)
    │
    ▼  render_frame() (called per video frame)
PIL Image
    │
    ▼  passed to Video Composer
```

`layout_words()` also accepts `List[str]`, but the current video pipeline passes `AlignedChunk.words` directly so both renderers share the same interface.

---

## See Also

- [Page Renderer](page-renderer.md) — PDF page-image renderer (preferred for PDF inputs)
- [Video Composer](video-composer.md) — Assembles frames into video with audio
- [Types](types.md) — `WordTiming` dataclass
- [Highlight Pipeline](../pipelines/highlight-pipeline.md) — Pipeline that creates the renderer
- [Constants](constants.md) — `DEFAULT_VIDEO_WIDTH`, `DEFAULT_VIDEO_HEIGHT`, `DEFAULT_VIDEO_FPS`
