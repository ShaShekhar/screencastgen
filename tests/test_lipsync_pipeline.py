"""Tests for the lip-sync video pipeline.

Covers: lipsync video generation (mocked), video composition with
face + text layout, and the full lipsync pipeline integration.

Run:
    pytest tests/test_lipsync_pipeline.py -v
"""

import json
import os
import subprocess
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from screencastgen.types import AlignedChunk, WordTiming

# Pillow is required for HighlightRenderer used in lipsync composition
PIL = pytest.importorskip("PIL", reason="Pillow not installed")

from screencastgen.highlight_renderer import HighlightRenderer
from tests.conftest import MockTTSBackend, make_lipsync_args, _make_wav


# ===================================================================
# Lipsync Module — Device Resolution
# ===================================================================

class TestLipsyncDeviceResolution:

    def test_explicit_device(self):
        from screencastgen.lipsync import _resolve_device

        assert _resolve_device("cpu") == "cpu"
        assert _resolve_device("cuda") == "cuda"

    def test_auto_device_without_torch(self):
        import builtins

        from screencastgen.lipsync import _resolve_device

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("torch unavailable")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            assert _resolve_device("auto") == "cpu"


# ===================================================================
# Audio Duration Helper
# ===================================================================

class TestGetAudioDuration:

    def test_get_duration_with_pydub(self, sample_wav):
        """Test _get_audio_duration from video_composer (pydub path)."""
        from screencastgen.video_composer import _get_audio_duration

        try:
            dur = _get_audio_duration(sample_wav)
            assert isinstance(dur, float)
            assert 0.8 < dur < 1.2  # 1-second wav with some tolerance
        except (ImportError, Exception):
            pytest.skip("pydub or ffmpeg not available")

    def test_get_duration_ffprobe_fallback(self, sample_wav):
        """Test ffprobe fallback in lipsync module."""
        from screencastgen.lipsync import _get_audio_duration

        mock_result = MagicMock()
        mock_result.stdout = "1.000000\n"
        with patch("screencastgen.lipsync.subprocess.run", return_value=mock_result):
            dur = _get_audio_duration(sample_wav)
        assert dur == 1.0


# ===================================================================
# Video Looping
# ===================================================================

class TestLoopVideo:

    def test_loop_video_calls_ffmpeg(self, tmp_path):
        from screencastgen.lipsync import _loop_video_to_duration

        input_video = str(tmp_path / "face.mp4")
        output_video = str(tmp_path / "looped.mp4")

        with patch("screencastgen.lipsync.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _loop_video_to_duration(input_video, 5.0, output_video)

        assert result == output_video
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd_args
        assert "-stream_loop" in cmd_args
        assert "5.0" in cmd_args


# ===================================================================
# Lip-Sync Video Generation (mocked)
# ===================================================================

class TestLipsyncProviderRegistry:

    def test_only_supported_providers_are_registered(self):
        from screencastgen.providers.lipsync import get_lipsync_provider_names

        assert get_lipsync_provider_names() == ["auto", "latentsync"]

    def test_latentsync_spec_uses_standard_callable(self):
        from screencastgen.providers.lipsync import get_lipsync_provider_spec

        spec = get_lipsync_provider_spec("latentsync")
        assert spec.function_name == "run_latentsync"


class TestGenerateLipsyncVideo:

    def test_auto_uses_latentsync(self, tmp_path):
        """Auto mode should select LatentSync."""
        from screencastgen.lipsync import generate_lipsync_video

        audio = str(tmp_path / "audio.wav")
        _make_wav(audio, duration_s=1.0)
        ref_video = str(tmp_path / "face.mp4")
        # Create a fake video file
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)
        output = str(tmp_path / "output.mp4")

        mock_duration = MagicMock()
        mock_duration.stdout = "1.0\n"

        with patch("screencastgen.lipsync._get_audio_duration", return_value=1.0), \
             patch("screencastgen.lipsync._loop_video_to_duration") as mock_loop, \
             patch("screencastgen.lipsync.run_lipsync_provider") as mock_ls, \
             patch("screencastgen.lipsync.os.path.exists", return_value=True), \
             patch("screencastgen.lipsync.os.unlink"):

            mock_loop.return_value = str(tmp_path / "looped.mp4")
            result = generate_lipsync_video(audio, ref_video, output, device="cpu")

        mock_ls.assert_called_once()
        provider_args, provider_kwargs = mock_ls.call_args
        assert provider_args[0] == "latentsync"
        assert provider_args[2:] == (audio, output)
        assert provider_kwargs == {"device": "cpu", "preset": "quality"}
        assert result == output

    def test_raises_if_no_backend(self, tmp_path):
        """Auto mode should explain how to configure LatentSync."""
        from screencastgen.lipsync import generate_lipsync_video

        audio = str(tmp_path / "audio.wav")
        _make_wav(audio, duration_s=1.0)
        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)
        output = str(tmp_path / "output.mp4")

        with patch("screencastgen.lipsync._get_audio_duration", return_value=1.0), \
             patch("screencastgen.lipsync._loop_video_to_duration") as mock_loop, \
             patch("screencastgen.lipsync.run_lipsync_provider", side_effect=ImportError), \
             patch("screencastgen.lipsync.os.path.exists", return_value=True), \
             patch("screencastgen.lipsync.os.unlink"):

            mock_loop.return_value = str(tmp_path / "looped.mp4")
            with pytest.raises(ImportError, match="Auto-selected lip-sync provider"):
                generate_lipsync_video(audio, ref_video, output, device="cpu")

    def test_cleans_up_temp_looped_video(self, tmp_path):
        """Temporary looped video should be cleaned up."""
        from screencastgen.lipsync import generate_lipsync_video

        audio = str(tmp_path / "audio.wav")
        _make_wav(audio, duration_s=1.0)
        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)
        output = str(tmp_path / "output.mp4")

        with patch("screencastgen.lipsync._get_audio_duration", return_value=1.0), \
             patch("screencastgen.lipsync._loop_video_to_duration") as mock_loop, \
             patch("screencastgen.lipsync.run_lipsync_provider"), \
             patch("screencastgen.lipsync.os.path.exists", return_value=True), \
             patch("screencastgen.lipsync.os.unlink") as mock_unlink:

            mock_loop.return_value = str(tmp_path / "looped.mp4")
            generate_lipsync_video(audio, ref_video, output, device="cpu")

        mock_unlink.assert_called_once()


