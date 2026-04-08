"""Integration tests for real GPU models — run against a live inference server.

These tests hit real models (Qwen3-TTS, WhisperX, LatentSync) either locally
or via the remote inference server.  They are *not* mocked.

Usage
-----
# Start the inference server on the GPU machine first:
#   screencastgen-server --backend qwen --device cuda

# Run all GPU tests against the remote server:
pytest tests/test_gpu_models.py -v --server-url http://gpu-vm:8100

# Run only one model:
pytest tests/test_gpu_models.py -v -k qwen
pytest tests/test_gpu_models.py -v -k whisperx
pytest tests/test_gpu_models.py -v -k lipsync

# Run locally (models loaded in-process, needs GPU + all deps):
pytest tests/test_gpu_models.py -v --local-gpu --device cuda
"""

import json
import os
import wave

import pytest


# ---------------------------------------------------------------------------
# Session-scoped fixtures (read CLI options from conftest.py)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def server_url(request):
    return request.config.getoption("--server-url")


@pytest.fixture(scope="session")
def local_gpu(request):
    return request.config.getoption("--local-gpu")


@pytest.fixture(scope="session")
def device(request):
    return request.config.getoption("--device")


@pytest.fixture(scope="session")
def ref_audio_path(request):
    return request.config.getoption("--ref-audio")


@pytest.fixture(scope="session")
def ref_video_path(request):
    return request.config.getoption("--ref-video")


