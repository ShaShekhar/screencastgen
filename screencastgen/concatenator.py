"""Concatenate per-chunk audio files into a single output file.

Strategy: try pydub (pure-Python, needs ffmpeg at runtime) first,
fall back to calling ffmpeg directly via subprocess.
"""

import glob
import os
import subprocess
import tempfile
from typing import List, Optional


def _find_chunk_files(output_dir: str, ext: str = "mp3") -> List[str]:
    """Return sorted list of chunk audio files in *output_dir*."""
    pattern = os.path.join(output_dir, f"audio_chunk_*.{ext}")
    return sorted(glob.glob(pattern))


def _concat_pydub(files: List[str], dest: str) -> None:
    from pydub import AudioSegment  # type: ignore[import-untyped]

    combined = AudioSegment.empty()
    for path in files:
        combined += AudioSegment.from_file(path)
    combined.export(dest, format=os.path.splitext(dest)[1].lstrip(".") or "mp3")


def _concat_ffmpeg(files: List[str], dest: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
        for path in files:
            fh.write(f"file '{os.path.abspath(path)}'\n")
        list_path = fh.name

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", dest],
            check=True,
            capture_output=True,
        )
    finally:
        os.unlink(list_path)


def concatenate(
    output_dir: str,
    dest: str,
    ext: str = "mp3",
    files: Optional[List[str]] = None,
) -> str:
    """Merge chunk files from *output_dir* into *dest*.

    Returns the path to the merged file.
    """
    if files is None:
        files = _find_chunk_files(output_dir, ext)

    if not files:
        raise FileNotFoundError(f"No audio_chunk_*.{ext} files found in {output_dir}")

    try:
        _concat_pydub(files, dest)
    except ImportError:
        _concat_ffmpeg(files, dest)

    return dest
