"""Render actual PDF pages with per-word highlighting.

This renderer replaces :class:`HighlightRenderer` for the MP4 pipeline when
the input is a PDF.  Instead of re-rendering extracted text on a plain
background, it rasterises each PDF page and draws a semi-transparent
highlight rectangle over the active word's bounding box.

The class exposes the same interface that :mod:`video_composer` expects
(``layout_words``, ``render_frame``, ``get_active_word_index``,
``compute_scroll_offset``, plus ``width``/``height`` attributes).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from .types import BBox, WordTiming


class PageRenderer:
    """Renders PDF page images with word-level highlighting."""

    def __init__(
        self,
        pdf_path: str,
        width: int = 1280,
        height: int = 720,
        highlight_color: Tuple[int, int, int, int] = (255, 255, 0, 100),
        bg_color: Tuple[int, int, int] = (30, 30, 30),
    ):
        self.pdf_path = pdf_path
        self.width = width
        self.height = height
        self.highlight_color = highlight_color
        self.bg_color = bg_color

        # (page_num, width, height) -> (scaled PIL Image, scale, x_offset, y_offset)
        self._page_cache: Dict[Tuple[int, int, int], Tuple[Image.Image, float, int, int]] = {}

    # -- page image cache -----------------------------------------------------

    def _get_page(self, page_num: int) -> Tuple[Image.Image, float, int, int]:
        """Return ``(image, scale, x_offset, y_offset)`` for *page_num*.

        The image is scaled to fit within ``(self.width, self.height)`` while
        preserving aspect ratio, then centered (letterboxed).
        """
        cache_key = (page_num, self.width, self.height)
        if cache_key in self._page_cache:
            return self._page_cache[cache_key]

        from .extractor import render_page_image_with_zoom

        # Oversample relative to the target frame width so the final page image
        # stays sharp after the fit-to-frame resize.
        raw, zoom = render_page_image_with_zoom(
            self.pdf_path,
            page_num,
            target_width=self.width * 2,
        )
        raw_w, raw_h = raw.size

        # Fit inside (self.width, self.height) preserving aspect ratio
        scale_w = self.width / raw_w
        scale_h = self.height / raw_h
        scale = min(scale_w, scale_h)

        new_w = max(1, int(raw_w * scale))
        new_h = max(1, int(raw_h * scale))
        scaled = raw.resize((new_w, new_h), Image.LANCZOS)

        # Center on a background-colored canvas
        canvas = Image.new("RGB", (self.width, self.height), self.bg_color)
        x_off = (self.width - new_w) // 2
        y_off = (self.height - new_h) // 2
        canvas.paste(scaled, (x_off, y_off))

        # PDF coordinates first scale into raster pixels via ``zoom`` and then
        # into the fitted frame via ``scale``.
        point_scale = zoom * scale
        self._page_cache[cache_key] = (canvas, point_scale, x_off, y_off)
        return canvas, point_scale, x_off, y_off

    # -- public interface (matches HighlightRenderer) -------------------------

    def layout_words(self, words) -> List[dict]:
        """Build a layout list from *words*.

        Accepts ``List[WordTiming]`` (preferred — uses bbox data) or
        ``List[str]`` (fallback — no positional data).
        """
        layout: List[dict] = []
        if not words:
            return layout

        if hasattr(words[0], "word"):
            # WordTiming objects
            for idx, wt in enumerate(words):
                entry: dict = {"word": wt.word, "index": idx, "line": 0}
                if wt.bbox is not None:
                    page_num = wt.bbox.page
                    _, scale, x_off, y_off = self._get_page(page_num)
                    entry["x"] = wt.bbox.x0 * scale + x_off
                    entry["y"] = wt.bbox.y0 * scale + y_off
                    entry["width"] = (wt.bbox.x1 - wt.bbox.x0) * scale
                    entry["height"] = (wt.bbox.y1 - wt.bbox.y0) * scale
                    entry["page"] = page_num
                else:
                    entry["x"] = 0
                    entry["y"] = 0
                    entry["width"] = 0
                    entry["height"] = 0
                    entry["page"] = 0
                layout.append(entry)
        else:
            # Plain strings — no bbox available
            for idx, w in enumerate(words):
                layout.append({
                    "word": w,
                    "index": idx,
                    "x": 0,
                    "y": 0,
                    "width": 0,
                    "height": 0,
                    "line": 0,
                    "page": 0,
                })
        return layout

    def render_frame(
        self,
        layout: List[dict],
        active_index: Optional[int] = None,
        scroll_offset: int = 0,
    ) -> Image.Image:
        """Render the PDF page for the active word with a highlight overlay."""
        # Determine which page to show
        page_num = self._resolve_page(layout, active_index)
        if page_num == 0:
            # No page info — return blank frame
            return Image.new("RGB", (self.width, self.height), self.bg_color)

        base_img, scale, x_off, y_off = self._get_page(page_num)
        frame = base_img.copy()

        if active_index is not None and 0 <= active_index < len(layout):
            item = layout[active_index]
            if item.get("page") == page_num and item.get("width", 0) > 0:
                # Draw semi-transparent highlight rectangle
                overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                pad = 2
                x0 = int(item["x"]) - pad
                y0 = int(item["y"]) - pad
                x1 = int(item["x"] + item["width"]) + pad
                y1 = int(item["y"] + item["height"]) + pad
                draw.rectangle([x0, y0, x1, y1], fill=self.highlight_color)
                frame = Image.alpha_composite(frame.convert("RGBA"), overlay)
                frame = frame.convert("RGB")

        return frame

    def get_active_word_index(
        self, words: List[WordTiming], time: float
    ) -> Optional[int]:
        """Return the index of the word being spoken at *time* seconds."""
        for i, w in enumerate(words):
            if w.start <= time <= w.end:
                return i
        # Between words: return the last word that ended before this time
        for i in range(len(words) - 1, -1, -1):
            if words[i].end <= time:
                return i
        return None

    def compute_scroll_offset(
        self, layout: List[dict], active_index: Optional[int]
    ) -> int:
        """Page images are pre-scaled to fit the frame — no scrolling needed."""
        return 0

    # -- helpers --------------------------------------------------------------

    def _resolve_page(self, layout: List[dict], active_index: Optional[int]) -> int:
        """Determine which page to display based on the active word."""
        if active_index is not None and 0 <= active_index < len(layout):
            page = layout[active_index].get("page", 0)
            if page > 0:
                return page

        # Fallback: find the most recent word that has a page
        if active_index is not None:
            for i in range(min(active_index, len(layout) - 1), -1, -1):
                page = layout[i].get("page", 0)
                if page > 0:
                    return page

        # Last resort: first word with a page
        for item in layout:
            page = item.get("page", 0)
            if page > 0:
                return page

        return 0