# ===================================================================
# Video Composition — Lipsync Layout
# ===================================================================

class TestComposeLipsyncVideoMocked:

    def _mock_moviepy(self):
        """Create a mock moviepy module with all needed classes."""
        mock_video_clip = MagicMock()
        mock_video_clip.with_fps.return_value = mock_video_clip
        mock_video_clip.with_position.return_value = mock_video_clip
        mock_video_clip.with_audio.return_value = mock_video_clip
        mock_video_clip.close.return_value = None

        mock_face_clip = MagicMock()
        mock_face_clip.duration = 2.0
        mock_face_clip.size = (640, 640)
        mock_face_clip.resized.return_value = mock_face_clip
        mock_face_clip.subclipped.return_value = mock_face_clip
        mock_face_clip.loop.return_value = mock_face_clip
        mock_face_clip.with_position.return_value = mock_face_clip

        mock_composite = MagicMock()
        mock_composite.with_duration.return_value = mock_composite
        mock_composite.with_audio.return_value = mock_composite
        mock_composite.close.return_value = None

        mock_final = MagicMock()
        mock_final.write_videofile.return_value = None
        mock_final.close.return_value = None

        mock_moviepy = MagicMock()
        mock_moviepy.VideoClip = MagicMock(return_value=mock_video_clip)
        mock_moviepy.VideoFileClip = MagicMock(return_value=mock_face_clip)
        mock_moviepy.AudioFileClip = MagicMock()
        mock_moviepy.CompositeVideoClip = MagicMock(return_value=mock_composite)
        mock_moviepy.concatenate_videoclips = MagicMock(return_value=mock_final)

        return mock_moviepy, mock_final

    def test_left_layout(self, sample_aligned_chunks, tmp_path):
        """Test lipsync composition with face on left."""
        renderer = HighlightRenderer(width=1280, height=720, font_size=24)
        output_path = str(tmp_path / "lipsync.mp4")

        lipsync_clips = []
        for i in range(3):
            clip_path = str(tmp_path / f"face_{i}.mp4")
            with open(clip_path, "wb") as f:
                f.write(b"\x00" * 100)
            lipsync_clips.append(clip_path)

        mock_moviepy, mock_final = self._mock_moviepy()

        with patch.dict("sys.modules", {"moviepy": mock_moviepy}), \
             patch("screencastgen.video_composer._get_audio_duration", return_value=1.5):

            import importlib
            import screencastgen.video_composer as vc
            importlib.reload(vc)
            result = vc.compose_lipsync_video(
                sample_aligned_chunks, lipsync_clips,
                renderer, output_path, fps=24, face_position="left",
            )

        assert result == output_path
        mock_final.write_videofile.assert_called_once()

    def test_center_layout(self, sample_aligned_chunks, tmp_path):
        """Test lipsync composition with face centered on top."""
        renderer = HighlightRenderer(width=1280, height=720, font_size=24)
        output_path = str(tmp_path / "lipsync_center.mp4")

        lipsync_clips = []
        for i in range(3):
            clip_path = str(tmp_path / f"face_{i}.mp4")
            with open(clip_path, "wb") as f:
                f.write(b"\x00" * 100)
            lipsync_clips.append(clip_path)

        mock_moviepy, mock_final = self._mock_moviepy()

        with patch.dict("sys.modules", {"moviepy": mock_moviepy}), \
             patch("screencastgen.video_composer._get_audio_duration", return_value=1.5):

            import importlib
            import screencastgen.video_composer as vc
            importlib.reload(vc)
            result = vc.compose_lipsync_video(
                sample_aligned_chunks, lipsync_clips,
                renderer, output_path, fps=24, face_position="center",
            )

        assert result == output_path

    def test_corner_layout_uses_scale_and_reserves_reading_pane(self, sample_aligned_chunks, tmp_path):
        """Corner layouts should size the face and keep text out from under it."""
        class TrackingRenderer(HighlightRenderer):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.layout_sizes = []

            def layout_words(self, words):
                self.layout_sizes.append((self.width, self.height))
                return super().layout_words(words)

        renderer = TrackingRenderer(width=1280, height=720, font_size=24)
        output_path = str(tmp_path / "lipsync_corner.mp4")

        lipsync_clips = []
        for i in range(3):
            clip_path = str(tmp_path / f"corner_face_{i}.mp4")
            with open(clip_path, "wb") as f:
                f.write(b"\x00" * 100)
            lipsync_clips.append(clip_path)

        mock_moviepy, _ = self._mock_moviepy()
        mock_face_clip = mock_moviepy.VideoFileClip.return_value

        with patch.dict("sys.modules", {"moviepy": mock_moviepy}), \
             patch("screencastgen.video_composer._get_audio_duration", return_value=1.5):

            import importlib
            import screencastgen.video_composer as vc
            importlib.reload(vc)
            vc.compose_lipsync_video(
                sample_aligned_chunks,
                lipsync_clips,
                renderer,
                output_path,
                fps=24,
                face_position="bottom-right",
                face_scale=0.2,
            )

        mock_face_clip.resized.assert_called_with((256, 256))
        assert renderer.layout_sizes
        assert all(size == (982, 720) for size in renderer.layout_sizes)

    def test_empty_chunks_raises(self, tmp_path):
        """compose_lipsync_video should raise with empty input."""
        renderer = HighlightRenderer()
        output_path = str(tmp_path / "empty.mp4")

        mock_moviepy, _ = self._mock_moviepy()

        with patch.dict("sys.modules", {"moviepy": mock_moviepy}):
            import importlib
            import screencastgen.video_composer as vc
            importlib.reload(vc)
            with pytest.raises(ValueError, match="No clips"):
                vc.compose_lipsync_video([], [], renderer, output_path)


