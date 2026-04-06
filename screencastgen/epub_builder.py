"""Build EPUB3 packages with Media Overlays (SMIL) for word-level audio sync.

The generated EPUB uses the standard Media Overlays 3.0 specification so that
compliant readers (Apple Books, Thorium, Kobo, Readium, …) can highlight each
word as the corresponding audio plays — no JavaScript or proprietary features.
"""

import os
import shutil
import subprocess
import uuid
import zipfile
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from xml.sax.saxutils import escape

from .constants import (
    EPUB_AUDIO_DIR,
    EPUB_AUDIO_FORMAT,
    EPUB_CHAPTER_DIR,
    EPUB_SMIL_DIR,
    EPUB_VIDEO_DIR,
    MEDIA_OVERLAY_ACTIVE_CLASS,
)
from .types import AlignedChunk


# ---------------------------------------------------------------------------
# Internal data
# ---------------------------------------------------------------------------

@dataclass
class _ChapterData:
    """Collects aligned chunks (and optional lipsync video) for one chapter."""
    num: int
    aligned_chunks: List[AlignedChunk] = field(default_factory=list)
    lipsync_video_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _convert_to_mp3(src: str, dest: str) -> None:
    """Convert *src* audio file to MP3 at *dest*.

    Tries pydub first, falls back to ffmpeg CLI.
    """
    if src.lower().endswith(".mp3"):
        shutil.copy2(src, dest)
        return

    try:
        from pydub import AudioSegment  # type: ignore[import-untyped]
        audio = AudioSegment.from_file(src)
        audio.export(dest, format="mp3")
    except ImportError:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-codec:a", "libmp3lame", "-q:a", "4", dest],
            check=True,
            capture_output=True,
        )


def _audio_duration_secs(path: str) -> float:
    """Return duration of an audio file in seconds."""
    try:
        from pydub import AudioSegment  # type: ignore[import-untyped]
        seg = AudioSegment.from_file(path)
        return seg.duration_seconds
    except ImportError:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())


# ---------------------------------------------------------------------------
# XML / XHTML helpers
# ---------------------------------------------------------------------------

_CONTAINER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

_CSS = """\
body {
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.6;
  margin: 1em;
  color: #1E1E1E;
}
span.-epub-media-overlay-active {
  background-color: #FFFF00;
  color: #1E1E1E;
  border-radius: 2px;
  padding: 0 2px;
}
.speaker-video {
  max-width: 280px;
  float: right;
  margin: 0 0 1em 1em;
  border-radius: 8px;
}
p {
  margin: 0.6em 0;
}
"""


