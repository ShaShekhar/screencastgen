# EPUB Builder

> Assembles EPUB3 packages with Media Overlays for word-level audio synchronization.

**Source:** [`screencastgen/epub_builder.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/epub_builder.py)

---

## Overview

Generates standards-compliant EPUB3 files with Media Overlays (SMIL). Each word in the text is individually timed to the audio, enabling reading systems to highlight words as they are spoken.

---

## Class: `EPUBBuilder`

### Constructor
```python
EPUBBuilder(title: str, language: str = "en-US")
```

### Methods

| Method | Description |
|--------|-------------|
| `add_chapter(chapter_num, aligned_chunks, lipsync_video_path=None)` | Add a chapter with audio-synced text (and optional video) |
| `build(output_path) -> str` | Assemble and write the EPUB file |

### Internal Methods

| Method | Description |
|--------|-------------|
| `_build_xhtml(ch, video_name) -> str` | Generate chapter XHTML with `<span>` per word |
| `_build_smil(ch, audio_map) -> Tuple[str, float]` | Generate SMIL Media Overlay with word-level `<par>` elements |
| `_build_toc() -> str` | Generate navigation document (table of contents) |
| `_build_opf(manifest_items, spine_items, total_duration, chapter_durations) -> str` | Generate OPF package document |

### EPUB3 Standards

- Uses `-epub-media-overlay-active` CSS class for active word highlighting
- SMIL files contain `<par>` elements with `<text src="...#word_id"/>` and `<audio src="..." clipBegin="..." clipEnd="..."/>`
- OPF includes `media:duration` metadata for each chapter and total

---

## Dependencies

```
EPUB Builder
├── zipfile (stdlib)
├── Types         (AlignedChunk, WordTiming)
└──▶ consumed by Highlight Pipeline
     └──▶ consumed by Lipsync Pipeline
```

---

## Output Structure

```
output.epub (ZIP)
├── mimetype
├── META-INF/
│   └── container.xml
├── OEBPS/
│   ├── content.opf
│   ├── toc.xhtml
│   ├── style.css
│   ├── chapters/
│   │   ├── chapter_001.xhtml
│   │   ├── chapter_001.smil
│   │   └── ...
│   └── audio/
│       ├── audio_chunk_0001.mp3
│       └── ...
```

---

## See Also

- [Highlight Pipeline](../pipelines/highlight-pipeline.md) — `build_highlight_epub()` function
- [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) — `build_lipsync_epub()` function
- [Types](types.md) — `AlignedChunk`, `WordTiming`
