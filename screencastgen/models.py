"""Model download and cache management."""

import os
from dataclasses import dataclass
from typing import Callable, Sequence

from .providers.lipsync.latentsync_provider import download_latentsync_checkpoints
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
        download_latentsync_checkpoints(
            root=getattr(args, "latentsync_root", None),
            python_executable=getattr(args, "latentsync_python", None),
            hf_repo=getattr(args, "latentsync_hf_repo", "ByteDance/LatentSync-1.6"),
            checkpoint_file=getattr(args, "latentsync_checkpoint_file", "latentsync_unet.pt"),
            audio_checkpoint=getattr(args, "latentsync_audio_checkpoint", "whisper/tiny.pt"),
        )
        print("LatentSync checkpoints downloaded.")
    except ImportError:
        print(
            "ERROR: LatentSync runtime not configured.\n"
            "Set LATENTSYNC_ROOT and LATENTSYNC_PYTHON, or run scripts/install_latentsync.sh."
        )
    except Exception as exc:
        print(f"ERROR downloading LatentSync models: {exc}")


_LATENTSYNC_DOWNLOAD_ARGS = (
    BackendArg(
        flags=("--latentsync-root",),
        kwargs={
            "default": None,
            "help": "Path to the LatentSync repo clone (defaults: ./external/LatentSync, ./LatentSync)",
        },
        contexts=frozenset({"download"}),
    ),
    BackendArg(
        flags=("--latentsync-python",),
        kwargs={
            "default": None,
            "help": "Python executable for the dedicated LatentSync env",
        },
        contexts=frozenset({"download"}),
    ),
    BackendArg(
        flags=("--latentsync-hf-repo",),
        kwargs={
            "default": "ByteDance/LatentSync-1.6",
            "help": "Hugging Face repo used for LatentSync checkpoints (default: ByteDance/LatentSync-1.6)",
        },
        contexts=frozenset({"download"}),
    ),
    BackendArg(
        flags=("--latentsync-checkpoint-file",),
        kwargs={
            "default": "latentsync_unet.pt",
            "help": "Checkpoint filename inside the Hugging Face repo (default: latentsync_unet.pt)",
        },
        contexts=frozenset({"download"}),
    ),
    BackendArg(
        flags=("--latentsync-audio-checkpoint",),
        kwargs={
            "default": "whisper/tiny.pt",
            "help": "Audio encoder checkpoint filename inside the Hugging Face repo (default: whisper/tiny.pt)",
        },
        contexts=frozenset({"download"}),
    ),
)


_PACKAGE_SPECS = {
    "whisperx": ModelPackageSpec(name="whisperx", download_models=_download_whisperx),
    "latentsync": ModelPackageSpec(
        name="latentsync",
        download_models=_download_latentsync,
        download_args=_LATENTSYNC_DOWNLOAD_ARGS,
    ),
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
