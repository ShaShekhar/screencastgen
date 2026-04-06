"""PDF text extraction."""

from typing import List, Tuple

import PyPDF2


def extract_text(pdf_path: str) -> str:
    """Read every page of *pdf_path* and return the concatenated text."""
    text = ""
    with open(pdf_path, "rb") as fh:
        reader = PyPDF2.PdfReader(fh)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text


def extract_text_by_page(pdf_path: str) -> List[Tuple[int, str]]:
    """Read every page of *pdf_path* and return ``[(page_num, text), ...]``.

    Page numbers are 1-indexed.
    """
    pages: List[Tuple[int, str]] = []
    with open(pdf_path, "rb") as fh:
        reader = PyPDF2.PdfReader(fh)
        for idx, page in enumerate(reader.pages):
            pages.append((idx + 1, page.extract_text() or ""))
    return pages
