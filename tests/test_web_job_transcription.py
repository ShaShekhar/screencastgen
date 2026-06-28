"""Tests for on-demand reference transcription in web pipeline jobs."""

from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest
from pydantic import ValidationError

from web.backend.schemas import LipsyncConfig
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


def test_lipsync_uses_bundled_preset_paths_without_uploads(monkeypatch):
    from web.backend.services import lipsync_presets

    preset = SimpleNamespace(
        id="default-presenter",
        video_exists=True,
        audio_exists=True,
        video_abs_path="/presets/default-presenter.mp4",
        audio_abs_path="/presets/default-presenter.wav",
        audio_file="default-presenter.wav",
        ref_text="bundled reference text",
        language="en-US",
    )
    transcribe = Mock()
    monkeypatch.setattr(lipsync_presets, "get_lipsync_preset", lambda _id: preset)
    monkeypatch.setattr(pipelines, "transcribe_upload", transcribe)

    request = pipelines._build_lipsync_request(
        SimpleNamespace(
            config_json={"preset_id": "default-presenter"},
            ref_audio_file_id=uuid.uuid4(),
            ref_video_file_id=uuid.uuid4(),
        ),
        "/tmp/document.pdf",
        "/tmp/output",
        _Session(None),
    )

    assert request.ref_video == "/presets/default-presenter.mp4"
    assert request.ref_audio == "/presets/default-presenter.wav"
    assert request.ref_text == "bundled reference text"
    transcribe.assert_not_called()


def test_lipsync_config_accepts_bundled_preset_without_uploaded_refs():
    cfg = LipsyncConfig(preset_id="default-presenter")

    assert cfg.preset_id == "default-presenter"
    assert cfg.ref_video_file_id is None


def test_lipsync_config_rejects_mixed_preset_and_upload_refs():
    with pytest.raises(ValidationError, match="preset_id"):
        LipsyncConfig(
            preset_id="default-presenter",
            ref_video_file_id=uuid.uuid4(),
        )


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
