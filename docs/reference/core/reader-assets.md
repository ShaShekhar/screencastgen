# Reader Assets

> Builds the browser-reader bundle consumed by the React reader.

**Source:** [`screencastgen/reader_assets.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/reader_assets.py)

---

## Overview

`build_reader_assets()` converts aligned chunks into the hosted assets consumed
by the React reader. The [Offline Reader](offline-reader.md) packages these same
assets into the self-contained downloadable ZIP.

| File | Purpose |
|------|---------|
| `reader_manifest.json` | Metadata, global word timings, chunk text, page mapping, and optional presenter filename |
| `reader_audio.mp3` | Concatenated chunk audio used by highlight-only reader output |
| `presenter.mp4` | Optional lip-sync presenter video built by [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) |
| `pages/page-0001.jpg` | Optional rendered PDF page images for the active-page side panel |

All word timings in the manifest are global timestamps relative to the concatenated audio/presenter timeline.

---

## Functions

### `build_reader_assets(aligned_chunks, output_dir, pdf_path, title, language, presenter) -> str | None`

1. Concatenates chunk audio into `reader_audio.mp3`.
2. Computes per-chunk offsets.
3. Renders PDF page images when page numbers are available and the source is a PDF.
4. Writes `reader_manifest.json`.
5. Returns the manifest path, or `None` if no chunks were available.

### `reader_asset_names(page_files=None, presenter=False) -> list[str]`

Returns relative paths for manifest/audio/presenter/page files so storage upload helpers can mirror the full bundle.

---

## Manifest Shape

```json
{
  "version": 1,
  "title": "Book title",
  "language": "en-US",
  "source_type": "pdf",
  "duration": 123.456,
  "audio": "reader_audio.mp3",
  "presenter": "presenter.mp4",
  "pages": {
    "dir": "pages",
    "image_width": 1400,
    "files": {"1": "page-0001.jpg"}
  },
  "chunks": [
    {
      "chunk_num": 1,
      "text": "...",
      "offset": 0.0,
      "pages": [1],
      "words": [{"word": "Hello", "start": 0.12, "end": 0.4}]
    }
  ]
}
```

---

## Dependencies

```
Reader Assets
├── Types             (AlignedChunk)
├── Extractor         (render_page_image_with_zoom for PDFs)
└── pydub / ffprobe      (duration and MP3 concatenation)
```

---

## See Also

- [Reader Page](../web/frontend/reader-page.md) — Frontend consumer
- [Reader Router](../web/backend/reader-router.md) — Backend asset serving
- [Offline Reader](offline-reader.md) — Standalone ZIP packaging
- [Highlight Pipeline](../pipelines/highlight-pipeline.md) — Builds reader assets for highlight outputs
- [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) — Adds `presenter.mp4`
