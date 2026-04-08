"""Model download and cache management."""

import os
from dataclasses import dataclass
from typing import Callable, Sequence

from .providers.tts import (
    get_backend_spec,
    get_downloadable_backend_names,
    register_backend_download_args,
)
from .providers.tts.base import BackendArg


@dataclass(frozen=True)
class ModelPackageSpec:
    """A downloadable package or model family outside the TTS backend registry."""

    name: str
    download_models: Callable[[object], None]
    download_args: Sequence[BackendArg] = ()


def _get_cache_dir() -> str:
    cache = os.environ.get("SCREENCASTGEN_MODEL_CACHE", "~/.cache/screencastgen/models")
    path = os.path.expanduser(cache)
    os.makedirs(path, exist_ok=True)
    return path


def _download_whisperx(args) -> None:
    print("\n--- Downloading WhisperX models ---")
    try:
        import whisperx as wx

        print("Loading Whisper base model...")
        wx.load_model("base", "cpu", compute_type="float32")
        print("Loading alignment model...")
        wx.load_align_model(language_code="en", device="cpu")
        print("WhisperX models ready.")
    except ImportError:
        print("ERROR: whisperx not installed. Run: pip install whisperx")
    except Exception as exc:
        print(f"ERROR downloading WhisperX models: {exc}")


def _download_latentsync(args) -> None:
    print("\n--- Downloading LatentSync models ---")
    try:
        import latentsync  # noqa: F401

        print("LatentSync package found. Models will be downloaded on first use.")
    except ImportError:
        print(
            "ERROR: latentsync not installed.\n"
            "See: https://github.com/bytedance/LatentSync for installation instructions."
        )


_PACKAGE_SPECS = {
    "whisperx": ModelPackageSpec(name="whisperx", download_models=_download_whisperx),
    "latentsync": ModelPackageSpec(name="latentsync", download_models=_download_latentsync),
}


def get_downloadable_package_names():
    """Return names of downloadable packages outside the TTS backend registry."""
    return list(_PACKAGE_SPECS.keys())


def register_model_download_args(parser) -> None:
    """Register generic and target-specific args for ``download-models``."""
    parser.add_argument(
        "--backend",
        dest="download_backends",
        action="append",
        choices=get_downloadable_backend_names(),
        default=[],
        help="Backend whose models should be downloaded; repeat as needed",
    )
    parser.add_argument(
        "--package",
        dest="download_packages",
        action="append",
        choices=get_downloadable_package_names(),
        default=[],
        help="Downloadable package to preload; repeat as needed",
    )
    parser.add_argument("--all", action="store_true", help="Download all registered models/packages")
    register_backend_download_args(parser)

    seen_flags = set()
    for spec in _PACKAGE_SPECS.values():
        for arg in spec.download_args:
            if "download" not in arg.contexts:
                continue
            if arg.flags in seen_flags:
                continue
            parser.add_argument(*arg.flags, **arg.kwargs)
            seen_flags.add(arg.flags)


def download_selected_models(args) -> None:
    """Download the backend and package models selected by parsed args."""
    selected_backends = list(args.download_backends or [])
    selected_packages = list(args.download_packages or [])

    if args.all:
        selected_backends = get_downloadable_backend_names()
        selected_packages = get_downloadable_package_names()

    if not selected_backends and not selected_packages:
        print("No models specified. Use --backend, --package, or --all")
        return

    cache_dir = _get_cache_dir()
    print(f"Model cache directory: {cache_dir}")

    for name in selected_packages:
        _PACKAGE_SPECS[name].download_models(args)

    for name in selected_backends:
        spec = get_backend_spec(name)
        if spec.download_models is None:
            print(f"\n--- Skipping backend {name}: no download hook registered ---")
            continue
        spec.download_models(args)

    print("\nDone.")
