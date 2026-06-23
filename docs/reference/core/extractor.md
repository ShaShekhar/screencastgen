# Extractor

> Reads PDF, TXT, and EPUB files into plain text. Also provides PyMuPDF-based word bounding-box extraction and page rasterisation for the page-image rendering pipeline.

**Source:** [`screencastgen/extractor.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/extractor.py)

---

## Text Extraction Functions (PyPDF2)

### `extract_text(path: str) -> str`
Reads a document and returns its full text content as a single string. Dispatches based on file extension:
- `.pdf` → PyPDF2 page extraction
- `.txt` → UTF-8 file read
- `.epub` → ebooklib HTML stripping

### `extract_text_by_page(path: str) -> List[Tuple[int, str]]`
Returns `(page_number, text)` pairs. Used by the [Highlight Pipeline](../pipelines/highlight-pipeline.md) and [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) when generating EPUB output with page-aware chunking.

---

## Page-Image Functions (PyMuPDF, deferred import)

These functions use PyMuPDF (`fitz`) and are only imported when called. They power the page-image rendering pipeline where words are highlighted on the actual PDF pages.

### `extract_words_with_bboxes(path: str) -> List[PDFWordInfo]`
Extracts every word from a PDF with its bounding box (x0, y0, x1, y1 in PDF points) and 1-indexed page number. Uses `fitz.page.get_text("words", sort=True)` so the result follows visual reading order, which the sequential [Word Matcher](word-matcher.md) depends on. Returns a flat list in reading order.

Consumed by: [Pipeline Common](../pipelines/pipeline-common.md) (`extract_words_with_bboxes_safe`) → [Word Matcher](word-matcher.md)

### `render_page_image(path: str, page_num: int, target_width: Optional[int]) -> PIL.Image`
Rasterises a single PDF page (1-indexed) to a Pillow RGB image. When `target_width` is given, scales proportionally. Uses `fitz.page.get_pixmap()`.

### `render_page_image_with_zoom(path: str, page_num: int, target_width: Optional[int]) -> Tuple[PIL.Image, float]`
Same rasterisation logic as `render_page_image()`, but also returns the zoom factor used during rendering. [Page Renderer](page-renderer.md) uses this to convert PDF-point bounding boxes into final video-pixel coordinates accurately when oversampling pages for sharper output.

Consumed by: [Page Renderer](page-renderer.md) (cached per page)

### `get_page_count(path: str) -> int`
Returns the number of pages in a PDF.

---

## Supported Formats

| Extension | Library | Text | Bounding Boxes | Page Images |
|-----------|---------|------|----------------|-------------|
| `.pdf` | PyPDF2 | Yes | No | No |
| `.pdf` | PyMuPDF | — | Yes | Yes |
| `.txt` | stdlib | Yes | — | — |
| `.epub` | ebooklib | Yes | — | — |

---

## Dependencies

```
Extractor
├── PyPDF2          (PDF text extraction)
├── ebooklib        (EPUB parsing, deferred import)
├── pymupdf (fitz)  (word bboxes + page rendering, deferred import)
├── Pillow (PIL)    (page-image return type, deferred import)
└──▶ consumed by Pipeline Common
     └──▶ consumed by Word Matcher, Page Renderer
```

---

## Data Flow

```
Document file
    │
    ├──▶ extract_text() or extract_text_by_page()     [PyPDF2]
    │    → Raw text string(s) → Text Processing
    │
    ├──▶ extract_words_with_bboxes()                   [PyMuPDF]
    │    → List[PDFWordInfo] → Word Matcher
    │
    └──▶ render_page_image() / render_page_image_with_zoom()   [PyMuPDF]
         → PIL Image (+ zoom) → Page Renderer
```

---

## See Also

- [Text Processing](text-processing.md) — Next step: preprocessing and chunking
- [Pipeline Common](../pipelines/pipeline-common.md) — Calls extractor functions
- [Word Matcher](word-matcher.md) — Maps aligned words to PDF bounding boxes
- [Page Renderer](page-renderer.md) — Renders PDF pages with word highlighting
- [Data Flow](../../concepts/data-flow.md) — Full pipeline data flow
