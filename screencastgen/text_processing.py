"""Text preprocessing, sentence splitting, chunking, and validation."""

import re
from typing import List, Tuple

from .constants import (
    LONG_SENTENCE_THRESHOLD,
    MAX_CHUNK_BYTES,
    MAX_SENTENCE_BYTES,
    MAX_TTS_BYTES,
    SENTENCE_WARN_BYTES,
)


# -- preprocessing ------------------------------------------------------------

def preprocess_text(text: str) -> str:
    """Fix common PDF-extraction artefacts and prepare text for TTS."""
    # Normalize smart quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")

    # Remove code blocks - replace with a simple note
    text = re.sub(r"<code>.*?</code>", " See code example. ", text, flags=re.DOTALL)
    text = re.sub(r"<output>.*?</output>", " See output. ", text, flags=re.DOTALL)

    # Remove inline code patterns (Python-like comments before assignments)
    text = re.sub(r"#\s*Step\s*\d+[^.]*", ". ", text)
    text = re.sub(r"#[^.]{0,50}(?=\s+[a-z_]+\s*=)", ". ", text)

    # Remove LaTeX artifacts
    text = re.sub(r"/[a-z]+display\s*", " ", text)
    text = re.sub(r"/[a-z]+\s*", " ", text)
    text = re.sub(r"\\[a-z]+\s*", " ", text)

    # Add periods after bullet points
    text = re.sub(r"[•●○▪▸►◦‣⁃]\s*", ". ", text)

    # Handle dashes as list markers
    text = re.sub(r"\s[-–—]\s+([A-Z])", r". \1", text)

    # Fix run-together words from PDF extraction
    text = re.sub(r"(@[a-zA-Z0-9.-]+\.[a-zA-Z]+)([A-Z])", r"\1 \2", text)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"\.([A-Z])", r". \1", text)
    text = re.sub(r"(Table\s*of\s*Contents)", r" \1 ", text)
    text = re.sub(r"(Editor:\s*[A-Za-z\s]+)([A-Z])", r"\1 \2", text)

    # Treat semicolons as sentence boundaries
    text = re.sub(r";\s+", ". ", text)

    # Treat colons followed by capital letter as sentence boundaries
    text = re.sub(r":\s+([A-Z])", r". \1", text)

    # Add periods after closing parentheses/brackets followed by capital letter
    text = re.sub(r"(\)|\])\s*([A-Z][a-z])", r"\1. \2", text)

    # Add periods after numbers followed by capital letter (math expressions)
    text = re.sub(r"(\d)\s+([A-Z][a-z])", r"\1. \2", text)

    # Fix spaced-out letters like "G R P O" -> convert to "GRPO."
    text = re.sub(r"([A-Z])\s+([A-Z])\s+([A-Z])\s+([A-Z])(\s+[A-Z][a-z])", r"\1\2\3\4.\5", text)
    text = re.sub(r"([A-Z])\s+([A-Z])\s+([A-Z])(\s+[A-Z][a-z])", r"\1\2\3.\4", text)

    # Add periods after equations ending in numbers before new sentences
    text = re.sub(r"(\d)\s*\)\s*([A-Z])", r"\1). \2", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Clean up multiple periods
    text = re.sub(r"\.\.+", ".", text)
    text = re.sub(r"\.\s+\.", ". ", text)

    return text.strip()


def _break_long_runs(text: str, max_run_bytes: int = 400) -> str:
    """Insert periods to break up long runs without sentence-ending punctuation."""
    words = text.split()
    result: List[str] = []
    current_len = 0

    for word in words:
        word_len = len(word.encode("utf-8"))
        if current_len + word_len > max_run_bytes and not word.endswith((".", "!", "?")):
            # Add period to previous word if it doesn't have one
            if result and not result[-1].endswith((".", "!", "?")):
                result[-1] = result[-1] + "."
            current_len = 0
        result.append(word)
        current_len += word_len + 1
        if word.endswith((".", "!", "?")):
            current_len = 0

    return " ".join(result)


# -- sentence splitting -------------------------------------------------------

def _split_long_sentence(sentence: str, max_bytes: int = LONG_SENTENCE_THRESHOLD) -> List[str]:
    """Break a sentence that exceeds *max_bytes* into smaller pieces."""
    if len(sentence.encode("utf-8")) <= max_bytes:
        return [sentence]

    # Try punctuation-based splits first
    for delimiter in ["; ", ", ", " - ", " \u2014 ", ": ", " and ", " or ", " but "]:
        if delimiter not in sentence:
            continue
        parts = sentence.split(delimiter)
        result: List[str] = []
        current = ""
        for i, part in enumerate(parts):
            if i > 0:
                part = delimiter.strip() + " " + part
            if len((current + " " + part).encode("utf-8")) > max_bytes:
                if current:
                    result.append(current.strip() + ".")
                current = part
            else:
                current = (current + " " + part).strip() if current else part
        if current:
            tail = current.strip()
            result.append(tail if tail.endswith((".", "!", "?")) else tail + ".")
        if all(len(p.encode("utf-8")) <= max_bytes for p in result):
            return result

    # Fall back to word-level splitting
    words = sentence.split()
    result = []
    current = ""
    for word in words:
        if len((current + " " + word).encode("utf-8")) > max_bytes:
            if current:
                result.append(current.strip() + ".")
            current = word
        else:
            current = (current + " " + word).strip() if current else word
    if current:
        tail = current.strip()
        result.append(tail if tail.endswith((".", "!", "?")) else tail + ".")
    return result


def split_into_sentences(text: str) -> List[str]:
    """Split *text* into sentences, ensuring none exceed the byte limit."""
    # Add periods after chapter headings that lack punctuation
    text = re.sub(r"(CHAPTER\s+\d+[^.!?]*?)(?=[A-Z])", r"\1. ", text)
    text = re.sub(r"(Chapter\s+\d+[^.!?]*?)(?=[A-Z])", r"\1. ", text)

    # Break up long runs without punctuation
    text = _break_long_runs(text)

    raw = re.split(r"(?<=[.!?])\s+", text)
    sentences: List[str] = []
    for sent in raw:
        sent = sent.strip()
        if not sent:
            continue
        # Ensure sentence ends with punctuation
        if sent and sent[-1] not in ".!?":
            sent = sent + "."
        if len(sent.encode("utf-8")) > LONG_SENTENCE_THRESHOLD:
            sentences.extend(_split_long_sentence(sent))
        else:
            sentences.append(sent)
    return sentences


# -- chunking -----------------------------------------------------------------

def create_chunks(sentences: List[str], max_bytes: int = MAX_CHUNK_BYTES) -> List[str]:
    """Combine sentences into chunks that stay within *max_bytes*."""
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        candidate = current + (" " if current else "") + sentence
        if len(candidate.encode("utf-8")) > max_bytes:
            if current:
                chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


# -- page-aware variants (for EPUB output) ------------------------------------

# A sentence tagged with its source PDF page number.
PageSentence = Tuple[int, str]


def split_into_sentences_by_page(
    pages: List[Tuple[int, str]],
) -> List[PageSentence]:
    """Preprocess and split each page's text, tagging sentences with page numbers.

    *pages* is a list of ``(page_num, raw_page_text)`` as returned by
    ``extract_text_by_page()``.
    """
    result: List[PageSentence] = []
    for page_num, page_text in pages:
        processed = preprocess_text(page_text)
        if not processed:
            continue
        sentences = split_into_sentences(processed)
        for sent in sentences:
            result.append((page_num, sent))
    return result


def create_chunks_with_pages(
    page_sentences: List[PageSentence],
    max_bytes: int = MAX_CHUNK_BYTES,
) -> List[Tuple[str, List[int]]]:
    """Combine page-tagged sentences into chunks, tracking source pages.

    Returns a list of ``(chunk_text, [page_numbers])``.  Chunks are **not**
    split at page boundaries — a single chunk may span multiple pages.
    """
    chunks: List[Tuple[str, List[int]]] = []
    current = ""
    current_pages: List[int] = []

    for page_num, sentence in page_sentences:
        candidate = current + (" " if current else "") + sentence
        if len(candidate.encode("utf-8")) > max_bytes:
            if current:
                chunks.append((current, sorted(set(current_pages))))
            current = sentence
            current_pages = [page_num]
        else:
            current = candidate
            if page_num not in current_pages:
                current_pages.append(page_num)

    if current:
        chunks.append((current, sorted(set(current_pages))))
    return chunks


# -- validation ---------------------------------------------------------------

def validate_chunk(
    chunk: str,
    chunk_num: int,
    *,
    max_tts_bytes: int = MAX_TTS_BYTES,
    sentence_warn_bytes: int = SENTENCE_WARN_BYTES,
) -> Tuple[bool, List[str]]:
    """Check *chunk* against TTS size limits.

    Pass backend-specific limits via *max_tts_bytes* and *sentence_warn_bytes*.
    Returns ``(is_valid, list_of_issues)``.
    """
    issues: List[str] = []

    chunk_bytes = len(chunk.encode("utf-8"))
    if chunk_bytes > max_tts_bytes:
        issues.append(f"Chunk size {chunk_bytes} exceeds {max_tts_bytes} bytes")

    # Per-sentence check
    for i, sent in enumerate(re.split(r"(?<=[.!?])\s*", chunk)):
        if not sent.strip():
            continue
        sent_bytes = len(sent.encode("utf-8"))
        if sent_bytes > sentence_warn_bytes:
            issues.append(
                f"Sentence {i + 1} is {sent_bytes} bytes: '{sent[:50]}...'"
            )

    # Long-run-without-punctuation check
    current_run = ""
    for word in chunk.split():
        current_run += word + " "
        if any(current_run.rstrip().endswith(p) for p in (".", "!", "?")):
            if len(current_run.encode("utf-8")) > sentence_warn_bytes:
                issues.append(
                    f"Long run without sentence ending: "
                    f"{len(current_run.encode('utf-8'))} bytes"
                )
            current_run = ""

    return len(issues) == 0, issues
