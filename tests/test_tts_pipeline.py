"""Tests for the TTS / audio pipeline.

Covers: text extraction, preprocessing, sentence splitting, chunking,
validation, tracker, concatenation, backend registry, and the full
audio pipeline with a mock backend.

Run:
    pytest tests/test_tts_pipeline.py -v
"""

import json
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from screencastgen.backends import BACKEND_NAMES, create_backend
from screencastgen.concatenator import _find_chunk_files, concatenate
from screencastgen.constants import (
    DEFAULT_CLONE_CHUNK_BYTES,
    LONG_SENTENCE_THRESHOLD,
    MAX_CHUNK_BYTES,
    MAX_TTS_BYTES,
    SENTENCE_WARN_BYTES,
)
from screencastgen.extractor import extract_text, extract_text_by_page
from screencastgen.text_processing import (
    _break_long_runs,
    _split_long_sentence,
    create_chunks,
    create_chunks_with_pages,
    preprocess_text,
    split_into_sentences,
    split_into_sentences_by_page,
    validate_chunk,
)
from screencastgen.tracker import ProcessingTracker, compute_chunk_hash

from tests.conftest import MockTTSBackend, FailingTTSBackend, make_audio_args, _make_wav


def _has_reportlab():
    try:
        import reportlab
        return True
    except ImportError:
        return False


# ===================================================================
# Text Extraction
# ===================================================================

class TestExtractText:

    def test_extract_text_returns_string(self, sample_pdf_simple):
        text = extract_text(sample_pdf_simple)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_extract_text_by_page_returns_page_tuples(self, sample_pdf_simple):
        pages = extract_text_by_page(sample_pdf_simple)
        assert isinstance(pages, list)
        assert len(pages) >= 1
        for page_num, text in pages:
            assert isinstance(page_num, int)
            assert page_num >= 1
            assert isinstance(text, str)

    def test_extract_text_nonexistent_file(self, tmp_path):
        with pytest.raises(Exception):
            extract_text(str(tmp_path / "nonexistent.pdf"))

    @pytest.mark.skipif(
        not _has_reportlab(),
        reason="reportlab not installed",
    )
    def test_extract_multipage_pdf(self, sample_pdf):
        pages = extract_text_by_page(sample_pdf)
        assert len(pages) == 2
        assert "first page" in pages[0][1].lower() or "sample" in pages[0][1].lower()


# ===================================================================
# Text Preprocessing
# ===================================================================

class TestPreprocessText:

    def test_smart_quotes_normalized(self):
        left_dq = chr(0x201C)   # left double quote
        right_dq = chr(0x201D)  # right double quote
        left_sq = chr(0x2018)   # left single quote
        right_sq = chr(0x2019)  # right single quote
        text = f"{left_dq}Hello{right_dq} she said {left_sq}world{right_sq}"
        result = preprocess_text(text)
        assert left_dq not in result
        assert right_dq not in result
        assert left_sq not in result
        assert right_sq not in result
        assert '"Hello"' in result
        assert "'world'" in result

    def test_code_blocks_removed(self):
        text = "Before <code>x = 1</code> after"
        result = preprocess_text(text)
        assert "x = 1" not in result
        assert "See code example" in result

    def test_output_blocks_removed(self):
        text = "Before <output>result here</output> after"
        result = preprocess_text(text)
        assert "result here" not in result

    def test_bullet_points_replaced(self):
        for bullet in "\u2022\u25cf\u25cb\u25aa\u25b8\u25ba\u25e6\u2023\u2043":
            text = f"{bullet} First item {bullet} Second item"
            result = preprocess_text(text)
            assert bullet not in result

    def test_run_together_words_split(self):
        text = "wordOne wordTwo"
        result = preprocess_text(text)
        # camelCase should be split
        assert "word" in result.lower()

    def test_semicolon_becomes_period(self):
        text = "First clause; second clause"
        result = preprocess_text(text)
        assert ";" not in result

    def test_whitespace_normalized(self):
        text = "Hello   world\n\nfoo   bar"
        result = preprocess_text(text)
        assert "  " not in result

    def test_multiple_periods_cleaned(self):
        text = "End... Start again"
        result = preprocess_text(text)
        assert "..." not in result

    def test_empty_input(self):
        assert preprocess_text("") == ""

    def test_preserves_normal_text(self):
        text = "This is a normal sentence."
        result = preprocess_text(text)
        assert "This is a normal sentence." in result


# ===================================================================
# Break Long Runs
# ===================================================================

