"""Audio → text transcription helper.

Used to auto-generate ``ref_text`` for voice-cloning reference clips so
Qwen3-TTS / F5-TTS can run in ICL (in-context learning) mode instead of
falling back to speaker-embedding-only synthesis.

Imports are deferred so this module can be imported without whisperx
installed; callers get a clear ImportError only when they actually try
to transcribe.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from .providers.tts.base import resolve_device


@dataclass
class _LoadedTranscriber:
    model: object
    lock: threading.Lock


_MODEL_CACHE: dict[tuple[str, str, str], _LoadedTranscriber] = {}
_CACHE_LOCK = threading.Lock()


def _get_transcriber(
    model_name: str,
    device: str,
    compute_type: str,
) -> _LoadedTranscriber:
    key = (model_name, device, compute_type)
    with _CACHE_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached

        import whisperx

        model = whisperx.load_model(model_name, device, compute_type=compute_type)
        loaded = _LoadedTranscriber(model=model, lock=threading.Lock())
        _MODEL_CACHE[key] = loaded
        return loaded


def transcribe_audio(
    audio_path: str,
    *,
    language: str = "en-US",
    device: str = "auto",
    model_name: str = "base",
) -> str:
    """Return the plain-text transcript of *audio_path* using WhisperX.

    Only the Whisper transcription step runs here — forced alignment is
    skipped because we just need the words, not their timestamps.
    """
    import whisperx

    device = resolve_device(device)
    lang_code = language.split("-")[0]

    compute_type = "float16" if device == "cuda" else "float32"
    transcriber = _get_transcriber(model_name, device, compute_type)
    audio = whisperx.load_audio(audio_path)
    with transcriber.lock:
        result = transcriber.model.transcribe(audio, language=lang_code)

    segments = result.get("segments", []) or []
    text = " ".join((seg.get("text") or "").strip() for seg in segments).strip()
    return text
