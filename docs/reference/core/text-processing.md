# Text Processing

> Preprocessing, sentence splitting, chunking, and validation.

**Source:** [`screencastgen/text_processing.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/text_processing.py)

---

## Functions

### `preprocess_text(text: str) -> str`
Cleans raw extracted text:
- Fixes PDF artifacts (broken words, stray hyphens)
- Normalizes quotes (curly → straight)
- Handles LaTeX fragments
- Normalizes bullet points and whitespace

### `split_into_sentences(text: str) -> List[str]`
Splits text on sentence boundaries (`.`, `!`, `?`). Handles abbreviations and edge cases. Forces splits on sentences exceeding `MAX_SENTENCE_BYTES`.

### `split_into_sentences_by_page(pages: List[Tuple[int, str]]) -> List[PageSentence]`
Page-aware variant that preserves which page each sentence came from. Used for EPUB output.

### `create_chunks(sentences: List[str], max_bytes: int) -> List[str]`
Combines sentences into chunks that fit within `max_bytes` (UTF-8 byte length). Greedy packing — adds sentences to current chunk until the next would exceed the limit.

### `create_chunks_with_pages(page_sentences, max_bytes) -> List[Tuple[str, List[int]]]`
Page-aware chunking that returns `(chunk_text, page_numbers)` tuples.

### `validate_chunk(chunk, chunk_num, max_tts_bytes, sentence_warn_bytes) -> Tuple[bool, List[str]]`
Validates a chunk against byte limits. Returns `(is_valid, warnings)`.

---

## Byte-Based Sizing

All sizing uses **UTF-8 byte length**, not character count. This is critical because TTS APIs have byte-based limits. See [Constants](constants.md) for the default values:

| Limit | Default | Purpose |
|-------|---------|---------|
| `MAX_CHUNK_BYTES` | 4900 | Max chunk size for TTS |
| `MAX_SENTENCE_BYTES` | 850 | Force-split threshold |
| `MAX_TTS_BYTES` | 5000 | Hard validation limit |

---

## Dependencies

```
Text Processing
├── Constants        (byte limits)
├──▶ consumed by Pipeline Common
└──▶ fed by Extractor
```

---

## Data Flow

```
Raw text (from Extractor)
    │
    ▼  preprocess_text()
Clean text
    │
    ▼  split_into_sentences()
List[str] sentences
    │
    ▼  create_chunks(sentences, max_bytes)
List[str] chunks
    │
    ▼  validate_chunk()
Validated chunks → ready for TTS
```

---

## See Also

- [Extractor](extractor.md) — Previous step: document parsing
- [Pipeline Common](../pipelines/pipeline-common.md) — Orchestrates the text pipeline
- [Constants](constants.md) — Byte limit values
- [Types](types.md) — `TTSBackend.max_chunk_bytes` property
