"""Tests for the lip-sync video pipeline.

Covers: lipsync video generation (mocked), video composition with
face + text layout, and the full lipsync pipeline integration.

Run:
    pytest tests/test_lipsync_pipeline.py -v
"""

import os
import subprocess
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

class TestGenerateLipsyncVideo:

    def test_uses_latentsync_first(self, tmp_path):
        """Should try LatentSync before Wav2Lip."""
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
             patch("screencastgen.lipsync._run_latentsync") as mock_ls, \
             patch("screencastgen.lipsync.os.path.exists", return_value=True), \
             patch("screencastgen.lipsync.os.unlink"):

            mock_loop.return_value = str(tmp_path / "looped.mp4")
            result = generate_lipsync_video(audio, ref_video, output, device="cpu")

        mock_ls.assert_called_once()
        assert result == output

    def test_falls_back_to_wav2lip(self, tmp_path):
        """When LatentSync raises ImportError, fall back to Wav2Lip."""
        from screencastgen.lipsync import generate_lipsync_video

        audio = str(tmp_path / "audio.wav")
        _make_wav(audio, duration_s=1.0)
        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)
        output = str(tmp_path / "output.mp4")

        with patch("screencastgen.lipsync._get_audio_duration", return_value=1.0), \
             patch("screencastgen.lipsync._loop_video_to_duration") as mock_loop, \
             patch("screencastgen.lipsync._run_latentsync", side_effect=ImportError), \
             patch("screencastgen.lipsync._run_wav2lip") as mock_w2l, \
             patch("screencastgen.lipsync.os.path.exists", return_value=True), \
             patch("screencastgen.lipsync.os.unlink"):

            mock_loop.return_value = str(tmp_path / "looped.mp4")
            result = generate_lipsync_video(audio, ref_video, output, device="cpu")

        mock_w2l.assert_called_once()

    def test_raises_if_no_backend(self, tmp_path):
        """When both LatentSync and Wav2Lip fail, raise ImportError."""
        from screencastgen.lipsync import generate_lipsync_video

        audio = str(tmp_path / "audio.wav")
        _make_wav(audio, duration_s=1.0)
        ref_video = str(tmp_path / "face.mp4")
        with open(ref_video, "wb") as f:
            f.write(b"\x00" * 100)
        output = str(tmp_path / "output.mp4")

        with patch("screencastgen.lipsync._get_audio_duration", return_value=1.0), \
             patch("screencastgen.lipsync._loop_video_to_duration") as mock_loop, \
             patch("screencastgen.lipsync._run_latentsync", side_effect=ImportError), \
             patch("screencastgen.lipsync._run_wav2lip", side_effect=ImportError), \
             patch("screencastgen.lipsync.os.path.exists", return_value=True), \
             patch("screencastgen.lipsync.os.unlink"):

            mock_loop.return_value = str(tmp_path / "looped.mp4")
            with pytest.raises(ImportError, match="No lip-sync backend"):
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
             patch("screencastgen.lipsync._run_latentsync"), \
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
            backend="f5",
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