# ===================================================================
# Full Lipsync Pipeline (mocked)
# ===================================================================

class TestLipsyncPipelineIntegration:

    def test_missing_ref_audio_returns_error(self, sample_pdf_simple, tmp_path):
        """Pipeline should fail early without --ref-audio for non-remote backend."""
        from screencastgen.cli import run_lipsync_pipeline

        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)

        args = make_lipsync_args(
            sample_pdf_simple, tmp_path,
            ref_audio=None, ref_video=ref_video,
            backend="qwen",
        )

        result = run_lipsync_pipeline(args)
        assert result == 1

    def test_missing_ref_video_returns_error(self, sample_pdf_simple, tmp_path):
        """Pipeline should fail if reference video doesn't exist."""
        from screencastgen.cli import run_lipsync_pipeline

        ref_audio = str(tmp_path / "ref.wav")
        _make_wav(ref_audio, duration_s=5.0)

        args = make_lipsync_args(
            sample_pdf_simple, tmp_path,
            ref_audio=ref_audio,
            ref_video=str(tmp_path / "nonexistent_face.mp4"),
        )

        mock_be = MockTTSBackend()
        with patch("screencastgen.cli._create_tts_backend", return_value=mock_be):
            result = run_lipsync_pipeline(args)
        assert result == 1

    def test_missing_pdf_returns_error(self, tmp_path):
        """Pipeline should fail if PDF doesn't exist."""
        from screencastgen.cli import run_lipsync_pipeline

        ref_audio = str(tmp_path / "ref.wav")
        _make_wav(ref_audio, duration_s=5.0)
        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)

        args = make_lipsync_args(
            str(tmp_path / "nonexistent.pdf"), tmp_path,
            ref_audio=ref_audio, ref_video=ref_video,
        )

        mock_be = MockTTSBackend()
        with patch("screencastgen.cli._create_tts_backend", return_value=mock_be):
            result = run_lipsync_pipeline(args)
        assert result == 1

    def test_full_lipsync_pipeline_mock(self, sample_pdf_simple, tmp_path):
        """End-to-end lipsync pipeline with all heavy deps mocked."""
        from screencastgen.cli import run_lipsync_pipeline

        ref_audio = str(tmp_path / "ref.wav")
        _make_wav(ref_audio, duration_s=5.0)
        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)

        args = make_lipsync_args(
            sample_pdf_simple, tmp_path,
            ref_audio=ref_audio, ref_video=ref_video,
            format="mp4",
        )
        mock_be = MockTTSBackend()
        mock_words = [WordTiming("test", 0.0, 0.5)]

        # Mock lipsync generation
        def fake_lipsync(audio_path, reference_video_path, output_path, device="cpu", **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"\x00" * 100)
            return output_path

        # Mock moviepy
        mock_moviepy = MagicMock()
        mock_video_clip = MagicMock()
        mock_video_clip.with_fps.return_value = mock_video_clip
        mock_video_clip.with_position.return_value = mock_video_clip
        mock_video_clip.with_audio.return_value = mock_video_clip
        mock_video_clip.close.return_value = None

        mock_face_clip = MagicMock()
        mock_face_clip.duration = 2.0
        mock_face_clip.size = (640, 640)
        mock_face_clip.resized.return_value = mock_face_clip
        mock_face_clip.subclipped.return_value = mock_face_clip
        mock_face_clip.loop.return_value = mock_face_clip
        mock_face_clip.with_position.return_value = mock_face_clip

        mock_composite = MagicMock()
        mock_composite.with_duration.return_value = mock_composite
        mock_composite.with_audio.return_value = mock_composite
        mock_composite.close.return_value = None

        mock_final = MagicMock()
        mock_final.write_videofile.return_value = None
        mock_final.close.return_value = None

        mock_moviepy.VideoClip = MagicMock(return_value=mock_video_clip)
        mock_moviepy.VideoFileClip = MagicMock(return_value=mock_face_clip)
        mock_moviepy.AudioFileClip = MagicMock()
        mock_moviepy.CompositeVideoClip = MagicMock(return_value=mock_composite)
        mock_moviepy.concatenate_videoclips = MagicMock(return_value=mock_final)

        # Mock aligner module for lazy import
        mock_aligner = MagicMock()
        mock_aligner.align_chunk = MagicMock(return_value=mock_words)

        # Mock lipsync module for lazy import
        mock_lipsync_mod = MagicMock()
        mock_lipsync_mod.generate_lipsync_video = MagicMock(side_effect=fake_lipsync)

        with patch("screencastgen.cli._create_tts_backend", return_value=mock_be), \
             patch.dict("sys.modules", {
                 "screencastgen.aligner": mock_aligner,
                 "screencastgen.lipsync": mock_lipsync_mod,
                 "moviepy": mock_moviepy,
             }), \
             patch("screencastgen.video_composer._get_audio_duration", return_value=1.0):
            result = run_lipsync_pipeline(args)

        assert result == 0

    def test_releases_tts_backend_before_alignment(self, sample_pdf_simple, tmp_path):
        """Local lip-sync should unload TTS before later GPU-heavy phases."""
        from screencastgen.pipelines.lipsync import run_lipsync_pipeline
        from screencastgen.pipelines.types import PipelineRunResult
        from screencastgen.types import AlignedChunk, WordTiming

        ref_audio = str(tmp_path / "ref.wav")
        _make_wav(ref_audio, duration_s=1.0)
        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)

        args = make_lipsync_args(
            sample_pdf_simple,
            tmp_path,
            ref_audio=ref_audio,
            ref_video=ref_video,
            backend="qwen",
            format="reader",
        )
        audio_path = str(tmp_path / "chunk_001.wav")
        order = []

        class ReleasableBackend:
            max_chunk_bytes = 1500
            output_format = "wav"

            def close(self):
                order.append("close")

        def fake_synthesize_chunks(*_args, **_kwargs):
            order.append("synthesize")
            with open(audio_path, "wb") as f:
                f.write(b"audio")

        def fake_align_chunks(*_args, **_kwargs):
            order.append("align")
            assert order == ["synthesize", "close", "align"]
            return [
                AlignedChunk(
                    chunk_num=1,
                    text="Hello.",
                    audio_path=audio_path,
                    words=[WordTiming("Hello", 0.0, 0.5)],
                )
            ]

        with patch("screencastgen.pipelines.lipsync.extract_and_chunk_paged", return_value=(["Hello."], {1: [1]})), \
             patch("screencastgen.pipelines.lipsync.validate_and_collect", return_value=[(1, "Hello.", "hash")]), \
             patch("screencastgen.pipelines.lipsync.synthesize_chunks", side_effect=fake_synthesize_chunks), \
             patch("screencastgen.pipelines.lipsync.has_failed_chunks", return_value=False), \
             patch("screencastgen.pipelines.lipsync.align_chunks", side_effect=fake_align_chunks), \
             patch("screencastgen.lipsync.generate_lipsync_video") as mock_lipsync, \
             patch("screencastgen.pipelines.lipsync.build_lipsync_reader", return_value=PipelineRunResult(exit_code=0)):
            def write_lipsync_output(*_args, **kwargs):
                Path(kwargs["output_path"]).write_bytes(b"video")
                return kwargs["output_path"]

            mock_lipsync.side_effect = write_lipsync_output
            result = run_lipsync_pipeline(
                args,
                backend_factory=lambda *_args, **_kwargs: ReleasableBackend(),
            )

        assert result.exit_code == 0
        assert order == ["synthesize", "close", "align"]

    def test_lipsync_tracks_video_rendering(self, tmp_path):
        """Tracker should record rendered video chunks for resumability."""
        from screencastgen.tracker import ProcessingTracker

        tracker = ProcessingTracker(str(tmp_path / "status.json"))
        tracker.mark_video_rendered(1, "video_chunk_001.mp4")
        tracker.mark_video_rendered(2, "video_chunk_002.mp4")

        assert tracker.is_video_rendered(1)
        assert tracker.is_video_rendered(2)
        assert not tracker.is_video_rendered(3)

        # Reload from disk
        tracker2 = ProcessingTracker(str(tmp_path / "status.json"))
        assert tracker2.is_video_rendered(1)


