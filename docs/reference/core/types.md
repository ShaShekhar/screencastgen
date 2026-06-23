# Types

> Core data structures and the `TTSBackend` protocol.

**Source:** [`screencastgen/types.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/types.py)

---

## Protocol

### `TTSBackend`
The protocol that all TTS backends must implement. Defined as a `typing.Protocol`.

| Member | Type | Description |
|--------|------|-------------|
| `max_chunk_bytes` | `int` (property) | Maximum UTF-8 byte length per chunk |
| `output_format` | `str` (property) | Audio file extension (`"wav"`, `"mp3"`) |
| `synthesize(text, output_path)` | method | Generate audio file from text |

Implemented by: [Qwen Backend](../providers/qwen-backend.md), [Remote TTS](../providers/remote-tts.md)

---

## Dataclasses

### `BBox`
A bounding box in PDF coordinate space (points, origin top-left).

| Field | Type | Description |
|-------|------|-------------|
| `x0` | `float` | Left edge |
| `y0` | `float` | Top edge |
| `x1` | `float` | Right edge |
| `y1` | `float` | Bottom edge |
| `page` | `int` | 1-indexed PDF page number |

Produced by: [Extractor](extractor.md) (`extract_words_with_bboxes`)
Consumed by: [Page Renderer](page-renderer.md), [Word Matcher](word-matcher.md)

### `PDFWordInfo`
A word extracted from a PDF with its position.

| Field | Type | Description |
|-------|------|-------------|
| `word` | `str` | The word text |
| `bbox` | `BBox` | Bounding box in PDF coordinates |
| `page` | `int` | 1-indexed PDF page number |

Produced by: [Extractor](extractor.md) (`extract_words_with_bboxes`)
Consumed by: [Word Matcher](word-matcher.md)

### `WordTiming`
A single word with its timing in the audio.

| Field | Type | Description |
|-------|------|-------------|
| `word` | `str` | The word text |
| `start` | `float` | Start time in seconds |
| `end` | `float` | End time in seconds |
| `page` | `int` | Source PDF page (1-indexed), 0 = unknown |
| `bbox` | `Optional[BBox]` | PDF bounding box, if matched |

Produced by: [Aligner](aligner.md), [WhisperX Provider](../providers/whisper-x-provider.md); enriched by [Word Matcher](word-matcher.md)
Consumed by: [Highlight Renderer](highlight-renderer.md), [Page Renderer](page-renderer.md), [Video Composer](video-composer.md), [EPUB Builder](epub-builder.md)

### `AlignedChunk`
A text chunk with its audio file and word-level alignment.

| Field | Type | Description |
|-------|------|-------------|
| `chunk_num` | `int` | Sequential chunk number |
| `text` | `str` | Original chunk text |
| `audio_path` | `str` | Path to synthesized audio file |
| `words` | `List[WordTiming]` | Word-level timing data |
| `offset` | `float` | Time offset in the concatenated audio |
| `pages` | `List[int]` | Source page numbers (for EPUB) |

Produced by: [Pipeline Common](../pipelines/pipeline-common.md) (`align_chunks`)
Consumed by: [Highlight Pipeline](../pipelines/highlight-pipeline.md), [Lipsync Pipeline](../pipelines/lipsync-pipeline.md), [Video Composer](video-composer.md), [EPUB Builder](epub-builder.md)

---

## Dependency Graph

```
Types
├──▶ used by Pipeline Types (extends for request objects)
├──▶ used by Aligner (returns WordTiming)
├──▶ used by Pipeline Common (builds AlignedChunk)
├──▶ used by Highlight Renderer (reads WordTiming)
├──▶ used by Page Renderer (reads WordTiming + BBox)
├──▶ used by Word Matcher (reads PDFWordInfo, writes BBox to WordTiming)
├──▶ used by Video Composer (reads AlignedChunk)
├──▶ used by EPUB Builder (reads AlignedChunk)
└──▶ used by TTS Registry (validates TTSBackend)
```

---

## See Also

- [Pipeline Types](../pipelines/pipeline-types.md) — Pipeline-specific request/result dataclasses
- [Constants](constants.md) — Default byte limits referenced by backends
