# Page Renderer

> Renders actual PDF pages with per-word highlighting at real bounding-box positions.

**Source:** [`screencastgen/page_renderer.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/page_renderer.py)

---

## Overview

Renders video frames showing the actual PDF page with a semi-transparent highlight rectangle over the currently-spoken word. This is the **preferred renderer** for PDF inputs — it preserves the original document layout, formatting, images, and structure.

For non-PDF inputs (TXT, EPUB) or when PyMuPDF is not installed, the pipeline falls back to [Highlight Renderer](highlight-renderer.md) which re-renders extracted text on a plain dark background.

---

## Class: `PageRenderer`

### Constructor
```python
PageRenderer(
    pdf_path: str,
    width: int = 1280,
    height: int = 720,
    highlight_color: Tuple[int, int, int, int] = (255, 255, 0, 100),  # RGBA
    bg_color: Tuple[int, int, int] = (30, 30, 30),
)
```

### Methods

| Method | Description |
|--------|-------------|
| `layout_words(words) -> List[dict]` | Builds layout dicts from `WordTiming` bbox data. Each entry includes `page`, `x`, `y`, `width`, `height` in video-pixel coordinates. |
| `render_frame(layout, active_index, scroll_offset) -> Image` | Renders the PDF page for the active word's page, draws a semi-transparent highlight at the word's bbox. |
| `compute_scroll_offset(layout, active_index) -> int` | Returns 0 — pages are pre-scaled to fit the frame. |
| `get_active_word_index(words, time) -> Optional[int]` | Same logic as [Highlight Renderer](highlight-renderer.md): finds which word is active at a given timestamp. |

### Page Image Caching

Page images are cached in `_page_cache` and keyed by `(page_num, width, height)`. This matters because the lipsync compositor temporarily changes renderer width for split-screen layouts. Each cache entry stores:
- The scaled and centered PIL Image (letterboxed on a dark background)
- The combined point scale (`render zoom * fit-to-frame scale`)
- The x/y offsets for centering

Pages are rasterised at an oversampled target width (`frame width * 2`) before being fit into the video frame. That keeps page text sharper than rendering at native PDF point resolution and then enlarging.

### Coordinate Transform

For a US Letter PDF (612x792 points) in a 1280x720 video frame:
- Render zoom: chosen from `target_width / page_width`
- Fit scale: `min(frame_width/raw_width, frame_height/raw_height)`
- Point scale: `render_zoom * fit_scale`
- Word bbox transform: `video_x = bbox.x0 * point_scale + x_offset`

---

## Renderer Interface Contract

Both `PageRenderer` and [Highlight Renderer](highlight-renderer.md) expose the same 4 methods that [Video Composer](video-composer.md) calls. The compositor is renderer-agnostic:

```
layout_words(words) -> List[dict]
render_frame(layout, active_index, scroll_offset) -> PIL.Image
get_active_word_index(words, time) -> Optional[int]
compute_scroll_offset(layout, active_index) -> int
```

Plus `width` and `height` attributes for frame dimensions.

---

## Dependencies

```
Page Renderer
├── Pillow (PIL)        (image compositing)
├── Extractor        (render_page_image_with_zoom — deferred PyMuPDF call)
├── Types            (WordTiming, BBox)
└──▶ consumed by Highlight Pipeline
     └──▶ consumed by Lipsync Pipeline
          └──▶ via Video Composer
```

---

## Data Flow

```
PDF path + List[WordTiming] (with bbox populated by Word Matcher)
    |
    +--> layout_words() --> layout dicts with video-pixel coordinates
    |
    +--> render_frame(layout, active_idx) per video frame:
         |
         +--> _get_page(page_num) --> cached page image
         |    (oversampled via Extractor.render_page_image_with_zoom)
         |
         +--> draw highlight rectangle at active word's bbox
         |
         +--> return PIL Image
```

---

## See Also

- [Highlight Renderer](highlight-renderer.md) — Plain-text fallback renderer
- [Word Matcher](word-matcher.md) — Populates bbox fields on WordTiming objects
- [Video Composer](video-composer.md) — Calls renderer to produce video frames
- [Extractor](extractor.md) — `render_page_image_with_zoom()` and `extract_words_with_bboxes()`
- [Types](types.md) — `BBox`, `WordTiming` dataclasses
