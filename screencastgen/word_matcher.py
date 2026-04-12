"""Match WhisperX-aligned words back to PDF word bounding boxes.

The TTS pipeline extracts text (PyPDF2), preprocesses it, chunks it,
synthesises audio, then aligns with WhisperX.  Meanwhile PyMuPDF extracts
the same words with bounding boxes.  This module bridges the two: it walks
both lists in order, matching normalised forms, and copies the bbox from the
PDF side onto each :class:`WordTiming`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List

from .types import AlignedChunk, PDFWordInfo

# Maximum number of PDF words to look ahead when searching for a match.
_LOOKAHEAD = 30


def _normalize(word: str) -> str:
    """Lowercase, strip punctuation, and normalise quotes for comparison."""
    w = unicodedata.normalize("NFKC", word).lower().strip()
    # Normalise smart quotes / dashes
    w = w.replace("\u201c", '"').replace("\u201d", '"')
    w = w.replace("\u2018", "'").replace("\u2019", "'")
    w = w.replace("\u2013", "-").replace("\u2014", "-")
    # Strip leading/trailing punctuation
    w = w.strip('.,;:!?"\'-()[]{}')
    # Collapse internal whitespace
    w = re.sub(r"\s+", " ", w)
    return w


def _is_prefix_match(aligned_norm: str, pdf_norm: str) -> bool:
    """Check if *aligned_norm* is a prefix or suffix of *pdf_norm* (for split words)."""
    if not aligned_norm or not pdf_norm:
        return False
    return pdf_norm.startswith(aligned_norm) or pdf_norm.endswith(aligned_norm)


def match_words_to_bboxes(
    aligned_chunks: List[AlignedChunk],
    pdf_words: List[PDFWordInfo],
) -> None:
    """Enrich every :class:`WordTiming` in *aligned_chunks* with bbox data.

    Walks *pdf_words* sequentially, matching each aligned word by its
    normalised form.  A lookahead window handles small insertions or
    deletions caused by text preprocessing.  Words that cannot be matched
    keep ``bbox=None`` — they simply won't be highlighted on the page.

    Mutates the ``WordTiming`` objects in place.
    """
    if not pdf_words:
        return

    cursor = 0  # position in pdf_words

    for ac in aligned_chunks:
        for wt in ac.words:
            aligned_norm = _normalize(wt.word)
            if not aligned_norm:
                continue

            matched = False
            # Search forward from cursor within the lookahead window
            end = min(cursor + _LOOKAHEAD, len(pdf_words))
            for j in range(cursor, end):
                pdf_norm = _normalize(pdf_words[j].word)

                if aligned_norm == pdf_norm:
                    wt.bbox = pdf_words[j].bbox
                    wt.page = pdf_words[j].page
                    cursor = j + 1
                    matched = True
                    break

                # Handle camelCase splitting: preprocessing may split
                # "forEach" into two aligned words "for" and "Each", but
                # the PDF has a single word "forEach".
                if _is_prefix_match(aligned_norm, pdf_norm):
                    wt.bbox = pdf_words[j].bbox
                    wt.page = pdf_words[j].page
                    # Don't advance cursor — next aligned word may also
                    # match this same PDF word (e.g. the "Each" part).
                    matched = True
                    break

            if not matched:
                # Soft skip: advance cursor by 1 to avoid getting stuck,
                # but only if we're not already past the pdf_words.
                if cursor < len(pdf_words) - 1:
                    cursor += 1