# ===================================================================
# Reader bundle output (separate presenter video + document)
# ===================================================================

class TestLipsyncReaderBundle:

    def test_cli_defaults_to_reader_format(self):
        from screencastgen.cli import _build_parser

        args = _build_parser().parse_args(
            ["lipsync", "document.pdf", "--ref-video", "face.mp4"]
        )
        assert args.format == "reader"

    def test_offline_archive_contains_local_viewer_and_assets(self, tmp_path):
        from screencastgen.offline_reader import build_offline_reader_archive
        from screencastgen.reader_assets import MANIFEST_NAME

        pages = tmp_path / "pages"
        pages.mkdir()
        (tmp_path / "reader_audio.mp3").write_bytes(b"audio")
        (tmp_path / "presenter.mp4").write_bytes(b"video")
        (pages / "page-0001.jpg").write_bytes(b"image")
        manifest = {
            "version": 1,
            "title": "Offline Test",
            "language": "en",
            "duration": 1.0,
            "audio": "reader_audio.mp3",
            "presenter": "presenter.mp4",
            "pages": {
                "dir": "pages",
                "files": {"1": "page-0001.jpg"},
            },
            "chunks": [{
                "chunk_num": 1,
                "text": "hello",
                "offset": 0,
                "pages": [1],
                "words": [{"word": "hello", "start": 0, "end": 1}],
            }],
        }
        manifest_path = tmp_path / MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        output = tmp_path / "offline.zip"
        build_offline_reader_archive(str(manifest_path), str(output))

        with zipfile.ZipFile(output) as archive:
            assert set(archive.namelist()) == {
                "index.html",
                MANIFEST_NAME,
                "reader_audio.mp3",
                "presenter.mp4",
                "pages/page-0001.jpg",
            }
            html = archive.read("index.html").decode()
        assert "Offline Test" in html
        assert "fetch(" not in html
        assert "presenter.mp4" in html

    def test_offline_archive_preserves_markdown_without_empty_page_panel(self, tmp_path):
        from screencastgen.offline_reader import build_offline_reader_archive
        from screencastgen.reader_assets import MANIFEST_NAME

        (tmp_path / "reader_audio.mp3").write_bytes(b"audio")
        manifest = {
            "version": 1,
            "title": "Markdown Test",
            "language": "en",
            "source_type": "md",
            "source_markdown": "# Heading\n\n- **Bold** item\n",
            "duration": 1.0,
            "audio": "reader_audio.mp3",
            "presenter": None,
            "pages": None,
            "chunks": [{
                "chunk_num": 1,
                "text": "Heading Bold item",
                "offset": 0,
                "pages": [],
                "words": [
                    {"word": "Heading", "start": 0, "end": 0.3},
                    {"word": "Bold", "start": 0.3, "end": 0.6},
                    {"word": "item", "start": 0.6, "end": 1.0},
                ],
            }],
        }
        manifest_path = tmp_path / MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        output = tmp_path / "offline.zip"
        build_offline_reader_archive(str(manifest_path), str(output))

        with zipfile.ZipFile(output) as archive:
            html = archive.read("index.html").decode()

        assert "renderMarkdown" in html
        assert "No page image available" not in html
        assert '"source_markdown": "# Heading\\n\\n- **Bold** item\\n"' in html

    def test_offline_archive_can_package_source_pdf(self, tmp_path):
        from screencastgen.offline_reader import build_offline_reader_archive
        from screencastgen.reader_assets import MANIFEST_NAME

        (tmp_path / "reader_audio.mp3").write_bytes(b"audio")
        (tmp_path / "source_document.pdf").write_bytes(b"%PDF-1.4\n")
        manifest = {
            "version": 1,
            "title": "PDF Test",
            "language": "en",
            "source_type": "pdf",
            "source_file": "source_document.pdf",
            "duration": 1.0,
            "audio": "reader_audio.mp3",
            "presenter": None,
            "pages": None,
            "chunks": [{
                "chunk_num": 1,
                "text": "hello",
                "offset": 0,
                "pages": [1],
                "words": [{"word": "hello", "start": 0, "end": 1}],
            }],
        }
        manifest_path = tmp_path / MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        output = tmp_path / "offline.zip"
        build_offline_reader_archive(str(manifest_path), str(output))

        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            html = archive.read("index.html").decode()

        assert "source_document.pdf" in names
        assert "source-pdf" in html
        assert "has-document" in html
        assert "No page image available" not in html

    def test_refresh_manifest_source_updates_pdf_and_markdown(self, tmp_path):
        from screencastgen.reader_assets import MANIFEST_NAME, refresh_manifest_source

        manifest_path = tmp_path / MANIFEST_NAME
        manifest_path.write_text(
            json.dumps({
                "version": 1,
                "title": "Source Test",
                "language": "en",
                "duration": 1.0,
                "audio": "reader_audio.mp3",
                "presenter": None,
                "pages": None,
                "chunks": [],
            }),
            encoding="utf-8",
        )
        pdf_path = tmp_path / "lesson.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")

        assert refresh_manifest_source(str(manifest_path), str(pdf_path)) is True
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["source_type"] == "pdf"
        assert manifest["source_file"] == "source_document.pdf"
        assert (tmp_path / "source_document.pdf").read_bytes() == b"%PDF-1.4\n"

        md_path = tmp_path / "lesson.md"
        md_path.write_text("# Heading\n\n- **Bold** item\n", encoding="utf-8")
        assert refresh_manifest_source(str(manifest_path), str(md_path)) is True
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["source_type"] == "md"
        assert manifest["source_file"] == "source_document.md"
        assert manifest["source_markdown"] == "# Heading\n\n- **Bold** item\n"

    def test_lipsync_epub_omits_presenter_video(
        self, sample_aligned_chunks, sample_pdf_simple, tmp_path
    ):
        from screencastgen.pipelines.lipsync import build_lipsync_epub

        captured = []

        class FakeBuilder:
            def __init__(self, **kwargs):
                pass

            def add_chapter(self, chapter_num, aligned_chunks, lipsync_video_path=None):
                captured.append(lipsync_video_path)

            def build(self, output_path):
                with open(output_path, "wb") as fh:
                    fh.write(b"epub")

        tracker = MagicMock()
        tracker.is_epub_built.return_value = False
        request = make_lipsync_args(
            sample_pdf_simple,
            tmp_path,
            ref_audio=str(tmp_path / "voice.wav"),
            ref_video=str(tmp_path / "face.mp4"),
            format="epub",
        )

        with patch("screencastgen.epub_builder.EPUBBuilder", FakeBuilder):
            result = build_lipsync_epub(
                request,
                sample_aligned_chunks,
                [str(tmp_path / "clip.mp4")] * len(sample_aligned_chunks),
                tracker,
            )

        assert result.exit_code == 0
        assert captured and all(video is None for video in captured)

    def test_tracker_presenter_flag_persists(self, tmp_path):
        """Tracker should record presenter-built state for resumability."""
        from screencastgen.tracker import ProcessingTracker

        status = str(tmp_path / "status.json")
        tracker = ProcessingTracker(status)
        assert not tracker.is_presenter_built()
        tracker.mark_presenter_built()
        assert tracker.is_presenter_built()

        assert ProcessingTracker(status).is_presenter_built()

    def test_build_reader_assets_includes_presenter_field(
        self, sample_aligned_chunks, sample_pdf_simple, tmp_path
    ):
        """The reader manifest carries the presenter filename for lip-sync jobs."""
        import json

        pytest.importorskip("pydub", reason="pydub required for reader audio")
        from screencastgen.reader_assets import (
            MANIFEST_NAME,
            PRESENTER_NAME,
            build_reader_assets,
        )

        out = str(tmp_path / "reader")
        os.makedirs(out, exist_ok=True)
        try:
            manifest_path = build_reader_assets(
                aligned_chunks=sample_aligned_chunks,
                output_dir=out,
                pdf_path=sample_pdf_simple,
                title="Test",
                presenter=PRESENTER_NAME,
            )
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"reader asset build needs ffmpeg/pydub: {exc}")

        assert manifest_path and manifest_path.endswith(MANIFEST_NAME)
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        assert manifest["presenter"] == PRESENTER_NAME

        # Highlight jobs (no presenter) leave the field null.
        highlight_manifest = build_reader_assets(
            aligned_chunks=sample_aligned_chunks,
            output_dir=out,
            pdf_path=sample_pdf_simple,
            title="Test",
        )
        with open(highlight_manifest, "r", encoding="utf-8") as fh:
            assert json.load(fh)["presenter"] is None

    def test_reader_assets_preserve_markdown_display_source(
        self, sample_aligned_chunks, tmp_path
    ):
        """Markdown jobs keep raw Markdown for display while chunks stay plain."""
        import json

        pytest.importorskip("pydub", reason="pydub required for reader audio")
        from screencastgen.reader_assets import build_reader_assets

        md_path = tmp_path / "lesson.md"
        md_path.write_text("# Lesson\n\nNarrate **this**.", encoding="utf-8")
        out = str(tmp_path / "reader")
        os.makedirs(out, exist_ok=True)

        try:
            manifest_path = build_reader_assets(
                aligned_chunks=sample_aligned_chunks,
                output_dir=out,
                pdf_path=str(md_path),
                title="Lesson",
            )
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"reader asset build needs ffmpeg/pydub: {exc}")

        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        assert manifest["source_type"] == "md"
        assert manifest["source_markdown"] == "# Lesson\n\nNarrate **this**."
        assert manifest["chunks"][0]["text"] == sample_aligned_chunks[0].text

    def test_reader_format_dispatches_to_build_lipsync_reader(
        self, sample_pdf_simple, tmp_path
    ):
        """format='reader' routes the pipeline to the reader-bundle builder."""
        from screencastgen.cli import run_lipsync_pipeline
        from screencastgen.pipelines.types import PipelineRunResult

        ref_audio = str(tmp_path / "ref.wav")
        _make_wav(ref_audio, duration_s=5.0)
        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)

        args = make_lipsync_args(
            sample_pdf_simple, tmp_path,
            ref_audio=ref_audio, ref_video=ref_video,
            format="reader",
        )
        mock_be = MockTTSBackend()
        mock_words = [WordTiming("test", 0.0, 0.5)]

        def fake_lipsync(audio_path, reference_video_path, output_path, device="cpu", **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"\x00" * 100)
            return output_path

        mock_aligner = MagicMock()
        mock_aligner.align_chunk = MagicMock(return_value=mock_words)
        mock_lipsync_mod = MagicMock()
        mock_lipsync_mod.generate_lipsync_video = MagicMock(side_effect=fake_lipsync)

        captured = {}

        def fake_build_reader(request, aligned_chunks, lipsync_clips, tracker, **kwargs):
            captured["chunks"] = list(aligned_chunks)
            captured["clips"] = list(lipsync_clips)
            return PipelineRunResult(
                exit_code=0,
                output_name="reader_manifest.json",
                output_path=str(tmp_path / "reader_manifest.json"),
            )

        with patch("screencastgen.cli._create_tts_backend", return_value=mock_be), \
             patch.dict("sys.modules", {
                 "screencastgen.aligner": mock_aligner,
                 "screencastgen.lipsync": mock_lipsync_mod,
             }), \
             patch(
                 "screencastgen.pipelines.lipsync.build_lipsync_reader",
                 side_effect=fake_build_reader,
             ) as mock_reader:
            result = run_lipsync_pipeline(args)

        assert result == 0
        assert mock_reader.called
        assert captured["chunks"], "reader builder received aligned chunks"
        assert captured["clips"], "reader builder received lip-sync clips"


