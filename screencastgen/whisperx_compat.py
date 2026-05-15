"""Compatibility helpers for WhisperX on newer PyTorch releases."""

from __future__ import annotations

import ctypes
import threading
from contextlib import contextmanager
from typing import Iterator, NamedTuple

_PATCH_LOCK = threading.RLock()
_PATCH_DEPTH = 0
_ORIGINAL_TORCH_LOAD = None


def resolve_whisperx_device(device: str) -> str:
    """Resolve the device WhisperX should actually use.

    WhisperX/pyannote can abort the process when CUDA is selected but the
    cuDNN 8 runtime it expects is not installed. In that case we fall back
    to CPU for WhisperX only so TTS or other GPU workloads can still use the
    configured device.
    """
    if device != "cuda":
        return device

    try:
        ctypes.CDLL("libcudnn_ops_infer.so.8")
    except OSError as exc:
        print(
            "WARNING: WhisperX CUDA runtime unavailable "
            f"({exc}). Falling back to CPU for WhisperX."
        )
        return "cpu"

    return device


def patch_torchaudio_audiometadata() -> None:
    """Restore the legacy ``torchaudio.AudioMetaData`` name for pyannote.

    Some pyannote.audio releases used by WhisperX evaluate this type annotation
    at import time. Newer TorchAudio releases moved or removed the top-level
    alias, which makes ``import whisperx`` fail before screencastgen can use the
    model. The attribute is only needed as a type object during import.
    """
    try:
        import torchaudio
    except Exception:
        return

    if hasattr(torchaudio, "AudioMetaData"):
        return

    try:
        from torchaudio._backend.common import AudioMetaData
    except Exception:

        class AudioMetaData(NamedTuple):
            sample_rate: int
            num_frames: int
            num_channels: int
            bits_per_sample: int
            encoding: str

    torchaudio.AudioMetaData = AudioMetaData


@contextmanager
def allow_unsafe_torch_load() -> Iterator[None]:
    """Temporarily force ``torch.load(..., weights_only=False)``.

    PyTorch 2.6 changed the default ``weights_only`` value to ``True``. Some
    WhisperX dependencies still load trusted checkpoints containing config
    objects that are incompatible with weights-only deserialization.

    We patch ``torch.load`` only while WhisperX is loading those checkpoints
    and override any explicit ``weights_only=True`` passed by downstream code.
    """
    try:
        import torch
    except Exception:
        yield
        return

    global _PATCH_DEPTH, _ORIGINAL_TORCH_LOAD

    with _PATCH_LOCK:
        if _PATCH_DEPTH == 0:
            _ORIGINAL_TORCH_LOAD = torch.load

            def patched_load(*args, **kwargs):
                kwargs["weights_only"] = False
                return _ORIGINAL_TORCH_LOAD(*args, **kwargs)

            torch.load = patched_load
        _PATCH_DEPTH += 1

    try:
        yield
    finally:
        with _PATCH_LOCK:
            _PATCH_DEPTH -= 1
            if _PATCH_DEPTH == 0 and _ORIGINAL_TORCH_LOAD is not None:
                torch.load = _ORIGINAL_TORCH_LOAD
                _ORIGINAL_TORCH_LOAD = None


def load_whisperx_model(model_name: str, device: str, *, compute_type: str):
    """Load a WhisperX ASR model with PyTorch 2.6 compatibility enabled."""
    patch_torchaudio_audiometadata()
    import whisperx

    device = resolve_whisperx_device(device)
    with allow_unsafe_torch_load():
        return whisperx.load_model(model_name, device, compute_type=compute_type)


def load_whisperx_align_model(*, language_code: str, device: str):
    """Load a WhisperX alignment model with PyTorch 2.6 compatibility enabled."""
    patch_torchaudio_audiometadata()
    import whisperx

    device = resolve_whisperx_device(device)
    with allow_unsafe_torch_load():
        return whisperx.load_align_model(language_code=language_code, device=device)