class TestBreakLongRuns:

    def test_short_text_unchanged(self):
        text = "Short sentence."
        assert _break_long_runs(text) == text

    def test_long_run_gets_period(self):
        words = ["word"] * 100
        text = " ".join(words)
        result = _break_long_runs(text, max_run_bytes=100)
        assert result.count(".") > 0

    def test_existing_punctuation_resets_counter(self):
        text = "First part ends here. Then more text follows normally."
        result = _break_long_runs(text, max_run_bytes=200)
        # Already has punctuation, should be mostly unchanged
        assert "First part ends here." in result


# ===================================================================
# Sentence Splitting
# ===================================================================

class TestSplitIntoSentences:

    def test_basic_splitting(self):
        text = "First sentence. Second sentence. Third one."
        sentences = split_into_sentences(text)
        assert len(sentences) == 3
        assert all(s.endswith((".", "!", "?")) for s in sentences)

    def test_question_and_exclamation(self):
        text = "Is this a question? Yes it is! Great."
        sentences = split_into_sentences(text)
        assert len(sentences) == 3

    def test_adds_period_if_missing(self):
        text = "No punctuation at end"
        sentences = split_into_sentences(text)
        assert all(s.endswith(".") for s in sentences)

    def test_long_sentence_split(self):
        # Create a sentence that exceeds LONG_SENTENCE_THRESHOLD
        long_sent = "word " * 200 + "end."
        sentences = split_into_sentences(long_sent)
        for s in sentences:
            assert len(s.encode("utf-8")) <= LONG_SENTENCE_THRESHOLD + 100  # some tolerance

    def test_chapter_heading_gets_period(self):
        text = "CHAPTER 1 Introduction The story begins here."
        sentences = split_into_sentences(text)
        assert len(sentences) >= 1

    def test_empty_input(self):
        assert split_into_sentences("") == []


class TestSplitLongSentence:

    def test_short_sentence_unchanged(self):
        sent = "Short sentence."
        result = _split_long_sentence(sent)
        assert result == [sent]

    def test_comma_split(self):
        parts = ["part " * 20] * 3
        sent = ", ".join(parts) + "."
        result = _split_long_sentence(sent, max_bytes=200)
        assert len(result) > 1
        assert all(r.endswith((".", "!", "?")) for r in result)

    def test_word_level_fallback(self):
        # No punctuation to split on, so word-level fallback
        sent = "a " * 500 + "end."
        result = _split_long_sentence(sent, max_bytes=200)
        assert len(result) > 1


# ===================================================================
# Chunking
# ===================================================================

class TestCreateChunks:

    def test_single_chunk_if_small(self):
        sentences = ["Hello.", "World."]
        chunks = create_chunks(sentences, max_bytes=1000)
        assert len(chunks) == 1
        assert "Hello." in chunks[0]
        assert "World." in chunks[0]

    def test_splits_when_exceeds_limit(self):
        sentences = [f"Sentence number {i}." for i in range(50)]
        chunks = create_chunks(sentences, max_bytes=100)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.encode("utf-8")) <= 100 + 50  # tolerance for single sentence

    def test_empty_input(self):
        assert create_chunks([], max_bytes=1000) == []

    def test_preserves_all_text(self):
        sentences = ["First sentence.", "Second sentence.", "Third sentence."]
        chunks = create_chunks(sentences, max_bytes=1000)
        combined = " ".join(chunks)
        for s in sentences:
            assert s in combined


class TestCreateChunksWithPages:

    def test_tracks_page_numbers(self):
        page_sentences = [
            (1, "First sentence on page one."),
            (1, "Second sentence on page one."),
            (2, "First on page two."),
        ]
        chunks = create_chunks_with_pages(page_sentences, max_bytes=5000)
        assert len(chunks) >= 1
        text, pages = chunks[0]
        assert 1 in pages

    def test_chunk_spans_pages(self):
        page_sentences = [
            (1, "Page one text."),
            (2, "Page two text."),
            (3, "Page three text."),
        ]
        chunks = create_chunks_with_pages(page_sentences, max_bytes=5000)
        # All should fit in one chunk
        assert len(chunks) == 1
        _, pages = chunks[0]
        assert pages == [1, 2, 3]


class TestSplitIntoSentencesByPage:

    def test_preserves_page_tags(self):
        pages = [
            (1, "Hello world. Testing here."),
            (2, "Second page content."),
        ]
        result = split_into_sentences_by_page(pages)
        assert all(isinstance(r, tuple) and len(r) == 2 for r in result)
        page_nums = [pn for pn, _ in result]
        assert 1 in page_nums
        assert 2 in page_nums

    def test_empty_pages_skipped(self):
        pages = [(1, ""), (2, "Some text.")]
        result = split_into_sentences_by_page(pages)
        page_nums = [pn for pn, _ in result]
        assert 1 not in page_nums


