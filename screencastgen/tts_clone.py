"""Voice cloning TTS backend using F5-TTS.

Imports are deferred so the module can be imported without torch/f5-tts installed.
"""

from typing import Optional

from .constants import DEFAULT_CLONE_CHUNK_BYTES


def _resolve_device(device: str = "auto") -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class F5TTSBackend:
    """TTSBackend implementation using F5-TTS for voice cloning."""

    def __init__(
        self,
        ref_audio_path: str,
        ref_text: Optional[str] = None,
        device: str = "auto",
    ):
        self.ref_audio_path = ref_audio_path
        self.ref_text = ref_text
        self.device = _resolve_device(device)
        self._model = None

    @property
    def max_chunk_bytes(self) -> int:
        return DEFAULT_CLONE_CHUNK_BYTES

    @property
    def output_format(self) -> str:
        return "wav"

    def _ensure_model(self):
        if self._model is not None:
            return

        from f5_tts.api import F5TTS

        self._model = F5TTS(device=self.device)

        # Auto-transcribe reference audio if no text provided
        if self.ref_text is None:
            print("  Auto-transcribing reference audio...")
            import whisperx
            audio = whisperx.load_audio(self.ref_audio_path)
            model = whisperx.load_model("base", self.device, compute_type="float32")
            result = model.transcribe(audio)
            self.ref_text = " ".join(
                seg["text"] for seg in result.get("segments", [])
            ).strip()
            print(f"  Reference text: {self.ref_text[:80]}...")

    def synthesize(self, text: str, output_path: str) -> None:
        """Synthesize *text* using the cloned voice and write to *output_path*."""
        self._ensure_model()

        self._model.infer(
            ref_file=self.ref_audio_path,
            ref_text=self.ref_text,
            gen_text=text,
            file_wave=output_path,
        )
