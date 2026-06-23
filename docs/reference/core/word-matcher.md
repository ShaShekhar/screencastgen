# Word Matcher

> Maps WhisperX-aligned words back to PDF word bounding boxes via sequential normalised matching.

**Source:** [`screencastgen/word_matcher.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/word_matcher.py)

---

## Overview

The TTS pipeline extracts text from a PDF (PyPDF2), preprocesses it, chunks it, synthesises audio, then aligns with WhisperX to get word-level timings. Meanwhile, PyMuPDF extracts the same words with their bounding boxes on the page.

The word matcher bridges these two parallel extractions: it walks both word lists in order, matches by normalised form, and copies the `BBox` from the PDF side onto each `WordTiming` object.

---

## Function

### `match_words_to_bboxes(aligned_chunks, pdf_words) -> None`

Enriches every `WordTiming` in the aligned chunks with bbox data. **Mutates in place.**

| Param | Type | Description |
|-------|------|-------------|
| `aligned_chunks` | `List[AlignedChunk]` | Chunks with word timings from WhisperX |
| `pdf_words` | `List[PDFWordInfo]` | Words with bboxes from PyMuPDF |

---

## Algorithm

**Sequential normalised matching with lookahead:**

1. Maintain a cursor into the flat `pdf_words` list.
2. For each aligned word (across all chunks, in order):
   a. Normalise both the aligned word and PDF words with Unicode NFKC, lowercase conversion, punctuation stripping, and quote/dash normalisation.
   b. Search forward from the cursor within a 30-word lookahead window.
   c. **Exact match**: Assign the PDF word's bbox and page, advance cursor past the match.
   d. **Prefix/suffix match**: Handles camelCase splitting (e.g. preprocessing splits "forEach" into "for" + "Each" — both map to the single PDF word's bbox). Does not advance cursor so the next aligned word can also match.
   e. **No match**: Leave `bbox=None`, advance cursor by 1 (soft skip).

### Why Sequential Matching Works

Word order is preserved through the entire pipeline: PDF → preprocess → sentences → chunks → TTS → WhisperX. No step reorders words, and [Extractor](extractor.md) explicitly requests `sort=True` from PyMuPDF so the PDF-side list is also in visual reading order. The 30-word lookahead handles insertions/deletions from preprocessing.

---

## Normalisation

The `_normalize()` function handles mismatches between raw PDF text and preprocessed/WhisperX text:

| Source | Example | Normalised |
|--------|---------|-----------|
| Unicode ligatures | `ﬁnal` | `final` |
| Smart quotes | `\u201cword\u201d` | `word` |
| Punctuation | `Hello,` | `hello` |
| Em dashes | `word\u2014` | `word` |
| Trailing periods | `end.` | `end` |

---

## Preprocessing Mismatch Handling

| Preprocessing Change | Effect on Matching | Resolution |
|---------------------|-------------------|-----------|
| Smart quote normalisation | Character difference | Both sides normalised |
| Code block removal | "See code example." inserted | No PDF match → `bbox=None` |
| camelCase splitting | "forEach" → "for" + "Each" | Prefix match, both get same bbox |
| Semicolons → periods | Punctuation only | Stripped in normalisation |
| LaTeX removal | Words removed | Lookahead skips past |

Words that can't be matched simply don't get highlighted on the page image. The page still displays, audio keeps playing — graceful degradation.

---

## Dependencies

```
Word Matcher
├── Types          (AlignedChunk, WordTiming, BBox, PDFWordInfo)
└──▶ consumed by Highlight Pipeline
     └──▶ consumed by Lipsync Pipeline
```

---

## Data Flow

```
List[AlignedChunk]          List[PDFWordInfo]
(words with timing,         (words with bboxes,
 bbox=None)                  from PyMuPDF)
       │                          │
       └────────┬─────────────────┘
                ▼
    match_words_to_bboxes()
    (sequential normalised matching)
                │
                ▼
    List[AlignedChunk]
    (words now have bbox + page populated)
                │
                ▼
    Page Renderer uses bbox for highlight positioning
```

---

## See Also

- [Page Renderer](page-renderer.md) — Consumes the enriched WordTiming objects
- [Extractor](extractor.md) — `extract_words_with_bboxes()` produces PDFWordInfo
- [Types](types.md) — `WordTiming`, `BBox`, `PDFWordInfo` dataclasses
- [Text Processing](text-processing.md) — Preprocessing that causes word mismatches
