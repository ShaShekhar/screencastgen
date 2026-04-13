"""WhisperX alignment provider."""

from __future__ import annotations

from typing import List

from ..tts.base import resolve_device
from ...types import WordTiming
from ...whisperx_compat import load_whisperx_align_model, load_whisperx_model


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

    model = load_whisperx_model("base", device, compute_type="float32")
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, language=lang_code)

    align_model, metadata = load_whisperx_align_model(
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