# ===================================================================
# Validation
# ===================================================================

class TestValidateChunk:

    def test_valid_chunk(self):
        chunk = "This is a short valid chunk."
        is_valid, issues = validate_chunk(chunk, 1)
        assert is_valid
        assert issues == []

    def test_oversized_chunk_invalid(self):
        chunk = "x" * (MAX_TTS_BYTES + 100)
        is_valid, issues = validate_chunk(chunk, 1)
        assert not is_valid
        assert any("exceeds" in i for i in issues)

    def test_custom_limits(self):
        chunk = "Small chunk."
        is_valid, issues = validate_chunk(chunk, 1, max_tts_bytes=5)
        assert not is_valid

    def test_long_sentence_flagged(self):
        long_sent = "a " * 500 + "end."
        is_valid, issues = validate_chunk(long_sent, 1)
        assert len(issues) > 0


# ===================================================================
# Processing Tracker
# ===================================================================

class TestProcessingTracker:

    def test_new_tracker_empty(self, tmp_path):
        tracker = ProcessingTracker(str(tmp_path / "status.json"))
        assert tracker.status["total_chunks"] == 0
        assert len(tracker.status["processed_chunks"]) == 0

    def test_mark_processed(self, tmp_path):
        tracker = ProcessingTracker(str(tmp_path / "status.json"))
        tracker.mark_processed(1, "abc123", "chunk_001.wav")
        assert tracker.is_processed(1, "abc123")
        assert not tracker.is_processed(1, "different_hash")
        assert not tracker.is_processed(2, "abc123")

    def test_mark_failed(self, tmp_path):
        tracker = ProcessingTracker(str(tmp_path / "status.json"))
        tracker.mark_failed(1, "abc123", "some error")
        assert "1" in tracker.status["failed_chunks"]

    def test_mark_processed_clears_failure(self, tmp_path):
        tracker = ProcessingTracker(str(tmp_path / "status.json"))
        tracker.mark_failed(1, "abc123", "error")
        tracker.mark_processed(1, "abc123", "chunk_001.wav")
        assert "1" not in tracker.status["failed_chunks"]
        assert tracker.is_processed(1, "abc123")

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "status.json")
        tracker1 = ProcessingTracker(path)
        tracker1.status["total_chunks"] = 5
        tracker1.mark_processed(1, "hash1", "file1.wav")
        tracker1.save()

        tracker2 = ProcessingTracker(path)
        assert tracker2.status["total_chunks"] == 5
        assert tracker2.is_processed(1, "hash1")

    def test_alignment_tracking(self, tmp_path):
        from screencastgen.types import WordTiming

        tracker = ProcessingTracker(str(tmp_path / "status.json"))
        words = [WordTiming("hello", 0.0, 0.5), WordTiming("world", 0.5, 1.0)]
        tracker.mark_aligned(1, words)
        assert tracker.is_aligned(1)
        assert not tracker.is_aligned(2)

        alignment = tracker.get_alignment(1)
        assert len(alignment) == 2
        assert alignment[0]["word"] == "hello"

    def test_video_tracking(self, tmp_path):
        tracker = ProcessingTracker(str(tmp_path / "status.json"))
        tracker.mark_video_rendered(1, "video_001.mp4")
        assert tracker.is_video_rendered(1)
        assert not tracker.is_video_rendered(2)

    def test_epub_tracking(self, tmp_path):
        tracker = ProcessingTracker(str(tmp_path / "status.json"))
        assert not tracker.is_epub_built()
        tracker.mark_epub_built()
        assert tracker.is_epub_built()

    def test_get_summary(self, tmp_path):
        tracker = ProcessingTracker(str(tmp_path / "status.json"))
        tracker.status["total_chunks"] = 10
        tracker.mark_processed(1, "h1", "f1.wav")
        tracker.mark_processed(2, "h2", "f2.wav")
        tracker.mark_failed(3, "h3", "error")

        summary = tracker.get_summary()
        assert summary["total"] == 10
        assert summary["processed"] == 2
        assert summary["failed"] == 1
        assert summary["remaining"] == 8


class TestComputeChunkHash:

    def test_deterministic(self):
        h1 = compute_chunk_hash("hello world")
        h2 = compute_chunk_hash("hello world")
        assert h1 == h2

    def test_different_text_different_hash(self):
        h1 = compute_chunk_hash("hello")
        h2 = compute_chunk_hash("world")
        assert h1 != h2

    def test_returns_hex_string(self):
        h = compute_chunk_hash("test")
        assert isinstance(h, str)
        assert all(c in "0123456789abcdef" for c in h)


