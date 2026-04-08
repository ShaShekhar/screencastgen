"""Shared backend metadata and helpers."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, Optional, Sequence, Tuple


def resolve_device(device: str = "auto") -> str:
    """Resolve ``auto`` to ``cuda`` when available, otherwise ``cpu``."""
    if device != "auto":
        return device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


@dataclass(frozen=True)
class BackendArg:
    """A backend-defined CLI/server argument."""

    flags: Tuple[str, ...]
    kwargs: Dict[str, Any] = field(default_factory=dict)
    contexts: FrozenSet[str] = frozenset({"cli", "server"})


@dataclass(frozen=True)
class BackendSpec:
    """Metadata and hooks for a TTS backend."""

    name: str
    module_path: str
    class_name: str
    contexts: FrozenSet[str] = frozenset({"cli", "server"})
    capabilities: FrozenSet[str] = frozenset()
    extra_args: Sequence[BackendArg] = ()
    download_args: Sequence[BackendArg] = ()
    build_kwargs: Optional[Callable[[Any, str], Dict[str, Any]]] = None
    validate: Optional[Callable[[Any, str], None]] = None
    download_models: Optional[Callable[[Any], None]] = None
