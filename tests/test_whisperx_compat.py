"""Tests for WhisperX compatibility helpers."""

from types import SimpleNamespace

from screencastgen.whisperx_compat import patch_torchaudio_audiometadata


def test_patch_torchaudio_audiometadata_adds_missing_alias(monkeypatch):
    fake_torchaudio = SimpleNamespace()
    monkeypatch.setitem(__import__("sys").modules, "torchaudio", fake_torchaudio)

    patch_torchaudio_audiometadata()

    assert hasattr(fake_torchaudio, "AudioMetaData")
    metadata = fake_torchaudio.AudioMetaData(
        sample_rate=48000,
        num_frames=1024,
        num_channels=2,
        bits_per_sample=16,
        encoding="PCM_S",
    )
    assert metadata.sample_rate == 48000
    assert metadata.num_channels == 2


def test_patch_torchaudio_audiometadata_preserves_existing_alias(monkeypatch):
    existing = object()
    fake_torchaudio = SimpleNamespace(AudioMetaData=existing)
    monkeypatch.setitem(__import__("sys").modules, "torchaudio", fake_torchaudio)

    patch_torchaudio_audiometadata()

    assert fake_torchaudio.AudioMetaData is existing
