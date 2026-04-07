"""Shared fixtures for screencastgen tests."""

import argparse
import json
import os
import struct
import tempfile
import wave
from pathlib import Path
from typing import List

import pytest


# ---------------------------------------------------------------------------
# CLI options for GPU integration tests
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--server-url",
        default=None,
        help="URL of a running screencastgen inference server (e.g. http://gpu-vm:8100).",
    )
    parser.addoption(
        "--local-gpu",
        action="store_true",
        default=False,
        help="Load models in-process (requires GPU + ML deps installed locally).",
    )
    parser.addoption(
        "--device",
        default="cuda",
        help="Device for local-gpu tests (default: cuda).",
    )
    parser.addoption(
        "--ref-audio",
        default=None,
        help="Path to a reference audio file for voice-cloning / F5-TTS tests.",
    )
    parser.addoption(
        "--ref-video",
        default=None,
        help="Path to a reference face video for lip-sync tests (~5-10 s).",
    )

from screencastgen.types import AlignedChunk, WordTiming


# ---------------------------------------------------------------------------
# Sample PDF
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_pdf(tmp_path):
    """Create a minimal valid PDF with two pages of text."""
    from PyPDF2 import PdfWriter
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as rl_canvas

    pdf_path = tmp_path / "sample.pdf"
    c = rl_canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawString(72, 700, "This is the first page of the sample document.")
    c.drawString(72, 680, "It contains a few sentences for testing purposes.")
    c.showPage()
    c.drawString(72, 700, "This is the second page with more content.")
    c.drawString(72, 680, "Machine learning models require large datasets.")
    c.save()

    return str(pdf_path)


@pytest.fixture
def sample_pdf_simple(tmp_path):
    """Create a minimal PDF without reportlab (uses raw PDF bytes)."""
    pdf_path = tmp_path / "simple.pdf"
    # Minimal valid PDF with text
    pdf_bytes = (
        b"%PDF-1.0\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
        b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 84>>stream\n"
        b"BT /F1 12 Tf 72 700 Td (Hello world. This is a test document. Testing sentence splitting.) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000400 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\n"
        b"startxref\n466\n%%EOF\n"
    )
    pdf_path.write_bytes(pdf_bytes)
    return str(pdf_path)


# ---------------------------------------------------------------------------
# Sample WAV audio
# ---------------------------------------------------------------------------

def _make_wav(path: str, duration_s: float = 1.0, sample_rate: int = 16000) -> str:
    """Generate a silent WAV file of the given duration."""
    n_frames = int(sample_rate * duration_s)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)
    return path


@pytest.fixture
def sample_wav(tmp_path):
    """Create a 1-second silent WAV file."""
    return _make_wav(str(tmp_path / "sample.wav"), duration_s=1.0)


@pytest.fixture
def sample_wav_short(tmp_path):
    """Create a 0.5-second silent WAV file."""
    return _make_wav(str(tmp_path / "short.wav"), duration_s=0.5)


@pytest.fixture
def chunk_wav_files(tmp_path):
    """Create multiple numbered chunk WAV files."""
    paths = []
    for i in range(1, 4):
        p = tmp_path / f"audio_chunk_{i:03d}.wav"
        _make_wav(str(p), duration_s=0.5)
        paths.append(str(p))
    return paths


# ---------------------------------------------------------------------------
# Mock TTS backend
# ---------------------------------------------------------------------------

class MockTTSBackend:
    """A fake TTS backend that creates silent WAV files."""

    def __init__(self, max_bytes=4900, fmt="wav"):
        self._max_bytes = max_bytes
        self._fmt = fmt
        self.calls: List[tuple] = []

    @property
    def max_chunk_bytes(self) -> int:
        return self._max_bytes

    @property
    def output_format(self) -> str:
        return self._fmt

    def synthesize(self, text: str, output_path: str) -> None:
        self.calls.append((text, output_path))
        _make_wav(output_path, duration_s=0.5 + len(text) / 500)


class FailingTTSBackend(MockTTSBackend):
    """A TTS backend that fails on every call."""

    def synthesize(self, text: str, output_path: str) -> None:
        self.calls.append((text, output_path))
        raise RuntimeError("TTS synthesis failed")


@pytest.fixture
def mock_backend():
    return MockTTSBackend()


@pytest.fixture
def failing_backend():
    return FailingTTSBackend()


# ---------------------------------------------------------------------------
# Sample aligned chunks
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_aligned_chunks(chunk_wav_files):
    """Three aligned chunks with word timings."""
    return [
        AlignedChunk(
            chunk_num=1,
            text="Hello world. This is a test.",
            audio_path=chunk_wav_files[0],
            words=[
                WordTiming("Hello", 0.0, 0.3),
                WordTiming("world.", 0.3, 0.6),
                WordTiming("This", 0.65, 0.8),
                WordTiming("is", 0.8, 0.9),
                WordTiming("a", 0.9, 0.95),
                WordTiming("test.", 0.95, 1.2),
            ],
        ),
        AlignedChunk(
            chunk_num=2,
            text="Machine learning is great.",
            audio_path=chunk_wav_files[1],
            words=[
                WordTiming("Machine", 0.0, 0.4),
                WordTiming("learning", 0.4, 0.8),
                WordTiming("is", 0.85, 0.95),
                WordTiming("great.", 0.95, 1.3),
            ],
        ),
        AlignedChunk(
            chunk_num=3,
            text="Final chunk here.",
            audio_path=chunk_wav_files[2],
            words=[
                WordTiming("Final", 0.0, 0.3),
                WordTiming("chunk", 0.3, 0.5),
                WordTiming("here.", 0.5, 0.8),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# CLI args helpers
# ---------------------------------------------------------------------------

def make_audio_args(pdf_path, output_dir, **overrides):
    """Build an argparse.Namespace mimicking CLI args for the audio pipeline."""
    defaults = dict(
        command="audio",
        pdf=pdf_path,
        output_dir=str(output_dir),
        output=None,
        language="en-US",
        status_file="processing_status.json",
        clean=True,
        verbose=False,
        backend="qwen",
        device="cpu",
        voice=None,
        model=None,
        ref_audio=None,
        ref_text=None,
        tts_server_url="http://localhost:8100",
        no_concat=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def make_highlight_args(pdf_path, output_dir, **overrides):
    """Build args for the highlight pipeline."""
    defaults = dict(
        command="highlight",
        pdf=pdf_path,
        output_dir=str(output_dir),
        output=None,
        language="en-US",
        status_file="processing_status.json",
        clean=True,
        verbose=False,
        backend="qwen",
        device="cpu",
        voice=None,
        model=None,
        ref_audio=None,
        ref_text=None,
        tts_server_url="http://localhost:8100",
        format="mp4",
        font_size=32,
        resolution="1280x720",
        fps=24,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def make_lipsync_args(pdf_path, output_dir, ref_audio, ref_video, **overrides):
    """Build args for the lipsync pipeline."""
    defaults = dict(
        command="lipsync",
        pdf=pdf_path,
        output_dir=str(output_dir),
        output=None,
        language="en-US",
        status_file="processing_status.json",
        clean=True,
        verbose=False,
        backend="f5",
        device="cpu",
        voice=None,
        model=None,
        ref_audio=ref_audio,
        ref_text=None,
        ref_video=ref_video,
        tts_server_url="http://localhost:8100",
        format="mp4",
        font_size=32,
        resolution="1280x720",
        fps=24,
        face_position="left",
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)
