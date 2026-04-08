"""Registry for alignment providers."""

from __future__ import annotations

from typing import Dict, List

from .base import AlignmentProviderSpec

DEFAULT_ALIGNMENT_PROVIDER = "whisperx"

_ALIGNMENT_MODULES: Dict[str, str] = {
    "whisperx": "screencastgen.providers.align.whisperx_provider",
}


def _import_module(module_path: str):
    import importlib

    return importlib.import_module(module_path)


def get_alignment_provider_names() -> List[str]:
    """Return registered alignment provider names."""
    return list(_ALIGNMENT_MODULES.keys())


def get_default_alignment_provider() -> str:
    """Return the default alignment provider."""
    return DEFAULT_ALIGNMENT_PROVIDER


def get_alignment_provider_spec(name: str) -> AlignmentProviderSpec:
    """Return metadata for the named alignment provider."""
    if name not in _ALIGNMENT_MODULES:
        raise ValueError(
            f"Unknown alignment provider {name!r}. "
            f"Choose from: {', '.join(get_alignment_provider_names())}"
        )

    module_path = _ALIGNMENT_MODULES[name]
    function_name = "align_with_whisperx" if name == "whisperx" else "align"
    return AlignmentProviderSpec(
        name=name,
        module_path=module_path,
        function_name=function_name,
    )


def align_with_provider(
    provider: str,
    audio_path: str,
    text: str,
    *,
    language: str = "en-US",
    device: str = "auto",
):
    """Run the selected alignment provider."""
    spec = get_alignment_provider_spec(provider)
    mod = _import_module(spec.module_path)
    fn = getattr(mod, spec.function_name)
    return fn(
        audio_path,
        text,
        language=language,
        device=device,
    )
