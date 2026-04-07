"""Word-level audio alignment with provider dispatch.

Imports are deferred so the module can be imported without heavy ML deps.
"""

from typing import List

from .backends.base import resolve_device
from .types import WordTiming

DEFAULT_ALIGNMENT_PROVIDER = "whisperx"


def get_alignment_provider_names() -> List[str]:
    """Return registered alignment provider names."""
    return [DEFAULT_ALIGNMENT_PROVIDER]


def get_default_alignment_provider() -> str:
    """Return the default alignment provider."""
    return DEFAULT_ALIGNMENT_PROVIDER


def _align_with_whisperx(
    audio_path: str,
    text: str,
    *,
    language: str = "en-US",
    device: str = "auto",
) -> List[WordTiming]:
    """Align with WhisperX using transcription plus forced alignment."""
    import whisperx

    device = resolve_device(device)
    # WhisperX uses 2-letter language codes
    lang_code = language.split("-")[0]

    # Step 1: Transcribe to get initial segments
    model = whisperx.load_model("base", device, compute_type="float32")
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, language=lang_code)

    # Step 2: Forced alignment for word-level timestamps
    align_model, metadata = whisperx.load_align_model(
        language_code=lang_code, device=device,
    )
    result = whisperx.align(
        result["segments"], align_model, metadata, audio, device,
    )

    # Extract word timings
    words = []
    for segment in result.get("word_segments", result.get("segments", [])):
        # word_segments is flat list; segments may have nested words
        if "word" in segment and "start" in segment and "end" in segment:
            words.append(WordTiming(
                word=segment["word"].strip(),
                start=float(segment["start"]),
                end=float(segment["end"]),
            ))
        elif "words" in segment:
            for w in segment["words"]:
                if "start" in w and "end" in w:
                    words.append(WordTiming(
                        word=w["word"].strip(),
                        start=float(w["start"]),
                        end=float(w["end"]),
                    ))

    return words


def align_chunk(
    audio_path: str,
    text: str,
    *,
    provider: str = DEFAULT_ALIGNMENT_PROVIDER,
    language: str = "en-US",
    device: str = "auto",
) -> List[WordTiming]:
    """Align *text* against *audio_path* via the selected provider."""
    if provider != DEFAULT_ALIGNMENT_PROVIDER:
        raise ValueError(
            f"Unknown alignment provider {provider!r}. "
            f"Choose from: {', '.join(get_alignment_provider_names())}"
        )

    return _align_with_whisperx(
        audio_path,
        text,
        language=language,
        device=device,
    )
