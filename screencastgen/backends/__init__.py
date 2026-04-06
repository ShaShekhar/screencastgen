"""TTS backend registry with lazy imports."""

from typing import Any, Dict, List

_BACKENDS: Dict[str, tuple] = {
    "qwen": ("screencastgen.backends.qwen_tts", "QwenTTS"),
    "f5": ("screencastgen.backends.f5_tts", "F5TTSBackend"),
    "remote": ("screencastgen.backends.remote_tts", "RemoteTTS"),
}

BACKEND_NAMES: List[str] = list(_BACKENDS.keys())


def create_backend(name: str, **kwargs: Any):
    """Lazily import and instantiate a TTS backend by *name*."""
    if name not in _BACKENDS:
        raise ValueError(
            f"Unknown backend {name!r}. Choose from: {', '.join(BACKEND_NAMES)}"
        )
    import importlib

    module_path, class_name = _BACKENDS[name]
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls(**kwargs)