def _skip_unless_gpu_available(server_url, local_gpu):
    if not server_url and not local_gpu:
        pytest.skip(
            "GPU tests require either --server-url or --local-gpu. "
            "Run with: pytest --server-url http://gpu:8100  OR  pytest --local-gpu --device cuda"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wav_duration(path: str) -> float:
    with wave.open(path, "r") as wf:
        return wf.getnframes() / wf.getframerate()


def _is_valid_wav(path: str) -> bool:
    try:
        with wave.open(path, "r") as wf:
            return wf.getnframes() > 0
    except Exception:
        return False


# ===================================================================
# 1. Qwen3-TTS  (Text-to-Speech)
# ===================================================================

class TestQwenTTS:
    """Test Qwen3-TTS model — synthesize text into audio."""

    SAMPLE_TEXTS = [
        "Hello, this is a test of the text to speech system.",
        "Machine learning models can generate realistic speech from text input.",
        "The quick brown fox jumps over the lazy dog.",
    ]

    def test_server_health(self, server_url, local_gpu):
        """Verify the inference server is up and reports qwen backend."""
        _skip_unless_gpu_available(server_url, local_gpu)
        if not server_url:
            pytest.skip("Health check only applies to remote server mode")

        import urllib.request
        req = urllib.request.Request(f"{server_url.rstrip('/')}/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            info = json.loads(resp.read())

        assert info["status"] == "ok"
        assert info["output_format"] in ("wav", "mp3")
        assert info["max_chunk_bytes"] > 0
        assert "synthesize" in info["capabilities"]

    def test_synthesize_short_text(self, server_url, local_gpu, device, tmp_path):
        """Synthesize a single short sentence and verify valid audio output."""
        _skip_unless_gpu_available(server_url, local_gpu)

        text = "Hello, this is a short test."
        output_path = str(tmp_path / "short.wav")

        if server_url:
            self._synthesize_remote(server_url, text, output_path)
        else:
            self._synthesize_local(text, output_path, device)

        assert os.path.isfile(output_path)
        assert os.path.getsize(output_path) > 1000, "Audio file suspiciously small"
        assert _is_valid_wav(output_path)
        duration = _wav_duration(output_path)
        assert duration > 0.5, f"Audio too short: {duration:.2f}s"
        print(f"  Generated audio: {duration:.2f}s, {os.path.getsize(output_path)} bytes")

    def test_synthesize_multiple_sentences(self, server_url, local_gpu, device, tmp_path):
        """Synthesize multiple sentences and verify each produces distinct audio."""
        _skip_unless_gpu_available(server_url, local_gpu)

        sizes = []
        for i, text in enumerate(self.SAMPLE_TEXTS):
            output_path = str(tmp_path / f"sentence_{i}.wav")

            if server_url:
                self._synthesize_remote(server_url, text, output_path)
            else:
                self._synthesize_local(text, output_path, device)

            assert os.path.isfile(output_path)
            assert _is_valid_wav(output_path)
            size = os.path.getsize(output_path)
            sizes.append(size)
            print(f"  [{i}] {len(text)} chars -> {size} bytes, {_wav_duration(output_path):.2f}s")

        # Different texts should produce different-sized audio
        assert len(set(sizes)) > 1, "All outputs have identical size — model may not be working"

    def test_synthesize_long_chunk(self, server_url, local_gpu, device, tmp_path):
        """Synthesize a paragraph-length chunk (typical pipeline chunk size)."""
        _skip_unless_gpu_available(server_url, local_gpu)

        text = (
            "Artificial intelligence has transformed how we interact with technology. "
            "From voice assistants to autonomous vehicles, machine learning models are "
            "becoming increasingly capable. Natural language processing enables computers "
            "to understand and generate human language with remarkable fluency. "
            "Text to speech systems can now produce audio that is nearly indistinguishable "
            "from human recordings."
        )
        output_path = str(tmp_path / "long_chunk.wav")

        if server_url:
            self._synthesize_remote(server_url, text, output_path)
        else:
            self._synthesize_local(text, output_path, device)

        assert os.path.isfile(output_path)
        assert _is_valid_wav(output_path)
        duration = _wav_duration(output_path)
        assert duration > 5.0, f"Long text should produce >5s audio, got {duration:.2f}s"
        print(f"  Long chunk: {len(text)} chars -> {duration:.2f}s")

    def test_synthesize_empty_text_fails(self, server_url, local_gpu, device, tmp_path):
        """Empty text should raise an error or produce no meaningful audio."""
        _skip_unless_gpu_available(server_url, local_gpu)

        output_path = str(tmp_path / "empty.wav")

        with pytest.raises(Exception):
            if server_url:
                self._synthesize_remote(server_url, "", output_path)
            else:
                self._synthesize_local("", output_path, device)

    # -- Helpers --

    @staticmethod
    def _synthesize_remote(server_url: str, text: str, output_path: str):
        import urllib.request
        payload = json.dumps({"text": text, "language": "en-US"}).encode()
        req = urllib.request.Request(
            f"{server_url.rstrip('/')}/synthesize",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            audio_bytes = resp.read()
        if not audio_bytes:
            raise RuntimeError("Server returned empty audio")
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

    @staticmethod
    def _synthesize_local(text: str, output_path: str, device: str):
        from screencastgen.providers.tts.qwen_backend import QwenTTS
        backend = QwenTTS(device=device)
        backend.synthesize(text, output_path)


# ===================================================================
# 2. WhisperX  (Speech-to-text alignment)
# ===================================================================

class TestWhisperXAlignment:
    """Test WhisperX model — align text to audio and get word-level timestamps."""

    def test_align_short_audio(self, server_url, local_gpu, device, tmp_path):
        """Synthesize text, then align it back — timestamps should be reasonable."""
        _skip_unless_gpu_available(server_url, local_gpu)

        text = "Hello world. This is a test of alignment."
        audio_path = str(tmp_path / "for_align.wav")

        # Step 1: generate real audio (we need real speech, not silence)
        if server_url:
            TestQwenTTS._synthesize_remote(server_url, text, audio_path)
        else:
            TestQwenTTS._synthesize_local(text, audio_path, device)

        assert os.path.isfile(audio_path) and os.path.getsize(audio_path) > 0

        # Step 2: run alignment
        if server_url:
            words = self._align_remote(server_url, audio_path, text)
        else:
            words = self._align_local(audio_path, text, device)

        assert len(words) > 0, "Alignment returned no words"
        print(f"  Aligned {len(words)} words")
        for w in words:
            print(f"    {w.word:15s}  {w.start:.3f} - {w.end:.3f}")

        # Validate timestamps
        for w in words:
            assert w.start >= 0, f"Negative start time: {w.word} @ {w.start}"
            assert w.end >= w.start, f"End before start: {w.word} @ {w.start}-{w.end}"

        # Timestamps should be monotonically non-decreasing
        starts = [w.start for w in words]
        assert starts == sorted(starts), "Word start times are not monotonically ordered"

    def test_align_longer_chunk(self, server_url, local_gpu, device, tmp_path):
        """Align a longer paragraph and verify coverage."""
        _skip_unless_gpu_available(server_url, local_gpu)

        text = (
            "Machine learning is a subset of artificial intelligence. "
            "It allows systems to learn and improve from experience. "
            "Deep learning uses neural networks with many layers."
        )
        audio_path = str(tmp_path / "long_align.wav")

        if server_url:
            TestQwenTTS._synthesize_remote(server_url, text, audio_path)
        else:
            TestQwenTTS._synthesize_local(text, audio_path, device)

        if server_url:
            words = self._align_remote(server_url, audio_path, text)
        else:
            words = self._align_local(audio_path, text, device)

        assert len(words) >= 10, f"Expected at least 10 aligned words, got {len(words)}"

        # Check that alignment spans most of the audio duration
        audio_duration = _wav_duration(audio_path)
        last_end = max(w.end for w in words)
        coverage = last_end / audio_duration
        assert coverage > 0.5, f"Alignment only covers {coverage:.0%} of audio"
        print(f"  {len(words)} words, audio={audio_duration:.2f}s, last_end={last_end:.2f}s, coverage={coverage:.0%}")

    def test_align_returns_word_timing_objects(self, server_url, local_gpu, device, tmp_path):
        """Verify the return type is a list of WordTiming."""
        _skip_unless_gpu_available(server_url, local_gpu)
        from screencastgen.types import WordTiming

        text = "Simple test sentence."
        audio_path = str(tmp_path / "wt_check.wav")

        if server_url:
            TestQwenTTS._synthesize_remote(server_url, text, audio_path)
        else:
            TestQwenTTS._synthesize_local(text, audio_path, device)

        if server_url:
            words = self._align_remote(server_url, audio_path, text)
        else:
            words = self._align_local(audio_path, text, device)

        assert all(isinstance(w, WordTiming) for w in words)
        assert all(hasattr(w, "word") and hasattr(w, "start") and hasattr(w, "end") for w in words)

    # -- Helpers --

    @staticmethod
    def _align_remote(server_url: str, audio_path: str, text: str):
        from screencastgen.remote_gpu import remote_align_chunk
        return remote_align_chunk(
            audio_path, text, server_url=server_url, language="en-US",
        )

    @staticmethod
    def _align_local(audio_path: str, text: str, device: str):
        from screencastgen.aligner import align_chunk
        return align_chunk(audio_path, text, language="en-US", device=device)


# ===================================================================
# 3. LatentSync / Lip-sync  (Audio + face video -> lip-synced video)
# ===================================================================

class TestLipSync:
    """Test LatentSync/Wav2Lip model — generate lip-synced video from audio + face."""

    @pytest.fixture
    def ref_video_required(self, ref_video_path):
        if not ref_video_path or not os.path.isfile(ref_video_path):
            pytest.skip(
                "Lip-sync tests require --ref-video pointing to a face video file. "
                "Example: pytest --ref-video /path/to/face.mp4"
            )
        return ref_video_path

    def test_lipsync_short_clip(self, server_url, local_gpu, device, tmp_path, ref_video_required):
        """Generate a short lip-synced video and verify the output exists."""
        _skip_unless_gpu_available(server_url, local_gpu)

        text = "Hello, this is a test of lip synchronization."
        audio_path = str(tmp_path / "lipsync_audio.wav")
        output_path = str(tmp_path / "lipsync_output.mp4")

        # Generate audio first
        if server_url:
            TestQwenTTS._synthesize_remote(server_url, text, audio_path)
        else:
            TestQwenTTS._synthesize_local(text, audio_path, device)

        assert os.path.isfile(audio_path)

        # Run lip-sync
        if server_url:
            self._lipsync_remote(server_url, audio_path, ref_video_required, output_path)
        else:
            self._lipsync_local(audio_path, ref_video_required, output_path, device)

        assert os.path.isfile(output_path), "Lip-sync output video not created"
        assert os.path.getsize(output_path) > 10000, "Output video suspiciously small"
        print(f"  Lip-sync output: {os.path.getsize(output_path)} bytes")

    def test_lipsync_produces_valid_video(self, server_url, local_gpu, device, tmp_path, ref_video_required):
        """Verify the output is a valid video file using ffprobe."""
        _skip_unless_gpu_available(server_url, local_gpu)

        text = "Testing video output validity."
        audio_path = str(tmp_path / "valid_audio.wav")
        output_path = str(tmp_path / "valid_output.mp4")

        if server_url:
            TestQwenTTS._synthesize_remote(server_url, text, audio_path)
        else:
            TestQwenTTS._synthesize_local(text, audio_path, device)

        if server_url:
            self._lipsync_remote(server_url, audio_path, ref_video_required, output_path)
        else:
            self._lipsync_local(audio_path, ref_video_required, output_path, device)

        # Verify with ffprobe
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", output_path],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"ffprobe failed: {result.stderr}"
        probe = json.loads(result.stdout)
        streams = probe.get("streams", [])
        video_streams = [s for s in streams if s["codec_type"] == "video"]
        assert len(video_streams) >= 1, "No video stream in output"
        print(f"  Video: {video_streams[0].get('width')}x{video_streams[0].get('height')}, "
              f"codec={video_streams[0].get('codec_name')}")

    # -- Helpers --

    @staticmethod
    def _lipsync_remote(server_url: str, audio_path: str, ref_video_path: str, output_path: str):
        from screencastgen.remote_gpu import remote_generate_lipsync
        remote_generate_lipsync(
            audio_path, ref_video_path, output_path, server_url=server_url,
        )

    @staticmethod
    def _lipsync_local(audio_path: str, ref_video_path: str, output_path: str, device: str):
        from screencastgen.lipsync import generate_lipsync_video
        generate_lipsync_video(
            audio_path=audio_path,
            reference_video_path=ref_video_path,
            output_path=output_path,
            device=device,
        )


# ===================================================================
# 4. End-to-end: TTS -> Alignment (chained)
# ===================================================================

class TestTTSThenAlignment:
    """Test the TTS + WhisperX chain — the core of the highlight pipeline."""

    def test_synthesize_then_align_roundtrip(self, server_url, local_gpu, device, tmp_path):
        """Full roundtrip: text -> TTS -> alignment -> verify words match."""
        _skip_unless_gpu_available(server_url, local_gpu)

        text = "The weather is sunny today. Birds are singing in the trees."
        audio_path = str(tmp_path / "roundtrip.wav")

        # Synthesize
        if server_url:
            TestQwenTTS._synthesize_remote(server_url, text, audio_path)
        else:
            TestQwenTTS._synthesize_local(text, audio_path, device)

        # Align
        if server_url:
            words = TestWhisperXAlignment._align_remote(server_url, audio_path, text)
        else:
            words = TestWhisperXAlignment._align_local(audio_path, text, device)

        assert len(words) >= 5

        # Check that aligned words roughly match the input text
        aligned_text = " ".join(w.word for w in words).lower()
        for keyword in ["weather", "sunny", "birds", "singing", "trees"]:
            assert keyword in aligned_text, f"Expected '{keyword}' in aligned output: {aligned_text}"

        # Timeline should fit within audio duration
        audio_duration = _wav_duration(audio_path)
        for w in words:
            assert w.end <= audio_duration + 0.5, (
                f"Word '{w.word}' ends at {w.end:.2f}s but audio is only {audio_duration:.2f}s"
            )

        print(f"  Roundtrip OK: {len(text)} chars -> {_wav_duration(audio_path):.1f}s audio -> {len(words)} words aligned")
