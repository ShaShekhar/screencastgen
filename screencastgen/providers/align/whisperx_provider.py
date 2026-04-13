"""WhisperX alignment provider."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, List

from ..tts.base import resolve_device
from ...types import WordTiming


@contextmanager
def _allow_unsafe_torch_load() -> Iterator[None]:
    """Force ``torch.load(..., weights_only=False)`` inside this block.

    PyTorch 2.6 flipped the default to ``weights_only=True``, which rejects
    pyannote's VAD checkpoint (used by whisperx for segmentation) because
    it pickles ``omegaconf.*`` objects not in the default safe-globals
    allowlist. The checkpoint bytes come from our own HF cache, so
    disabling weights-only just for these loads is safe.
    """
    import torch

    original_load = torch.load

    def patched_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_load(*args, **kwargs)

    torch.load = patched_load
    try:
        yield
    finally:
        torch.load = original_load


def align_with_whisperx(
    audio_path: str,
    text: str,
    *,
    language: str = "en-US",
    device: str = "auto",
) -> List[WordTiming]:
    """Align with WhisperX using transcription plus forced alignment."""
    import whisperx

    device = resolve_device(device)
    lang_code = language.split("-")[0]

    with _allow_unsafe_torch_load():
        model = whisperx.load_model("base", device, compute_type="float32")
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, language=lang_code)

    with _allow_unsafe_torch_load():
        align_model, metadata = whisperx.load_align_model(
            language_code=lang_code,
            device=device,
        )
    result = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        device,
    )

    words = []
    for segment in result.get("word_segments", result.get("segments", [])):
        if "word" in segment and "start" in segment and "end" in segment:
            words.append(
                WordTiming(
                    word=segment["word"].strip(),
                    start=float(segment["start"]),
                    end=float(segment["end"]),
                )
            )
        elif "words" in segment:
            for word in segment["words"]:
                if "start" in word and "end" in word:
                    words.append(
                        WordTiming(
                            word=word["word"].strip(),
                            start=float(word["start"]),
                            end=float(word["end"]),
                        )
                    )

    return words
