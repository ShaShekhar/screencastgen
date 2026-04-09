"""Document text extraction.

Supports:
  * ``.pdf``  – via PyPDF2
  * ``.txt``  – plain UTF-8 text
  * ``.epub`` – via the ``ebooklib`` package (optional dependency)
"""

import os
from typing import List, Tuple

import PyPDF2


def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


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
    """Read *path* (PDF, TXT, or EPUB) and return concatenated text."""
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
    if ext == ".epub":
        return "\n".join(text for _, text in _read_epub(path))
    raise ValueError(
        f"Unsupported file extension '{ext}'. Supported: .pdf, .txt, .epub"
    )


def extract_text_by_page(path: str) -> List[Tuple[int, str]]:
    """Read *path* and return ``[(page_num, text), ...]`` (1-indexed).

    For ``.txt`` files the entire content is returned as a single page.
    For ``.epub`` files each document item becomes a page.
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
    if ext == ".epub":
        return _read_epub(path)
    raise ValueError(
        f"Unsupported file extension '{ext}'. Supported: .pdf, .txt, .epub"
    )
