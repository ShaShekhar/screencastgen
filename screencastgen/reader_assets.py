"""Build browser-reader assets (manifest + concatenated audio + page images).

The reader manifest is a single JSON file consumed by the web frontend to
render a synced reading view: flowing text with per-word highlighting driven
by an HTML ``<audio>`` element. All timestamps in the manifest are global —
relative to the start of the concatenated audio file.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import List, Optional

from .extractor import MARKDOWN_EXTENSIONS, read_markdown_source
from .types import AlignedChunk


MANIFEST_NAME = "reader_manifest.json"
AUDIO_NAME = "reader_audio.mp3"
PRESENTER_NAME = "presenter.mp4"
PAGES_DIR = "pages"
SOURCE_DOCUMENT_STEM = "source_document"
PAGE_IMAGE_WIDTH = 1400  # pixels; fits desktop readers and downscales on mobile
SOURCE_COPY_EXTENSIONS = {".pdf", *MARKDOWN_EXTENSIONS}


def _audio_duration_secs(path: str) -> float:
    try:
        from pydub import AudioSegment  # type: ignore[import-untyped]

        return AudioSegment.from_file(path).duration_seconds
    except ImportError:
        import subprocess

        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())


def _concatenate_chunks(aligned_chunks: List[AlignedChunk], dest: str) -> List[float]:
    """Concatenate per-chunk audio into *dest* as MP3.

    Returns a list of offsets (seconds) — one per chunk, in order.
    """
    from pydub import AudioSegment  # type: ignore[import-untyped]

    combined = AudioSegment.empty()
    offsets: List[float] = []
    for ac in aligned_chunks:
        offsets.append(combined.duration_seconds)
        combined += AudioSegment.from_file(ac.audio_path)
    combined.export(dest, format="mp3")
    return offsets


def _render_pages(pdf_path: str, page_nums: List[int], pages_dir: str) -> dict:
    """Rasterise *page_nums* from *pdf_path* into ``pages_dir`` as JPEGs.

    Returns a ``{page_num: filename}`` map. On any failure (non-PDF, no
    pymupdf, rendering error) returns ``{}`` and the reader falls back to
    reflowed text.
    """
    if not page_nums:
        return {}
    ext = os.path.splitext(pdf_path)[1].lower()
    if ext != ".pdf":
        return {}

    try:
        from .extractor import render_page_image_with_zoom
    except ImportError:
        return {}

    os.makedirs(pages_dir, exist_ok=True)
    result: dict = {}
    for page_num in sorted(set(page_nums)):
        try:
            img, _zoom = render_page_image_with_zoom(
                pdf_path, page_num, target_width=PAGE_IMAGE_WIDTH,
            )
            filename = f"page-{page_num:04d}.jpg"
            img.convert("RGB").save(
                os.path.join(pages_dir, filename), "JPEG", quality=82, optimize=True,
            )
            result[page_num] = filename
        except Exception:
            continue
    return result


def _source_document_filename(source_path: str) -> str | None:
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in SOURCE_COPY_EXTENSIONS:
        return None
    return f"{SOURCE_DOCUMENT_STEM}{ext}"


def ensure_source_document(output_dir: str, source_path: str) -> str | None:
    """Copy the display source into the reader output directory.

    PDF readers can use the original PDF directly when page rasterisation is
    unavailable, and Markdown readers keep the source alongside the manifest.
    """
    filename = _source_document_filename(source_path)
    if not filename or not os.path.isfile(source_path):
        return None
    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, filename)
    if os.path.abspath(source_path) != os.path.abspath(dest):
        shutil.copy2(source_path, dest)
    return filename


def refresh_manifest_source(manifest_path: str, source_path: str) -> bool:
    """Update an existing reader manifest with current source display data."""
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    output_dir = os.path.dirname(os.path.abspath(manifest_path))
    changed = False
    source_ext = os.path.splitext(source_path)[1].lower().lstrip(".") or "text"
    if manifest.get("source_type") != source_ext:
        manifest["source_type"] = source_ext
        changed = True

    source_file = ensure_source_document(output_dir, source_path)
    if source_file and manifest.get("source_file") != source_file:
        manifest["source_file"] = source_file
        changed = True

    source_markdown = read_markdown_source(source_path)
    if source_markdown is not None and manifest.get("source_markdown") != source_markdown:
        manifest["source_markdown"] = source_markdown
        changed = True

    if changed:
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False)
    return changed


def build_reader_assets(
    aligned_chunks: List[AlignedChunk],
    output_dir: str,
    pdf_path: str,
    title: str,
    language: str = "en",
    presenter: Optional[str] = None,
) -> Optional[str]:
    """Write reader manifest, concatenated audio, and (for PDF) page images.

    ``presenter`` is the filename of a talking-head video synced to the same
    timeline (lip-sync jobs); ``None`` for audio-only highlight jobs.

    Returns the manifest path on success, ``None`` if no chunks were available
    to render.
    """
    if not aligned_chunks:
        return None

    os.makedirs(output_dir, exist_ok=True)
    audio_dest = os.path.join(output_dir, AUDIO_NAME)

    try:
        chunk_offsets = _concatenate_chunks(aligned_chunks, audio_dest)
    except Exception as exc:
        raise RuntimeError(f"Reader audio concatenation failed: {exc}") from exc

    total_duration = _audio_duration_secs(audio_dest)

    page_nums: List[int] = []
    for ac in aligned_chunks:
        if ac.pages:
            page_nums.extend(ac.pages)
    page_map = _render_pages(pdf_path, page_nums, os.path.join(output_dir, PAGES_DIR))

    manifest_chunks = []
    for offset, ac in zip(chunk_offsets, aligned_chunks):
        words = [
            {
                "word": w.word,
                "start": round(offset + w.start, 3),
                "end": round(offset + w.end, 3),
            }
            for w in ac.words
        ]
        manifest_chunks.append(
            {
                "chunk_num": ac.chunk_num,
                "text": ac.text,
                "offset": round(offset, 3),
                "pages": ac.pages,
                "words": words,
            }
        )

    source_ext = os.path.splitext(pdf_path)[1].lower().lstrip(".") or "text"
    source_file = ensure_source_document(output_dir, pdf_path)
    source_markdown = read_markdown_source(pdf_path)
    manifest = {
        "version": 1,
        "title": title,
        "language": language,
        "source_type": source_ext,
        "source_file": source_file,
        "source_markdown": source_markdown,
        "duration": round(total_duration, 3),
        "audio": AUDIO_NAME,
        "presenter": presenter,
        "pages": (
            {
                "dir": PAGES_DIR,
                "image_width": PAGE_IMAGE_WIDTH,
                "files": {str(k): v for k, v in page_map.items()},
            }
            if page_map
            else None
        ),
        "chunks": manifest_chunks,
    }

    manifest_path = os.path.join(output_dir, MANIFEST_NAME)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False)
    return manifest_path


def reader_asset_names(
    page_files: Optional[dict] = None,
    presenter: bool = False,
) -> List[str]:
    """Return relative paths of every reader asset for upload helpers."""
    names = [MANIFEST_NAME, AUDIO_NAME]
    if presenter:
        names.append(PRESENTER_NAME)
    if page_files:
        for fname in page_files.values():
            names.append(f"{PAGES_DIR}/{fname}")
    return names
