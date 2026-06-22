"""Non-mutating environment diagnostics for supported setup profiles."""

from __future__ import annotations

import ctypes
import importlib
import json
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


PROFILES = ("auto", "local-gpu", "remote-client", "dev")
QWEN_MODELS = {
    "0.6B": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
}


@dataclass(frozen=True)
class CheckResult:
    level: str
    name: str
    detail: str


def is_wsl() -> bool:
    if platform.system() != "Linux":
        return False
    text = " ".join((platform.release(), platform.version())).lower()
    return "microsoft" in text or "wsl" in text


def nvidia_available() -> bool:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return False
    return subprocess.run(
        [executable, "-L"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0


def resolve_profile(profile: str) -> str:
    if profile != "auto":
        return profile
    if platform.system() == "Linux" and nvidia_available():
        return "local-gpu"
    return "remote-client"


def _command(name: str) -> CheckResult:
    path = shutil.which(name)
    return CheckResult("OK" if path else "FAIL", name, path or "not found in PATH")


def _module(import_name: str, label: str | None = None) -> CheckResult:
    try:
        importlib.import_module(import_name)
    except Exception as exc:
        return CheckResult("FAIL", label or import_name, f"import failed: {exc}")
    return CheckResult("OK", label or import_name, "importable")


def _huggingface_repo(repo_id: str, label: str) -> CheckResult:
    try:
        from huggingface_hub import scan_cache_dir

        repos = {repo.repo_id for repo in scan_cache_dir().repos}
    except Exception as exc:
        return CheckResult("FAIL", label, f"cannot inspect Hugging Face cache: {exc}")
    if repo_id in repos:
        return CheckResult("OK", label, f"cached ({repo_id})")
    return CheckResult("FAIL", label, f"not cached; expected {repo_id}")


def _latentsync() -> Iterable[CheckResult]:
    try:
        from .providers.lipsync.latentsync_provider import (
            find_latentsync_python,
            find_latentsync_root,
        )

        root = Path(find_latentsync_root())
        python = Path(find_latentsync_python())
    except Exception as exc:
        yield CheckResult("FAIL", "LatentSync runtime", str(exc))
        return
    yield CheckResult("OK", "LatentSync repository", str(root))
    yield CheckResult("OK", "LatentSync Python", str(python))
    checkpoint = root / "checkpoints" / "latentsync_unet.pt"
    audio = root / "checkpoints" / "whisper" / "tiny.pt"
    yield CheckResult(
        "OK" if checkpoint.is_file() else "FAIL",
        "LatentSync checkpoint",
        str(checkpoint),
    )
    yield CheckResult(
        "OK" if audio.is_file() else "FAIL",
        "LatentSync audio checkpoint",
        str(audio),
    )


def _cuda() -> Iterable[CheckResult]:
    try:
        import torch
    except Exception as exc:
        yield CheckResult("FAIL", "PyTorch CUDA", f"torch import failed: {exc}")
        return
    if not torch.cuda.is_available():
        yield CheckResult("FAIL", "PyTorch CUDA", "torch.cuda.is_available() is false")
        return
    yield CheckResult("OK", "PyTorch CUDA", torch.cuda.get_device_name(0))
    try:
        ctypes.CDLL("libcudnn_ops_infer.so.8")
    except OSError:
        yield CheckResult(
            "WARN",
            "WhisperX cuDNN 8",
            "unavailable; WhisperX will use its CPU fallback",
        )
    else:
        yield CheckResult("OK", "WhisperX cuDNN 8", "loadable")


def _remote_server(url: str) -> CheckResult:
    endpoint = f"{url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(endpoint, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return CheckResult("FAIL", "remote GPU server", f"{endpoint}: {exc}")
    required = {"synthesize", "transcribe", "align", "lipsync"}
    capabilities = set(payload.get("capabilities", []))
    missing = sorted(required - capabilities)
    if payload.get("status") != "ok":
        return CheckResult("FAIL", "remote GPU server", f"server is not ready: {payload}")
    if missing:
        return CheckResult(
            "FAIL", "remote GPU server", f"missing capabilities: {', '.join(missing)}"
        )
    return CheckResult(
        "OK",
        "remote GPU server",
        f"ready ({payload.get('backend')}, {payload.get('device')})",
    )


def _frontend() -> CheckResult:
    directory = Path(__file__).resolve().parents[1] / "web" / "frontend" / "node_modules"
    return CheckResult(
        "OK" if directory.is_dir() else "FAIL",
        "frontend dependencies",
        str(directory)
        if directory.is_dir()
        else "not installed; run npm install in web/frontend",
    )


def _whisper_alignment() -> CheckResult:
    try:
        import torch

        checkpoint_dir = Path(torch.hub.get_dir()) / "checkpoints"
        candidates = list(checkpoint_dir.glob("*wav2vec*")) + list(
            checkpoint_dir.glob("*hubert*")
        )
    except Exception as exc:
        return CheckResult("FAIL", "WhisperX alignment weights", f"cannot inspect cache: {exc}")
    if candidates:
        return CheckResult("OK", "WhisperX alignment weights", str(candidates[0]))
    return CheckResult("FAIL", "WhisperX alignment weights", f"not found in {checkpoint_dir}")


def collect_checks(
    profile: str, model: str, server_url: str | None = None
) -> list[CheckResult]:
    resolved = resolve_profile(profile)
    results = [
        CheckResult("OK", "profile", resolved),
        CheckResult(
            "OK",
            "platform",
            f"{platform.system()} {platform.machine()}" + (" (WSL)" if is_wsl() else ""),
        ),
        CheckResult(
            "OK" if sys.version_info >= (3, 9) else "FAIL",
            "Python",
            platform.python_version(),
        ),
    ]
    for command in ("git", "uv", "node", "npm", "ffmpeg", "ffprobe"):
        results.append(_command(command))
    results.append(_module("PyPDF2"))

    media_modules = (
        ("pydub", None),
        ("moviepy", None),
        ("PIL", "Pillow"),
        ("fitz", "PyMuPDF"),
        ("fastapi", None),
        ("sqlalchemy", None),
    )
    for import_name, label in media_modules:
        results.append(_module(import_name, label))
    results.append(_frontend())

    if resolved == "local-gpu":
        if platform.system() != "Linux":
            results.append(
                CheckResult("FAIL", "local GPU platform", "requires Linux or NVIDIA-enabled WSL2")
            )
        results.append(_command("nvidia-smi"))
        for command in ("gcc", "g++", "make"):
            results.append(_command(command))
        results.extend(_cuda())
        results.append(_module("qwen_tts", "Qwen3-TTS"))
        results.append(_module("whisperx", "WhisperX"))
        results.append(_huggingface_repo(QWEN_MODELS[model], f"Qwen {model} weights"))
        results.append(
            _huggingface_repo("Systran/faster-whisper-base", "WhisperX base weights")
        )
        results.append(_whisper_alignment())
        results.extend(_latentsync())
    elif resolved == "remote-client":
        if server_url:
            results.append(_remote_server(server_url))
        else:
            results.append(
                CheckResult(
                    "WARN", "remote GPU server", "not checked; pass --server-url to verify it"
                )
            )
    return results


def run_doctor(
    profile: str = "auto",
    model: str = "0.6B",
    server_url: str | None = None,
    *,
    emit: Callable[[str], None] = print,
) -> int:
    results = collect_checks(profile, model, server_url)
    for result in results:
        emit(f"[{result.level}] {result.name}: {result.detail}")
    failures = sum(result.level == "FAIL" for result in results)
    emit(f"\nDoctor completed with {failures} failure(s).")
    return 1 if failures else 0
