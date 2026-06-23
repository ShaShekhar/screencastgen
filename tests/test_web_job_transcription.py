"""Tests for on-demand reference transcription in web pipeline jobs."""

from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from web.backend.tasks import pipelines


class _Session:
    def __init__(self, uploaded):
        self.uploaded = uploaded

    def get(self, _model, _file_id):
        return self.uploaded


def _uploaded():
    return SimpleNamespace(stored_path="stored/voice.wav", ref_text=None)


def test_highlight_transcribes_reference_audio_during_job(monkeypatch):
    file_id = uuid.uuid4()
    uploaded = _uploaded()
    job = SimpleNamespace(ref_audio_file_id=file_id)
    transcribe = Mock(return_value="spoken reference text")
    monkeypatch.setattr(pipelines, "get_upload_abs_path", lambda _path: "/tmp/voice.wav")
    monkeypatch.setattr(pipelines, "transcribe_upload", transcribe)

    path, text = pipelines._resolve_highlight_voice(
        {"language": "en-US", "tts_server_url": "http://gpu:8100"},
        job,
        _Session(uploaded),
    )

    assert path == "/tmp/voice.wav"
    assert text == "spoken reference text"
    assert uploaded.ref_text == text
    transcribe.assert_called_once_with(
        "http://gpu:8100", "/tmp/voice.wav", language="en-US"
    )


def test_highlight_reuses_cached_reference_transcript(monkeypatch):
    uploaded = _uploaded()
    uploaded.ref_text = "cached text"
    transcribe = Mock()
    monkeypatch.setattr(pipelines, "get_upload_abs_path", lambda _path: "/tmp/voice.wav")
    monkeypatch.setattr(pipelines, "transcribe_upload", transcribe)

    _path, text = pipelines._resolve_highlight_voice(
        {},
        SimpleNamespace(ref_audio_file_id=uuid.uuid4()),
        _Session(uploaded),
    )

    assert text == "cached text"
    transcribe.assert_not_called()


def test_lipsync_transcribes_uploaded_reference_audio_during_job(monkeypatch):
    uploaded = _uploaded()
    transcribe = Mock(return_value="lip sync reference")
    monkeypatch.setattr(pipelines, "get_upload_abs_path", lambda _path: "/tmp/voice.wav")
    monkeypatch.setattr(pipelines, "transcribe_upload", transcribe)

    request = pipelines._build_lipsync_request(
        SimpleNamespace(
            config_json={"language": "en-US", "tts_server_url": "http://gpu:8100"},
            ref_audio_file_id=uuid.uuid4(),
            ref_video_file_id=None,
        ),
        "/tmp/document.pdf",
        "/tmp/output",
        _Session(uploaded),
    )

    assert request.ref_text == "lip sync reference"
    assert uploaded.ref_text == request.ref_text


def test_job_fails_clearly_when_reference_transcription_fails(monkeypatch):
    uploaded = _uploaded()
    monkeypatch.setattr(pipelines, "get_upload_abs_path", lambda _path: "/tmp/voice.wav")
    monkeypatch.setattr(pipelines, "transcribe_upload", lambda *_args, **_kwargs: None)

    with pytest.raises(ValueError, match="Could not transcribe reference audio"):
        pipelines._resolve_highlight_voice(
            {},
            SimpleNamespace(ref_audio_file_id=uuid.uuid4()),
            _Session(uploaded),
        )


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ("reader", "document_reader.zip"),
        ("epub", "document_lipsync.epub"),
        ("mp4", "document_lipsync.mp4"),
    ],
)
def test_lipsync_web_output_names_follow_format(fmt, expected):
    request = pipelines._build_lipsync_request(
        SimpleNamespace(
            config_json={},
            ref_audio_file_id=None,
            ref_video_file_id=None,
        ),
        "/tmp/document.pdf",
        "/tmp/output",
        _Session(None),
        fmt=fmt,
    )

    assert request.output == expected
