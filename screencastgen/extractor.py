"""Document text extraction.

Supports:
  * ``.pdf``  – via PyPDF2
  * ``.txt``  – plain UTF-8 text
  * ``.md``   – Markdown converted to plain text
  * ``.epub`` – via the ``ebooklib`` package (optional dependency)

PyMuPDF (fitz) functions are deferred-imported and only used for the
page-image rendering pipeline (word bounding boxes + page rasterisation).
"""

import os
import re
from typing import List, Optional, Tuple

import PyPDF2


MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown"}
SUPPORTED_TEXT_EXTENSIONS = {".pdf", ".txt", ".epub", *MARKDOWN_EXTENSIONS}


def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def read_markdown_source(path: str) -> Optional[str]:
    """Return raw Markdown source for Markdown files, otherwise ``None``."""
    if _ext(path) not in MARKDOWN_EXTENSIONS:
        return None
    return _read_text_file(path)


def strip_markdown_formatting(markdown: str) -> str:
    """Return readable plain text from Markdown without formatting markers."""
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")

    # Drop metadata and non-readable markup that should not be narrated.
    text = re.sub(r"\A---\s*\n.*?\n---\s*(?:\n|$)", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)

    # Preserve code content but remove fence/indent formatting.
    text = re.sub(r"^[ \t]*(```+|~~~+)[^\n]*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*(```+|~~~+)[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?m)^(?: {4}|\t)(.+)$", r"\1", text)

    # Links/images should narrate their human-readable text, not URLs.
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"^\s{0,3}\[[^\]]+\]:\s+\S+.*$", " ", text, flags=re.MULTILINE)

    # Strip block and inline syntax while keeping the words.
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-+*]\s+\[[ xX]\]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-+*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}[-*_]{3,}\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"\*(?!\s)(.*?)(?<!\s)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(?!\s)(.*?)(?<!\s)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.*?)~~", r"\1", text)

    # Markdown table pipes/separators are formatting, not content.
    text = re.sub(r"^\s*\|?[\s:|-]{3,}\|[\s:|.-]*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"(?m)^\s*\|(.+)\|\s*$", lambda m: m.group(1).replace("|", " "), text)

    # Remove raw HTML tags after markdown-specific handling.
    text = re.sub(r"<[^>]+>", " ", text)

    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _read_epub(path: str) -> List[Tuple[int, str]]:
    """Return ``[(page_num, text), ...]`` from an EPUB, one entry per chapter."""
    try:
        from ebooklib import epub, ITEM_DOCUMENT
    except ImportError as exc:
        raise ImportError(
            "EPUB support requires `ebooklib`. Install with `pip install ebooklib beautifulsoup4`."
        ) from exc
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ImportError(
            "EPUB support requires `beautifulsoup4`. Install with `pip install beautifulsoup4`."
        ) from exc

    book = epub.read_epub(path)
    pages: List[Tuple[int, str]] = []
    idx = 0
    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        idx += 1
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n")
        pages.append((idx, text))
    return pages


def extract_text(path: str) -> str:
    """Read *path* and return concatenated plain text."""
    ext = _ext(path)
    if ext == ".pdf":
        text = ""
        with open(path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
        return text
    if ext == ".txt":
        return _read_text_file(path)
    if ext in MARKDOWN_EXTENSIONS:
        return strip_markdown_formatting(_read_text_file(path))
    if ext == ".epub":
        return "\n".join(text for _, text in _read_epub(path))
    raise ValueError(
        f"Unsupported file extension '{ext}'. Supported: .pdf, .txt, .md, .epub"
    )


def extract_text_by_page(path: str) -> List[Tuple[int, str]]:
    """Read *path* and return ``[(page_num, text), ...]`` (1-indexed).

    For ``.txt`` and Markdown files the entire content is returned as a
    single page. For ``.epub`` files each document item becomes a page.
    """
    ext = _ext(path)
    if ext == ".pdf":
        pages: List[Tuple[int, str]] = []
        with open(path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            for idx, page in enumerate(reader.pages):
                pages.append((idx + 1, page.extract_text() or ""))
        return pages
    if ext == ".txt":
        return [(1, _read_text_file(path))]
    if ext in MARKDOWN_EXTENSIONS:
        return [(1, strip_markdown_formatting(_read_text_file(path)))]
    if ext == ".epub":
        return _read_epub(path)
    raise ValueError(
        f"Unsupported file extension '{ext}'. Supported: .pdf, .txt, .md, .epub"
    )


# ---------------------------------------------------------------------------
# PyMuPDF-based extraction (deferred import)
# ---------------------------------------------------------------------------

def extract_words_with_bboxes(path: str) -> List["PDFWordInfo"]:
    """Extract every word from *path* with its bounding box using PyMuPDF.

    Returns a flat list in reading order.  Each entry carries the word text,
    its bounding box in PDF points, and the 1-indexed page number.
    """
    import fitz  # pymupdf

    from .types import BBox, PDFWordInfo

    doc = fitz.open(path)
    result: List[PDFWordInfo] = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        # ``sort=True`` keeps extraction in visual reading order, which the
        # bbox matcher relies on when walking aligned words sequentially.
        # get_text("words") returns (x0, y0, x1, y1, word, block, line, word_no)
        for entry in page.get_text("words", sort=True):
            x0, y0, x1, y1, word_text = entry[0], entry[1], entry[2], entry[3], entry[4]
            word_text = word_text.strip()
            if not word_text:
                continue
            result.append(
                PDFWordInfo(
                    word=word_text,
                    bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1, page=page_num),
                    page=page_num,
                )
            )
    doc.close()
    return result


def render_page_image_with_zoom(
    path: str,
    page_num: int,
    target_width: Optional[int] = None,
) -> Tuple["Image.Image", float]:
    """Rasterise a single PDF page to a Pillow RGB image.

    *page_num* is 1-indexed.  If *target_width* is given the page is scaled
    proportionally to that width; otherwise the native resolution is used.
    """
    import fitz  # pymupdf
    from PIL import Image

    doc = fitz.open(path)
    page = doc[page_num - 1]

    if target_width:
        zoom = target_width / page.rect.width
    else:
        zoom = 1.0

    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    return img, zoom


def render_page_image(
    path: str,
    page_num: int,
    target_width: Optional[int] = None,
) -> "Image.Image":
    """Backward-compatible wrapper for page rasterisation."""
    img, _zoom = render_page_image_with_zoom(path, page_num, target_width=target_width)
    return img


def get_page_count(path: str) -> int:
    """Return the number of pages in a PDF."""
    import fitz  # pymupdf

    doc = fitz.open(path)
    count = len(doc)
    doc.close()
    return count
