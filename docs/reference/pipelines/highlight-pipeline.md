# Highlight Pipeline

> Audio + word-level alignment → highlighted-text video/EPUB plus browser-reader assets.

**Source:** [`screencastgen/pipelines/highlight.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/pipelines/highlight.py)

---

## Functions

### `run_highlight_pipeline(request, reporter, backend_factory) -> PipelineRunResult`
Main pipeline runner. Produces either an MP4 video or EPUB3 with Media Overlays, then best-effort browser-reader assets.

### `parse_resolution(res_str) -> Tuple[int, int]`
Parses resolution strings like `"1280x720"` into `(width, height)`.

### `build_highlight_epub(request, aligned_chunks, tracker, reporter) -> PipelineRunResult`
Assembles an EPUB3 file with word-level audio synchronization via [EPUB Builder](../core/epub-builder.md).

### `build_highlight_mp4(request, aligned_chunks, pdf_words, reporter) -> PipelineRunResult`
Renders a highlighted MP4 video. When `pdf_words` is available (PDF input with PyMuPDF), uses [Word Matcher](../core/word-matcher.md) + [Page Renderer](../core/page-renderer.md) to highlight on actual PDF pages. The PDF page path now relies on visually sorted PyMuPDF word extraction and oversampled page rasterisation for better match stability and sharper output. Otherwise falls back to [Highlight Renderer](../core/highlight-renderer.md) (plain text on dark background).

---

## Steps

```
1. Create TTS backend            ← TTS Registry
2. Extract and chunk             ← Pipeline Common
   ├── EPUB: page-aware chunking
   └── MP4: standard chunking + extract word bboxes  ← Extractor (PyMuPDF)
3. Validate and synthesize       ← Pipeline Common
4. Align chunks                  ← Pipeline Common → Aligner or Remote GPU Client
5. Build output:
   ├── MP4 (PDF input):  Word Matcher → Page Renderer → Video Composer
   ├── MP4 (other input): Highlight Renderer → Video Composer
   └── EPUB: EPUB Builder
6. Build reader assets             ← Reader Assets
```

---

## Configuration

Key fields from [HighlightPipelineRequest](pipeline-types.md):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | `str` | `"epub"` | Output format (`mp4` or `epub`) |
| `font_size` | `int` | 32 | Text font size |
| `resolution` | `str` | `"1280x720"` | Video resolution |
| `fps` | `int` | 24 | Frames per second |

Inherits all fields from [TTSRequest](pipeline-types.md) (backend, device, voice, etc.)

---

## Dependencies

```
Highlight Pipeline
├── Pipeline Common        (extract, chunk, validate, synthesize, align, bbox extraction)
├── Pipeline Types         (HighlightPipelineRequest, PipelineRunResult)
├── Page Renderer          (PDF page-image rendering, preferred for PDFs)
├── Highlight Renderer     (plain-text fallback renderer)
├── Word Matcher           (maps aligned words to PDF bboxes)
├── Video Composer         (compose_highlight_video)
├── EPUB Builder           (EPUB3 assembly)
├── Reader Assets          (browser reader manifest/audio/page images)
├── Constants              (video defaults)
└── TTS Registry           (create backend)
```

---

## See Also

- [Audio Pipeline](audio-pipeline.md) — Simpler pipeline (no alignment/video)
- [Lipsync Pipeline](lipsync-pipeline.md) — Extends this with face animation
- [Data Flow](../../concepts/data-flow.md) — Highlight pipeline flow diagram