# ===================================================================
# Lipsync with Remote GPU (mocked)
# ===================================================================

class TestLipsyncRemoteGPU:

    def test_gpu_server_url_for_remote_backend(self):
        from screencastgen.cli import _gpu_server_url
        import argparse

        args = argparse.Namespace(backend="remote", tts_server_url="http://gpu:8100")
        assert _gpu_server_url(args) == "http://gpu:8100"

    def test_gpu_server_url_for_local_backend(self):
        from screencastgen.cli import _gpu_server_url
        import argparse

        args = argparse.Namespace(backend="qwen")
        assert _gpu_server_url(args) is None

    def test_remote_backend_skips_ref_audio_check(self, sample_pdf_simple, tmp_path):
        """Remote backend should not require --ref-audio."""
        from screencastgen.cli import run_lipsync_pipeline

        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)

        args = make_lipsync_args(
            sample_pdf_simple, tmp_path,
            ref_audio=None, ref_video=ref_video,
            backend="remote",
            format="mp4",
        )

        mock_be = MockTTSBackend()
        mock_words = [WordTiming("remote", 0.0, 0.5)]

        def fake_remote_lipsync(audio_path, reference_video_path, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"\x00" * 100)
            return output_path

        mock_moviepy = MagicMock()
        mock_video_clip = MagicMock()
        mock_video_clip.with_fps.return_value = mock_video_clip
        mock_video_clip.with_position.return_value = mock_video_clip
        mock_video_clip.with_audio.return_value = mock_video_clip
        mock_video_clip.close.return_value = None

        mock_face_clip = MagicMock()
        mock_face_clip.duration = 2.0
        mock_face_clip.size = (640, 640)
        mock_face_clip.resized.return_value = mock_face_clip
        mock_face_clip.subclipped.return_value = mock_face_clip
        mock_face_clip.loop.return_value = mock_face_clip
        mock_face_clip.with_position.return_value = mock_face_clip

        mock_composite = MagicMock()
        mock_composite.with_duration.return_value = mock_composite
        mock_composite.with_audio.return_value = mock_composite
        mock_composite.close.return_value = None

        mock_final = MagicMock()
        mock_final.write_videofile.return_value = None
        mock_final.close.return_value = None

        mock_moviepy.VideoClip = MagicMock(return_value=mock_video_clip)
        mock_moviepy.VideoFileClip = MagicMock(return_value=mock_face_clip)
        mock_moviepy.AudioFileClip = MagicMock()
        mock_moviepy.CompositeVideoClip = MagicMock(return_value=mock_composite)
        mock_moviepy.concatenate_videoclips = MagicMock(return_value=mock_final)

        with patch("screencastgen.cli._create_tts_backend", return_value=mock_be), \
             patch("screencastgen.remote_gpu.remote_align_chunk", return_value=mock_words) as mock_align, \
             patch("screencastgen.remote_gpu.remote_generate_lipsync", side_effect=fake_remote_lipsync) as mock_lipsync, \
             patch.dict("sys.modules", {"moviepy": mock_moviepy}), \
             patch("screencastgen.video_composer._get_audio_duration", return_value=1.0):
            result = run_lipsync_pipeline(args)

        assert result == 0
        assert mock_align.called
        assert mock_lipsync.called