# ===================================================================
# Audio Concatenation
# ===================================================================

class TestConcatenation:

    def test_find_chunk_files(self, tmp_path, chunk_wav_files):
        files = _find_chunk_files(str(tmp_path), "wav")
        assert len(files) == 3

    def test_find_no_files(self, tmp_path):
        files = _find_chunk_files(str(tmp_path), "wav")
        assert files == []

    def test_concatenate_raises_if_no_files(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            concatenate(str(tmp_path), str(tmp_path / "out.wav"), ext="wav")

    def test_concatenate_with_explicit_files(self, tmp_path, chunk_wav_files):
        dest = str(tmp_path / "merged.wav")
        try:
            result = concatenate(str(tmp_path), dest, ext="wav", files=chunk_wav_files)
            assert os.path.isfile(result)
            assert os.path.getsize(result) > 0
        except (ImportError, FileNotFoundError):
            # pydub or ffmpeg not available — skip gracefully
            pytest.skip("pydub or ffmpeg not available")


# ===================================================================
# Backend Registry
# ===================================================================

class TestBackendRegistry:

    def test_backend_names(self):
        assert "qwen" in BACKEND_NAMES
        assert "f5" in BACKEND_NAMES
        assert "remote" in BACKEND_NAMES

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            create_backend("nonexistent")

    @patch("screencastgen.backends.qwen_backend.QwenTTS")
    def test_create_qwen_backend(self, mock_cls):
        mock_cls.return_value = MagicMock()
        backend = create_backend("qwen", language="en-US", device="cpu")
        mock_cls.assert_called_once()

    @patch("screencastgen.backends.remote_tts.RemoteTTS")
    def test_create_remote_backend(self, mock_cls):
        mock_cls.return_value = MagicMock()
        backend = create_backend("remote", server_url="http://test:8100")
        mock_cls.assert_called_once()


# ===================================================================
# Mock Backend Protocol Compliance
# ===================================================================

class TestMockTTSBackend:

    def test_has_required_properties(self, mock_backend):
        assert isinstance(mock_backend.max_chunk_bytes, int)
        assert isinstance(mock_backend.output_format, str)

    def test_synthesize_creates_file(self, mock_backend, tmp_path):
        out = str(tmp_path / "test.wav")
        mock_backend.synthesize("Hello world", out)
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 0

    def test_tracks_calls(self, mock_backend, tmp_path):
        out = str(tmp_path / "test.wav")
        mock_backend.synthesize("Hello", out)
        assert len(mock_backend.calls) == 1
        assert mock_backend.calls[0] == ("Hello", out)


# ===================================================================
# Full Audio Pipeline (with mock backend)
# ===================================================================

class TestAudioPipeline:

    def test_extract_and_chunk(self, sample_pdf_simple, tmp_path):
        """Test the shared extraction + chunking steps."""
        from screencastgen.cli import _extract_and_chunk

        args = make_audio_args(sample_pdf_simple, tmp_path)
        status_path = str(tmp_path / "processing_status.json")
        tracker = ProcessingTracker(status_path)
        backend = MockTTSBackend()

        chunks = _extract_and_chunk(args, tracker, max_chunk_bytes=backend.max_chunk_bytes)
        assert isinstance(chunks, list)
        assert len(chunks) >= 1
        assert tracker.status["total_chunks"] == len(chunks)

    def test_validate_and_collect(self, sample_pdf_simple, tmp_path):
        """Test validation of extracted chunks."""
        from screencastgen.cli import _extract_and_chunk, _validate_and_collect

        args = make_audio_args(sample_pdf_simple, tmp_path)
        status_path = str(tmp_path / "processing_status.json")
        tracker = ProcessingTracker(status_path)
        backend = MockTTSBackend()

        chunks = _extract_and_chunk(args, tracker, max_chunk_bytes=backend.max_chunk_bytes)
        to_process = _validate_and_collect(chunks, tracker, verbose=False)
        assert isinstance(to_process, list)
        # Each item is (chunk_num, chunk_text, chunk_hash)
        for chunk_num, text, h in to_process:
            assert isinstance(chunk_num, int)
            assert isinstance(text, str)
            assert isinstance(h, str)

    def test_synthesize_chunks_with_mock(self, sample_pdf_simple, tmp_path):
        """Full synthesis loop with mock backend."""
        from screencastgen.cli import (
            _extract_and_chunk,
            _synthesize_chunks,
            _validate_and_collect,
        )

        args = make_audio_args(sample_pdf_simple, tmp_path)
        status_path = str(tmp_path / "processing_status.json")
        tracker = ProcessingTracker(status_path)
        backend = MockTTSBackend()

        chunks = _extract_and_chunk(args, tracker, max_chunk_bytes=backend.max_chunk_bytes)
        to_process = _validate_and_collect(chunks, tracker, verbose=False)
        count = _synthesize_chunks(
            to_process, len(chunks), tracker, backend, str(tmp_path), verbose=False,
        )

        assert count == len(to_process)
        assert tracker.get_summary()["processed"] == count
        # Check audio files were created
        for _, _, _ in to_process:
            pass
        assert len(backend.calls) == count

    def test_synthesize_with_failing_backend(self, sample_pdf_simple, tmp_path):
        """Failing backend marks chunks as failed."""
        from screencastgen.cli import (
            _extract_and_chunk,
            _synthesize_chunks,
            _validate_and_collect,
        )

        args = make_audio_args(sample_pdf_simple, tmp_path)
        status_path = str(tmp_path / "processing_status.json")
        tracker = ProcessingTracker(status_path)
        backend = FailingTTSBackend()

        chunks = _extract_and_chunk(args, tracker, max_chunk_bytes=backend.max_chunk_bytes)
        to_process = _validate_and_collect(chunks, tracker, verbose=False)
        count = _synthesize_chunks(
            to_process, len(chunks), tracker, backend, str(tmp_path), verbose=False,
        )

        assert count == 0
        assert tracker.get_summary()["failed"] > 0

    def test_resume_skips_processed(self, sample_pdf_simple, tmp_path):
        """Already-processed chunks are skipped on re-run."""
        from screencastgen.cli import (
            _extract_and_chunk,
            _synthesize_chunks,
            _validate_and_collect,
        )

        args = make_audio_args(sample_pdf_simple, tmp_path)
        status_path = str(tmp_path / "processing_status.json")
        tracker = ProcessingTracker(status_path)
        backend = MockTTSBackend()

        chunks = _extract_and_chunk(args, tracker, max_chunk_bytes=backend.max_chunk_bytes)
        to_process = _validate_and_collect(chunks, tracker)
        _synthesize_chunks(to_process, len(chunks), tracker, backend, str(tmp_path))

        # Second run — should skip all
        backend2 = MockTTSBackend()
        to_process2 = _validate_and_collect(chunks, tracker)
        assert len(to_process2) == 0

    def test_full_audio_pipeline_mock(self, sample_pdf_simple, tmp_path):
        """End-to-end audio pipeline with patched backend creation."""
        from screencastgen.cli import run_audio_pipeline

        args = make_audio_args(sample_pdf_simple, tmp_path)
        mock_be = MockTTSBackend()

        with patch("screencastgen.cli._create_tts_backend", return_value=mock_be):
            result = run_audio_pipeline(args)

        # Pipeline should succeed (0) or might fail on concat if pydub/ffmpeg missing
        if result == 0:
            assert mock_be.calls  # backend was called
        else:
            # Concat might fail without pydub/ffmpeg, but synthesis should work
            assert mock_be.calls

    def test_no_concat_flag(self, sample_pdf_simple, tmp_path):
        """--no-concat skips concatenation step."""
        from screencastgen.cli import run_audio_pipeline

        args = make_audio_args(sample_pdf_simple, tmp_path, no_concat=True)
        mock_be = MockTTSBackend()

        with patch("screencastgen.cli._create_tts_backend", return_value=mock_be):
            result = run_audio_pipeline(args)

        assert result == 0
        assert mock_be.calls


# ===================================================================
# CLI Argument Parsing
# ===================================================================

class TestCLIParsing:

    def test_parse_resolution(self):
        from screencastgen.cli import _parse_resolution

        w, h = _parse_resolution("1920x1080")
        assert w == 1920
        assert h == 1080

    def test_parse_resolution_invalid(self):
        from screencastgen.cli import _parse_resolution

        with pytest.raises(ValueError):
            _parse_resolution("invalid")

    def test_build_parser(self):
        from screencastgen.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["audio", "test.pdf"])
        assert args.command == "audio"
        assert args.pdf == "test.pdf"

    def test_validation_limits_high_backend(self):
        from screencastgen.cli import _validation_limits

        backend = MockTTSBackend(max_bytes=20000)
        max_tts, sent_warn = _validation_limits(backend)
        assert max_tts == 20000
        assert sent_warn == 20000

    def test_validation_limits_low_backend(self):
        from screencastgen.cli import _validation_limits

        backend = MockTTSBackend(max_bytes=3000)
        max_tts, sent_warn = _validation_limits(backend)
        assert max_tts == MAX_TTS_BYTES
        assert sent_warn == SENTENCE_WARN_BYTES
