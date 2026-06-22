"""Registry for lip-sync providers."""

from __future__ import annotations

from typing import Dict, List

from .base import LipsyncProviderSpec

DEFAULT_LIPSYNC_PROVIDER = "auto"

_LIPSYNC_PROVIDERS: Dict[str, LipsyncProviderSpec] = {
    "latentsync": LipsyncProviderSpec(
        name="latentsync",
        module_path="screencastgen.providers.lipsync.latentsync_provider",
        function_name="run_latentsync",
    ),
}


def _import_module(module_path: str):
    import importlib

    return importlib.import_module(module_path)


def get_lipsync_provider_names() -> List[str]:
    """Return registered lip-sync provider names, including auto mode."""
    return [DEFAULT_LIPSYNC_PROVIDER, *_LIPSYNC_PROVIDERS.keys()]


def get_default_lipsync_provider() -> str:
    """Return the default lip-sync provider."""
    return DEFAULT_LIPSYNC_PROVIDER


def get_auto_lipsync_provider() -> str:
    """Return the first registered provider used by auto mode."""
    if not _LIPSYNC_PROVIDERS:
        raise RuntimeError("No lip-sync providers are registered")
    return next(iter(_LIPSYNC_PROVIDERS))


def get_lipsync_provider_spec(name: str) -> LipsyncProviderSpec:
    """Return metadata for the named lip-sync provider."""
    if name not in _LIPSYNC_PROVIDERS:
        raise ValueError(
            f"Unknown lip-sync provider {name!r}. "
            f"Choose from: {', '.join(get_lipsync_provider_names())}"
        )

    return _LIPSYNC_PROVIDERS[name]


def run_lipsync_provider(
    provider: str,
    video_path: str,
    audio_path: str,
    output_path: str,
    *,
    device: str,
    **kwargs,
):
    """Run the selected lip-sync provider."""
    spec = get_lipsync_provider_spec(provider)
    mod = _import_module(spec.module_path)
    fn = getattr(mod, spec.function_name)
    return fn(video_path, audio_path, output_path, device=device, **kwargs)
