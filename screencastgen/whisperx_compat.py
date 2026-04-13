"""Compatibility helpers for WhisperX on newer PyTorch releases."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

_PATCH_LOCK = threading.RLock()
_PATCH_DEPTH = 0
_ORIGINAL_TORCH_LOAD = None


@contextmanager
def allow_unsafe_torch_load() -> Iterator[None]:
    """Temporarily force ``torch.load(..., weights_only=False)``.

    PyTorch 2.6 changed the default ``weights_only`` value to ``True``. Some
    WhisperX dependencies still load trusted checkpoints containing config
    objects that are incompatible with weights-only deserialization.

    We patch ``torch.load`` only while WhisperX is loading those checkpoints
    and override any explicit ``weights_only=True`` passed by downstream code.
    """
    import torch

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
    import whisperx

    with allow_unsafe_torch_load():
        return whisperx.load_model(model_name, device, compute_type=compute_type)


def load_whisperx_align_model(*, language_code: str, device: str):
    """Load a WhisperX alignment model with PyTorch 2.6 compatibility enabled."""
    import whisperx

    with allow_unsafe_torch_load():
        return whisperx.load_align_model(language_code=language_code, device=device)
