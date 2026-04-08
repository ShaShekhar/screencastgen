"""Registry for lip-sync providers."""

from __future__ import annotations

from typing import Dict, List

from .base import LipsyncProviderSpec

DEFAULT_LIPSYNC_PROVIDER = "auto"

_LIPSYNC_MODULES: Dict[str, str] = {
    "latentsync": "screencastgen.providers.lipsync.latentsync_provider",
    "wav2lip": "screencastgen.providers.lipsync.wav2lip_provider",
}


def _import_module(module_path: str):
    import importlib

    return importlib.import_module(module_path)


def get_lipsync_provider_names() -> List[str]:
    """Return registered lip-sync provider names, including auto mode."""
    return [DEFAULT_LIPSYNC_PROVIDER, *_LIPSYNC_MODULES.keys()]


def get_default_lipsync_provider() -> str:
    """Return the default lip-sync provider."""
    return DEFAULT_LIPSYNC_PROVIDER


def get_lipsync_provider_spec(name: str) -> LipsyncProviderSpec:
    """Return metadata for the named lip-sync provider."""
    if name not in _LIPSYNC_MODULES:
        raise ValueError(
            f"Unknown lip-sync provider {name!r}. "
            f"Choose from: {', '.join(get_lipsync_provider_names())}"
        )

    module_path = _LIPSYNC_MODULES[name]
    function_name = "run_latentsync" if name == "latentsync" else "run_wav2lip"
    return LipsyncProviderSpec(
        name=name,
        module_path=module_path,
        function_name=function_name,
    )


def run_lipsync_provider(provider: str, video_path: str, audio_path: str, output_path: str, *, device: str):
    """Run the selected lip-sync provider."""
    spec = get_lipsync_provider_spec(provider)
    mod = _import_module(spec.module_path)
    fn = getattr(mod, spec.function_name)
    if provider == "latentsync":
        return fn(video_path, audio_path, output_path, device)
    return fn(video_path, audio_path, output_path)
