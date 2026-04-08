"""Qwen3-TTS backend for self-hosted speech synthesis.

Imports are deferred so the module can be imported without qwen-tts/torch installed.
"""

from typing import Optional

from .base import BackendArg, BackendSpec, resolve_device


_MODEL_ALIASES = {
    "0.6b": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "0.6B": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "1.7b": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
}

DEFAULT_QWEN_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"

_LANG_MAP = {
    "en": "English",
    "en-us": "English",
    "en-gb": "English",
    "zh": "Chinese",
    "zh-cn": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "ru": "Russian",
    "pt": "Portuguese",
    "es": "Spanish",
    "it": "Italian",
}


class QwenTTS:
    """TTSBackend implementation using Qwen3-TTS for local speech synthesis."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        ref_audio_path: Optional[str] = None,
        ref_text: Optional[str] = None,
        language: str = "en-US",
        device: str = "auto",
    ):
        self._model_name = _MODEL_ALIASES.get(model_name, model_name) if model_name else DEFAULT_QWEN_MODEL
        self.ref_audio_path = ref_audio_path
        self.ref_text = ref_text
        self._language = _LANG_MAP.get(language.lower(), "English")
        self.device = resolve_device(device)
        self._model = None

    @property
    def max_chunk_bytes(self) -> int:
        return 20000

    @property
    def output_format(self) -> str:
        return "wav"

    def _ensure_model(self):
        if self._model is not None:
            return

        import torch
        from qwen_tts import Qwen3TTSModel

        dtype = torch.bfloat16 if self.device != "cpu" else torch.float32

        print(f"  Loading Qwen3-TTS model: {self._model_name} on {self.device}...")
        self._model = Qwen3TTSModel.from_pretrained(
            self._model_name,
            device_map=self.device if self.device == "cpu" else f"{self.device}:0",
            dtype=dtype,
        )

    def synthesize(self, text: str, output_path: str) -> None:
        """Synthesize *text* and write audio to *output_path*."""
        self._ensure_model()
        import soundfile as sf

        if self.ref_audio_path:
            wavs, sr = self._model.generate_voice_clone(
                text=text,
                language=self._language,
                ref_audio=self.ref_audio_path,
                ref_text=self.ref_text or "",
            )
        else:
            wavs, sr = self._model.generate_custom_voice(
                text=text,
                language=self._language,
            )

        sf.write(output_path, wavs[0], sr)


def _build_kwargs(args, invocation: str):
    return {
        "model_name": getattr(args, "model", None),
        "ref_audio_path": getattr(args, "ref_audio", None),
        "ref_text": getattr(args, "ref_text", None),
        "language": getattr(args, "language", "en-US"),
        "device": getattr(args, "device", "auto"),
    }


def _validate(args, invocation: str) -> None:
    if invocation == "lipsync" and not getattr(args, "ref_audio", None):
        raise ValueError("Error: --ref-audio is required for the qwen backend in lipsync mode")


def _download_models(args) -> None:
    model_name = _MODEL_ALIASES.get(getattr(args, "model", None), getattr(args, "model", None)) or DEFAULT_QWEN_MODEL

    print(f"\n--- Downloading Qwen3-TTS model: {model_name} ---")
    try:
        import torch
        from qwen_tts import Qwen3TTSModel

        print(f"Loading {model_name}...")
        Qwen3TTSModel.from_pretrained(
            model_name,
            device_map="cpu",
            dtype=torch.float32,
        )
        print("Qwen3-TTS model ready.")
    except ImportError:
        print("ERROR: qwen-tts not installed. Run: pip install 'screencastgen[qwen]'")
    except Exception as exc:
        print(f"ERROR downloading Qwen3-TTS model: {exc}")


_MODEL_ARG = BackendArg(
    ("--model",),
    {
        "default": None,
        "help": "Model name/path for local backends (e.g. 0.6B, 1.7B for qwen)",
    },
)


SPEC = BackendSpec(
    name="qwen",
    module_path=__name__,
    class_name="QwenTTS",
    contexts=frozenset({"cli", "server"}),
    capabilities=frozenset({"local", "voice_clone"}),
    extra_args=(_MODEL_ARG,),
    download_args=(
        BackendArg(_MODEL_ARG.flags, dict(_MODEL_ARG.kwargs), contexts=frozenset({"download"})),
    ),
    build_kwargs=_build_kwargs,
    validate=_validate,
    download_models=_download_models,
)
