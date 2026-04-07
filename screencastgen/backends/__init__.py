"""TTS backend registry with lazy imports."""

from typing import Any, Dict, List, Optional

from .base import BackendSpec

_BACKEND_MODULES: Dict[str, str] = {
    "qwen": "screencastgen.backends.qwen_backend",
    "f5": "screencastgen.backends.f5_tts",
    "remote": "screencastgen.backends.remote_tts",
}

BACKEND_NAMES: List[str] = list(_BACKEND_MODULES.keys())


def _import_module(module_path: str):
    import importlib

    return importlib.import_module(module_path)


def get_backend_names(context: Optional[str] = None) -> List[str]:
    """Return backend names available in *context*."""
    if context is None:
        return list(BACKEND_NAMES)
    return [spec.name for spec in iter_backend_specs(context=context)]


def get_default_backend_name(context: Optional[str] = None, preferred: str = "qwen") -> str:
    """Return the default backend name for *context*."""
    names = get_backend_names(context=context)
    if not names:
        raise ValueError(f"No backends registered for context {context!r}")
    return preferred if preferred in names else names[0]


def get_backend_spec(name: str) -> BackendSpec:
    """Load and return the backend spec for *name*."""
    if name not in _BACKEND_MODULES:
        raise ValueError(
            f"Unknown backend {name!r}. Choose from: {', '.join(BACKEND_NAMES)}"
        )

    mod = _import_module(_BACKEND_MODULES[name])
    try:
        spec = getattr(mod, "SPEC")
    except AttributeError as exc:
        raise ValueError(f"Backend {name!r} does not define SPEC") from exc
    return spec


def iter_backend_specs(context: Optional[str] = None) -> List[BackendSpec]:
    """Return all backend specs, optionally filtered by availability context."""
    specs = [get_backend_spec(name) for name in BACKEND_NAMES]
    if context is None:
        return specs
    return [spec for spec in specs if context in spec.contexts]


def register_backend_args(parser, context: str) -> None:
    """Register backend-specific args for all backends available in *context*."""
    seen_flags = set()
    for spec in iter_backend_specs(context=context):
        for arg in spec.extra_args:
            if context not in arg.contexts:
                continue
            if arg.flags in seen_flags:
                continue
            parser.add_argument(*arg.flags, **arg.kwargs)
            seen_flags.add(arg.flags)


def get_downloadable_backend_names() -> List[str]:
    """Return backend names that expose a model download hook."""
    return [spec.name for spec in iter_backend_specs() if spec.download_models is not None]


def register_backend_download_args(parser) -> None:
    """Register backend-specific args used by ``download-models``."""
    seen_flags = set()
    for spec in iter_backend_specs():
        for arg in spec.download_args:
            if "download" not in arg.contexts:
                continue
            if arg.flags in seen_flags:
                continue
            parser.add_argument(*arg.flags, **arg.kwargs)
            seen_flags.add(arg.flags)


def create_backend(name: str, **kwargs: Any):
    """Lazily import and instantiate a TTS backend by *name*."""
    spec = get_backend_spec(name)
    mod = _import_module(spec.module_path)
    cls = getattr(mod, spec.class_name)
    return cls(**kwargs)


def create_backend_from_args(args: Any, invocation: str):
    """Validate parsed args and instantiate the selected backend."""
    parser_context = "server" if invocation == "server" else "cli"
    spec = get_backend_spec(args.backend)
    if parser_context not in spec.contexts:
        allowed = ", ".join(sorted(spec.contexts))
        raise ValueError(
            f"Backend {spec.name!r} is not available in {parser_context} context "
            f"(available in: {allowed})"
        )

    if spec.validate is not None:
        spec.validate(args, invocation)

    kwargs = spec.build_kwargs(args, invocation) if spec.build_kwargs else {}
    return create_backend(spec.name, **kwargs)
