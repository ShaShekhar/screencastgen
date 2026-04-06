"""Word-level audio alignment using WhisperX.

Imports are deferred so the module can be imported without torch installed.
"""

from typing import List

from .types import WordTiming


def _resolve_device(device: str = "auto") -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def align_chunk(
    audio_path: str,
    text: str,
    *,
    language: str = "en-US",
    device: str = "auto",
) -> List[WordTiming]:
    """Align *text* against *audio_path* and return per-word timestamps.

    Uses WhisperX: transcribe with Whisper, then refine timestamps
    via wav2vec2 forced alignment.
    """
    import whisperx

    device = _resolve_device(device)
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
