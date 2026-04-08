"""F5-TTS backend shim and backend spec."""

from .base import BackendSpec
from screencastgen.tts_clone import F5TTSBackend  # noqa: F401


def _build_kwargs(args, invocation: str):
    return {
        "ref_audio_path": getattr(args, "ref_audio", None),
        "ref_text": getattr(args, "ref_text", None),
        "device": getattr(args, "device", "auto"),
    }


def _validate(args, invocation: str) -> None:
    if not getattr(args, "ref_audio", None):
        raise ValueError("Error: --ref-audio is required for the f5 backend")


def _download_models(args) -> None:
    print("\n--- Downloading F5-TTS models ---")
    try:
        from f5_tts.api import F5TTS

        print("Loading F5-TTS model...")
        F5TTS(device="cpu")
        print("F5-TTS model ready.")
    except ImportError:
        print("ERROR: f5-tts not installed. Run: pip install f5-tts")
    except Exception as exc:
        print(f"ERROR downloading F5-TTS models: {exc}")


SPEC = BackendSpec(
    name="f5",
    module_path=__name__,
    class_name="F5TTSBackend",
    contexts=frozenset({"cli", "server"}),
    capabilities=frozenset({"local", "voice_clone", "requires_ref_audio"}),
    build_kwargs=_build_kwargs,
    validate=_validate,
    download_models=_download_models,
)
