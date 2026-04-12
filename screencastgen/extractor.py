"""Document text extraction.

Supports:
  * ``.pdf``  – via PyPDF2
  * ``.txt``  – plain UTF-8 text
  * ``.epub`` – via the ``ebooklib`` package (optional dependency)

PyMuPDF (fitz) functions are deferred-imported and only used for the
page-image rendering pipeline (word bounding boxes + page rasterisation).
"""

import os
from typing import List, Optional, Tuple

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