def _fmt_time(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS.mmm`` for SMIL ``clipBegin`` / ``clipEnd``."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _word_id(chunk_num: int, word_idx: int) -> str:
    return f"w{chunk_num:03d}_{word_idx:04d}"


# ---------------------------------------------------------------------------
# EPUBBuilder
# ---------------------------------------------------------------------------

class EPUBBuilder:
    """Assemble an EPUB3 file with Media Overlays from aligned chunks.

    Usage::

        builder = EPUBBuilder("My Book")
        builder.add_chapter(1, aligned_chunks_for_page_1)
        builder.add_chapter(2, aligned_chunks_for_page_2, lipsync_video="face_p2.mp4")
        builder.build("output.epub")
    """

    def __init__(self, title: str, language: str = "en"):
        self.title = title
        self.language = language
        self.book_id = str(uuid.uuid4())
        self._chapters: OrderedDict[int, _ChapterData] = OrderedDict()

    # -- public API ---------------------------------------------------------

    def add_chapter(
        self,
        chapter_num: int,
        aligned_chunks: List[AlignedChunk],
        lipsync_video_path: Optional[str] = None,
    ) -> None:
        """Register a chapter (typically one per PDF page)."""
        if chapter_num in self._chapters:
            ch = self._chapters[chapter_num]
            ch.aligned_chunks.extend(aligned_chunks)
            if lipsync_video_path:
                ch.lipsync_video_path = lipsync_video_path
        else:
            self._chapters[chapter_num] = _ChapterData(
                num=chapter_num,
                aligned_chunks=list(aligned_chunks),
                lipsync_video_path=lipsync_video_path,
            )

    def build(self, output_path: str) -> str:
        """Write the EPUB file to *output_path* and return the path."""
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # mimetype MUST be first and uncompressed
            zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            # META-INF
            zf.writestr("META-INF/container.xml", _CONTAINER_XML)

            # CSS
            zf.writestr(f"OEBPS/style.css", _CSS)

            # Collect manifest / spine / durations as we write chapters
            manifest_items: List[str] = []
            spine_items: List[str] = []
            total_duration = 0.0
            chapter_durations: Dict[int, float] = {}

            # Audio files already copied (audio_path -> epub-internal name)
            audio_map: Dict[str, str] = {}

            for ch in self._chapters.values():
                ch_id = f"chapter_{ch.num:03d}"
                xhtml_path = f"OEBPS/{EPUB_CHAPTER_DIR}/{ch_id}.xhtml"
                smil_path = f"OEBPS/{EPUB_SMIL_DIR}/{ch_id}.smil"

                # --- copy audio files and convert to mp3 ---
                for ac in ch.aligned_chunks:
                    if ac.audio_path in audio_map:
                        continue
                    mp3_name = f"chunk_{ac.chunk_num:03d}.{EPUB_AUDIO_FORMAT}"
                    epub_audio_path = f"OEBPS/{EPUB_AUDIO_DIR}/{mp3_name}"
                    if ac.audio_path.lower().endswith(f".{EPUB_AUDIO_FORMAT}"):
                        zf.write(ac.audio_path, epub_audio_path)
                    else:
                        # Convert in-memory via temp file
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                            tmp_path = tmp.name
                        try:
                            _convert_to_mp3(ac.audio_path, tmp_path)
                            zf.write(tmp_path, epub_audio_path)
                        finally:
                            os.unlink(tmp_path)
                    audio_map[ac.audio_path] = mp3_name
                    # manifest entry for audio
                    manifest_items.append(
                        f'    <item id="audio_{ac.chunk_num:03d}" '
                        f'href="{EPUB_AUDIO_DIR}/{mp3_name}" media-type="audio/mpeg"/>'
                    )

                # --- copy lipsync video ---
                video_epub_name: Optional[str] = None
                if ch.lipsync_video_path and os.path.isfile(ch.lipsync_video_path):
                    video_epub_name = f"face_{ch.num:03d}.mp4"
                    zf.write(
                        ch.lipsync_video_path,
                        f"OEBPS/{EPUB_VIDEO_DIR}/{video_epub_name}",
                    )
                    manifest_items.append(
                        f'    <item id="video_{ch.num:03d}" '
                        f'href="{EPUB_VIDEO_DIR}/{video_epub_name}" '
                        f'media-type="video/mp4"/>'
                    )

                # --- generate XHTML ---
                xhtml_content = self._build_xhtml(ch, video_epub_name)
                zf.writestr(xhtml_path, xhtml_content)

                # --- generate SMIL ---
                smil_content, ch_dur = self._build_smil(ch, audio_map)
                zf.writestr(smil_path, smil_content)
                chapter_durations[ch.num] = ch_dur
                total_duration += ch_dur

                # manifest + spine
                manifest_items.append(
                    f'    <item id="{ch_id}" href="{EPUB_CHAPTER_DIR}/{ch_id}.xhtml" '
                    f'media-type="application/xhtml+xml" media-overlay="smil_{ch.num:03d}"/>'
                )
                manifest_items.append(
                    f'    <item id="smil_{ch.num:03d}" href="{EPUB_SMIL_DIR}/{ch_id}.smil" '
                    f'media-type="application/smil+xml"/>'
                )
                spine_items.append(f'    <itemref idref="{ch_id}"/>')

            # --- toc.xhtml ---
            toc_content = self._build_toc()
            zf.writestr("OEBPS/toc.xhtml", toc_content)

            # --- content.opf ---
            opf_content = self._build_opf(
                manifest_items, spine_items, total_duration, chapter_durations,
            )
            zf.writestr("OEBPS/content.opf", opf_content)

        return output_path

    # -- private builders ---------------------------------------------------

    def _build_xhtml(self, ch: _ChapterData, video_name: Optional[str]) -> str:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE html>',
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops">',
            "<head>",
            f"  <title>Page {ch.num}</title>",
            '  <link rel="stylesheet" type="text/css" href="../style.css"/>',
            "</head>",
            "<body>",
            f'  <section epub:type="chapter" id="ch{ch.num:03d}">',
        ]

        if video_name:
            lines.append(
                f'    <video src="../{EPUB_VIDEO_DIR}/{video_name}" '
                f'controls="controls" class="speaker-video">'
                f"Your reader does not support video.</video>"
            )

        for ac in ch.aligned_chunks:
            lines.append("    <p>")
            if ac.words:
                for idx, wt in enumerate(ac.words):
                    wid = _word_id(ac.chunk_num, idx)
                    lines.append(f'      <span id="{wid}">{escape(wt.word)}</span>')
            else:
                # No alignment data — render plain text
                lines.append(f"      {escape(ac.text)}")
            lines.append("    </p>")

        lines += [
            "  </section>",
            "</body>",
            "</html>",
        ]
        return "\n".join(lines) + "\n"

    def _build_smil(
        self, ch: _ChapterData, audio_map: Dict[str, str],
    ) -> tuple:
        """Return ``(smil_xml, duration_seconds)``."""
        ch_id = f"chapter_{ch.num:03d}"
        par_elements: List[str] = []
        max_end = 0.0

        for ac in ch.aligned_chunks:
            mp3_name = audio_map.get(ac.audio_path, "")
            audio_href = f"../{EPUB_AUDIO_DIR}/{mp3_name}"
            for idx, wt in enumerate(ac.words):
                wid = _word_id(ac.chunk_num, idx)
                par_id = f"par_{ac.chunk_num:03d}_{idx:04d}"
                par_elements.append(
                    f"      <par id=\"{par_id}\">\n"
                    f"        <text src=\"../{EPUB_CHAPTER_DIR}/{ch_id}.xhtml#{wid}\"/>\n"
                    f"        <audio src=\"{audio_href}\" "
                    f"clipBegin=\"{_fmt_time(wt.start)}\" "
                    f"clipEnd=\"{_fmt_time(wt.end)}\"/>\n"
                    f"      </par>"
                )
                if wt.end > max_end:
                    max_end = wt.end

        # If no alignment data but we have audio, estimate duration from file
        if not par_elements and ch.aligned_chunks:
            for ac in ch.aligned_chunks:
                if ac.audio_path and os.path.isfile(ac.audio_path):
                    try:
                        max_end += _audio_duration_secs(ac.audio_path)
                    except Exception:
                        pass

        smil = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<smil xmlns="http://www.w3.org/ns/SMIL" version="3.0">\n'
            "  <body>\n"
            f'    <seq id="seq_{ch.num:03d}">\n'
            + "\n".join(par_elements) + "\n"
            "    </seq>\n"
            "  </body>\n"
            "</smil>\n"
        )
        return smil, max_end

    def _build_toc(self) -> str:
        nav_items = []
        for ch in self._chapters.values():
            ch_id = f"chapter_{ch.num:03d}"
            nav_items.append(
                f'      <li><a href="{EPUB_CHAPTER_DIR}/{ch_id}.xhtml">Page {ch.num}</a></li>'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops">\n'
            "<head>\n"
            f"  <title>{escape(self.title)}</title>\n"
            "</head>\n"
            "<body>\n"
            '  <nav epub:type="toc" id="toc">\n'
            "    <h1>Table of Contents</h1>\n"
            "    <ol>\n"
            + "\n".join(nav_items) + "\n"
            "    </ol>\n"
            "  </nav>\n"
            "</body>\n"
            "</html>\n"
        )

    def _build_opf(
        self,
        manifest_items: List[str],
        spine_items: List[str],
        total_duration: float,
        chapter_durations: Dict[int, float],
    ) -> str:
        duration_meta = [
            f'    <meta property="media:duration">{_fmt_time(total_duration)}</meta>',
        ]
        for ch_num, dur in chapter_durations.items():
            duration_meta.append(
                f'    <meta property="media:duration" refines="#smil_{ch_num:03d}">'
                f"{_fmt_time(dur)}</meta>"
            )

        # Add fixed manifest items (toc, css)
        fixed_manifest = [
            '    <item id="toc" href="toc.xhtml" media-type="application/xhtml+xml" '
            'properties="nav"/>',
            '    <item id="style" href="style.css" media-type="text/css"/>',
        ]

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
            f'unique-identifier="bookid">\n'
            "  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">\n"
            f"    <dc:identifier id=\"bookid\">urn:uuid:{self.book_id}</dc:identifier>\n"
            f"    <dc:title>{escape(self.title)}</dc:title>\n"
            f"    <dc:language>{escape(self.language)}</dc:language>\n"
            f'    <meta property="media:active-class">{MEDIA_OVERLAY_ACTIVE_CLASS}</meta>\n'
            + "\n".join(duration_meta) + "\n"
            "  </metadata>\n"
            "  <manifest>\n"
            + "\n".join(fixed_manifest) + "\n"
            + "\n".join(manifest_items) + "\n"
            "  </manifest>\n"
            "  <spine>\n"
            + "\n".join(spine_items) + "\n"
            "  </spine>\n"
            "</package>\n"
        )
