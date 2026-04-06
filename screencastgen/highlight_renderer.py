"""Render text frames with word-by-word highlighting using Pillow."""

import os
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .types import WordTiming


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a monospace font, falling back to default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class HighlightRenderer:
    """Renders text frames with per-word highlighting."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        font_size: int = 32,
        highlight_color: Tuple[int, int, int] = (255, 255, 0),
        text_color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (30, 30, 30),
        margin: int = 40,
    ):
        self.width = width
        self.height = height
        self.font_size = font_size
        self.highlight_color = highlight_color
        self.text_color = text_color
        self.bg_color = bg_color
        self.margin = margin
        self.font = _load_font(font_size)

    def _word_wrap(self, words: List[str]) -> List[List[Tuple[str, int]]]:
        """Wrap words into lines that fit within the frame width.

        Returns list of lines, where each line is a list of (word, word_index).
        """
        max_width = self.width - 2 * self.margin
        lines: List[List[Tuple[str, int]]] = []
        current_line: List[Tuple[str, int]] = []
        current_width = 0
        space_width = self.font.getlength(" ")

        for idx, word in enumerate(words):
            word_width = self.font.getlength(word)
            needed = word_width + (space_width if current_line else 0)

            if current_width + needed > max_width and current_line:
                lines.append(current_line)
                current_line = [(word, idx)]
                current_width = word_width
            else:
                current_line.append((word, idx))
                current_width += needed

        if current_line:
            lines.append(current_line)

        return lines

    def _get_line_height(self) -> int:
        bbox = self.font.getbbox("Ag")
        return int((bbox[3] - bbox[1]) * 1.5)

    def layout_words(self, words: List[str]) -> List[dict]:
        """Compute pixel positions for each word.

        Returns list of dicts: {word, index, x, y, width, line}.
        """
        lines = self._word_wrap(words)
        line_height = self._get_line_height()
        space_width = self.font.getlength(" ")

        layout = []
        for line_idx, line in enumerate(lines):
            x = self.margin
            y = self.margin + line_idx * line_height
            for word, word_idx in line:
                word_width = self.font.getlength(word)
                layout.append({
                    "word": word,
                    "index": word_idx,
                    "x": x,
                    "y": y,
                    "width": word_width,
                    "line": line_idx,
                })
                x += word_width + space_width

        return layout

    def render_frame(
        self,
        layout: List[dict],
        active_index: Optional[int] = None,
        scroll_offset: int = 0,
    ) -> Image.Image:
        """Render a single frame with the active word highlighted.

        Args:
            layout: Word layout from layout_words().
            active_index: Index of the currently spoken word (highlighted).
            scroll_offset: Vertical pixel offset for scrolling long texts.
        """
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        line_height = self._get_line_height()

        for item in layout:
            y = item["y"] - scroll_offset
            # Skip words outside visible area
            if y + line_height < 0 or y > self.height:
                continue

            is_active = item["index"] == active_index
            if is_active:
                # Draw highlight background
                pad = 4
                draw.rectangle(
                    [item["x"] - pad, y - pad,
                     item["x"] + item["width"] + pad, y + line_height - pad],
                    fill=self.highlight_color,
                )
                draw.text((item["x"], y), item["word"], font=self.font, fill=self.bg_color)
            else:
                draw.text((item["x"], y), item["word"], font=self.font, fill=self.text_color)

        return img

    def compute_scroll_offset(self, layout: List[dict], active_index: Optional[int]) -> int:
        """Compute scroll offset to keep the active word vertically centered."""
        if active_index is None:
            return 0

        for item in layout:
            if item["index"] == active_index:
                line_height = self._get_line_height()
                word_center_y = item["y"] + line_height // 2
                visible_center = self.height // 2
                offset = word_center_y - visible_center
                return max(0, offset)

        return 0

    def get_active_word_index(self, words: List[WordTiming], time: float) -> Optional[int]:
        """Return the index of the word being spoken at *time* seconds."""
        for i, w in enumerate(words):
            if w.start <= time <= w.end:
                return i
        # Between words: return the last word that ended before this time
        for i in range(len(words) - 1, -1, -1):
            if words[i].end <= time:
                return i
        return None
