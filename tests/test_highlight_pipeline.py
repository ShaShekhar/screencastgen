"""Tests for the highlight (word-highlighted video) pipeline.

Covers: HighlightRenderer (layout, rendering, scrolling, active word),
audio alignment (mocked), and the highlight video composition pipeline.

Run:
    pytest tests/test_highlight_pipeline.py -v
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from screencastgen.types import AlignedChunk, WordTiming

# HighlightRenderer requires Pillow — skip entire module if unavailable
PIL = pytest.importorskip("PIL", reason="Pillow not installed")

from screencastgen.highlight_renderer import HighlightRenderer, _load_font
from tests.conftest import MockTTSBackend, make_highlight_args, _make_wav


# ===================================================================
# Font Loading
# ===================================================================

class TestLoadFont:

    def test_returns_font_object(self):
        font = _load_font(24)
        # Should return either a TrueType or default font
        assert font is not None

    def test_different_sizes(self):
        f1 = _load_font(12)
        f2 = _load_font(48)
        assert f1 is not None
        assert f2 is not None


# ===================================================================
# HighlightRenderer Initialization
# ===================================================================

class TestHighlightRendererInit:

    def test_default_parameters(self):
        r = HighlightRenderer()
        assert r.width == 1280
        assert r.height == 720
        assert r.font_size == 32
        assert r.highlight_color == (255, 255, 0)
        assert r.text_color == (255, 255, 255)
        assert r.bg_color == (30, 30, 30)
        assert r.margin == 40

    def test_custom_parameters(self):
        r = HighlightRenderer(
            width=800, height=600, font_size=24,
            highlight_color=(255, 0, 0),
            text_color=(0, 0, 0),
            bg_color=(255, 255, 255),
            margin=20,
        )
        assert r.width == 800
        assert r.height == 600
        assert r.font_size == 24
        assert r.margin == 20


# ===================================================================
# Word Layout
# ===================================================================

class TestLayoutWords:

    @pytest.fixture
    def renderer(self):
        return HighlightRenderer(width=800, height=600, font_size=24)

    def test_layout_returns_list_of_dicts(self, renderer):
        words = ["Hello", "world", "test"]
        layout = renderer.layout_words(words)
        assert isinstance(layout, list)
        assert len(layout) == 3
        for item in layout:
            assert "word" in item
            assert "index" in item
            assert "x" in item
            assert "y" in item
            assert "width" in item
            assert "line" in item

    def test_indices_match_input(self, renderer):
        words = ["alpha", "beta", "gamma"]
        layout = renderer.layout_words(words)
        indices = [item["index"] for item in layout]
        assert indices == [0, 1, 2]

    def test_words_match_input(self, renderer):
        words = ["Hello", "world"]
        layout = renderer.layout_words(words)
        assert [item["word"] for item in layout] == words

    def test_x_positions_increase(self, renderer):
        words = ["a", "b", "c"]
        layout = renderer.layout_words(words)
        # Within same line, x should increase
        same_line = [item for item in layout if item["line"] == 0]
        for i in range(1, len(same_line)):
            assert same_line[i]["x"] > same_line[i - 1]["x"]

    def test_long_text_wraps(self, renderer):
        words = ["word"] * 50
        layout = renderer.layout_words(words)
        lines = set(item["line"] for item in layout)
        assert len(lines) > 1  # Should wrap to multiple lines

    def test_empty_input(self, renderer):
        layout = renderer.layout_words([])
        assert layout == []

    def test_single_word(self, renderer):
        layout = renderer.layout_words(["hello"])
        assert len(layout) == 1
        assert layout[0]["index"] == 0
        assert layout[0]["line"] == 0


# ===================================================================
# Frame Rendering
# ===================================================================

class TestRenderFrame:

    @pytest.fixture
    def renderer(self):
        return HighlightRenderer(width=640, height=480, font_size=20)

    def test_returns_pil_image(self, renderer):
        words = ["Hello", "world"]
        layout = renderer.layout_words(words)
        img = renderer.render_frame(layout)
        assert isinstance(img, PIL.Image.Image)

    def test_image_dimensions(self, renderer):
        layout = renderer.layout_words(["test"])
        img = renderer.render_frame(layout)
        assert img.size == (640, 480)

    def test_render_with_active_word(self, renderer):
        words = ["Hello", "world", "test"]
        layout = renderer.layout_words(words)
        img_none = renderer.render_frame(layout, active_index=None)
        img_active = renderer.render_frame(layout, active_index=1)
        # Both should be valid images but visually different
        assert img_none.size == img_active.size
        # Check pixels differ (highlight should change colors)
        assert img_none.tobytes() != img_active.tobytes()

    def test_render_with_scroll_offset(self, renderer):
        words = ["word"] * 100  # lots of words to fill the frame
        layout = renderer.layout_words(words)
        img_no_scroll = renderer.render_frame(layout, scroll_offset=0)
        img_scrolled = renderer.render_frame(layout, scroll_offset=200)
        # Scrolled image should differ
        assert img_no_scroll.tobytes() != img_scrolled.tobytes()

    def test_render_empty_layout(self, renderer):
        img = renderer.render_frame([])
        assert isinstance(img, PIL.Image.Image)
        assert img.size == (640, 480)

    def test_bg_color_fills_frame(self, renderer):
        img = renderer.render_frame([])
        # Sample a pixel from the center — should be the bg color
        pixel = img.getpixel((320, 240))
        assert pixel == renderer.bg_color


# ===================================================================
# Scroll Offset
# ===================================================================

class TestComputeScrollOffset:

    @pytest.fixture
    def renderer(self):
        return HighlightRenderer(width=800, height=400, font_size=24)

    def test_no_active_word(self, renderer):
        layout = renderer.layout_words(["hello"])
        offset = renderer.compute_scroll_offset(layout, None)
        assert offset == 0

    def test_first_word_no_scroll(self, renderer):
        words = ["first", "second", "third"]
        layout = renderer.layout_words(words)
        offset = renderer.compute_scroll_offset(layout, 0)
        # First word is near top, offset should be 0 (clamped)
        assert offset >= 0

    def test_scroll_for_bottom_word(self, renderer):
        words = ["word"] * 100  # Force many lines
        layout = renderer.layout_words(words)
        last_idx = len(words) - 1
        offset = renderer.compute_scroll_offset(layout, last_idx)
        assert offset > 0

    def test_nonexistent_index_returns_zero(self, renderer):
        layout = renderer.layout_words(["hello"])
        offset = renderer.compute_scroll_offset(layout, 999)
        assert offset == 0


# ===================================================================
# Active Word Index
# ===================================================================

class TestGetActiveWordIndex:

    @pytest.fixture
    def renderer(self):
        return HighlightRenderer()

    @pytest.fixture
    def words(self):
        return [
            WordTiming("Hello", 0.0, 0.5),
            WordTiming("world", 0.6, 1.0),
            WordTiming("test", 1.1, 1.5),
        ]

    def test_exact_start(self, renderer, words):
        idx = renderer.get_active_word_index(words, 0.0)
        assert idx == 0

    def test_exact_end(self, renderer, words):
        idx = renderer.get_active_word_index(words, 0.5)
        assert idx == 0

    def test_mid_word(self, renderer, words):
        idx = renderer.get_active_word_index(words, 0.8)
        assert idx == 1

    def test_between_words(self, renderer, words):
        # 0.55 is between word 0 (ends 0.5) and word 1 (starts 0.6)
        idx = renderer.get_active_word_index(words, 0.55)
        # Should return last word that ended before this time
        assert idx == 0

    def test_after_all_words(self, renderer, words):
        idx = renderer.get_active_word_index(words, 10.0)
        assert idx == 2  # Last word

    def test_before_all_words(self, renderer, words):
        # Negative time — no words started yet
        idx = renderer.get_active_word_index(words, -1.0)
        assert idx is None

    def test_empty_words(self, renderer):
        idx = renderer.get_active_word_index([], 0.5)
        assert idx is None

    def test_single_word(self, renderer):
        words = [WordTiming("only", 0.0, 1.0)]
        assert renderer.get_active_word_index(words, 0.5) == 0
        assert renderer.get_active_word_index(words, 1.5) == 0


# ===================================================================
# Alignment (mocked WhisperX)
# ===================================================================

class TestAlignChunkMocked:

    def test_align_returns_word_timings(self):
        """Test alignment function with fully mocked WhisperX."""
        mock_words = [
            {"word": "Hello", "start": 0.0, "end": 0.3},
            {"word": "world", "start": 0.4, "end": 0.8},
        ]
        mock_result = {"word_segments": mock_words}

        mock_whisperx = MagicMock()
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"segments": []}
        mock_whisperx.load_model.return_value = mock_model
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.align.return_value = mock_result

        with patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            from screencastgen.aligner import align_chunk
            words = align_chunk("/fake/audio.wav", "Hello world", device="cpu")

        assert len(words) == 2
        assert words[0].word == "Hello"
        assert words[0].start == 0.0
        assert words[0].end == 0.3
        assert words[1].word == "world"

    def test_align_handles_nested_segments(self):
        """WhisperX sometimes returns words nested inside segments."""
        mock_result = {
            "segments": [{
                "words": [
                    {"word": "Test", "start": 0.0, "end": 0.5},
                    {"word": "sentence", "start": 0.5, "end": 1.0},
                ]
            }]
        }

        mock_whisperx = MagicMock()
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"segments": []}
        mock_whisperx.load_model.return_value = mock_model
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.align.return_value = mock_result

        with patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            from screencastgen.aligner import align_chunk
            words = align_chunk("/fake/audio.wav", "Test sentence", device="cpu")

        assert len(words) == 2
        assert words[0].word == "Test"
        assert words[1].word == "sentence"


# ===================================================================
# Highlight Pipeline Integration (mocked)
# ===================================================================

class TestHighlightPipelineIntegration:

    def test_align_chunks_with_tracker(self, sample_pdf_simple, tmp_path):
        """Test _align_chunks with pre-synthesized data and mocked aligner."""
        from screencastgen.cli import (
            _align_chunks,
            _extract_and_chunk,
            _synthesize_chunks,
            _validate_and_collect,
        )
        from screencastgen.tracker import ProcessingTracker

        args = make_highlight_args(sample_pdf_simple, tmp_path)
        status_path = str(tmp_path / "processing_status.json")
        tracker = ProcessingTracker(status_path)
        backend = MockTTSBackend()

        chunks = _extract_and_chunk(args, tracker, max_chunk_bytes=backend.max_chunk_bytes)
        to_process = _validate_and_collect(chunks, tracker)
        _synthesize_chunks(to_process, len(chunks), tracker, backend, str(tmp_path))

        # Mock the aligner — create a mock module so the lazy import succeeds
        mock_words = [
            WordTiming("Hello", 0.0, 0.3),
            WordTiming("world", 0.4, 0.8),
        ]
        mock_aligner = MagicMock()
        mock_aligner.align_chunk = MagicMock(return_value=mock_words)
        with patch.dict("sys.modules", {"screencastgen.aligner": mock_aligner}):
            aligned = _align_chunks(chunks, tracker, args)

        assert len(aligned) > 0
        for ac in aligned:
            assert isinstance(ac, AlignedChunk)
            assert ac.audio_path
            assert len(ac.words) > 0

    def test_highlight_video_composition_mock(self, sample_aligned_chunks, tmp_path):
        """Test compose_highlight_video with mocked moviepy."""
        renderer = HighlightRenderer(width=640, height=480, font_size=20)
        output_path = str(tmp_path / "highlight.mp4")

        # Mock moviepy internals — patch at moviepy module since imports are deferred
        mock_video_clip = MagicMock()
        mock_video_clip.with_fps.return_value = mock_video_clip
        mock_video_clip.with_audio.return_value = mock_video_clip
        mock_video_clip.close.return_value = None

        mock_final = MagicMock()
        mock_final.write_videofile.return_value = None
        mock_final.close.return_value = None

        mock_moviepy = MagicMock()
        mock_moviepy.VideoClip = MagicMock(return_value=mock_video_clip)
        mock_moviepy.AudioFileClip = MagicMock()
        mock_moviepy.concatenate_videoclips = MagicMock(return_value=mock_final)

        with patch.dict("sys.modules", {"moviepy": mock_moviepy}), \
             patch("screencastgen.video_composer._get_audio_duration", return_value=1.5):
            import screencastgen.video_composer as vc
            result = vc.compose_highlight_video(
                sample_aligned_chunks, renderer, output_path, fps=24,
            )

        assert result == output_path
        mock_final.write_videofile.assert_called_once()

    def test_full_highlight_pipeline_mock(self, sample_pdf_simple, tmp_path):
        """End-to-end highlight pipeline with all heavy deps mocked."""
        from screencastgen.cli import run_highlight_pipeline

        args = make_highlight_args(sample_pdf_simple, tmp_path, format="mp4")
        mock_be = MockTTSBackend()
        mock_words = [WordTiming("test", 0.0, 0.5)]

        mock_video_clip = MagicMock()
        mock_video_clip.with_fps.return_value = mock_video_clip
        mock_video_clip.with_audio.return_value = mock_video_clip
        mock_video_clip.close.return_value = None

        mock_final = MagicMock()
        mock_final.write_videofile.return_value = None
        mock_final.close.return_value = None

        mock_moviepy = MagicMock()
        mock_moviepy.VideoClip = MagicMock(return_value=mock_video_clip)
        mock_moviepy.AudioFileClip = MagicMock()
        mock_moviepy.concatenate_videoclips = MagicMock(return_value=mock_final)

        with patch("screencastgen.cli._create_tts_backend", return_value=mock_be), \
             patch("screencastgen.aligner.align_chunk", return_value=mock_words), \
             patch.dict("sys.modules", {"moviepy": mock_moviepy}), \
             patch("screencastgen.video_composer._get_audio_duration", return_value=1.0):
            result = run_highlight_pipeline(args)

        assert result == 0


# ===================================================================
# Renderer Width Adjustment (used in lipsync composition)
# ===================================================================

class TestRendererWidthAdjustment:

    def test_layout_respects_width(self):
        r = HighlightRenderer(width=400, height=300, font_size=20)
        words = ["word"] * 30
        layout_wide = r.layout_words(words)

        r.width = 200
        layout_narrow = r.layout_words(words)

        # Narrow layout should have more lines
        wide_lines = max(item["line"] for item in layout_wide) + 1
        narrow_lines = max(item["line"] for item in layout_narrow) + 1
        assert narrow_lines >= wide_lines
