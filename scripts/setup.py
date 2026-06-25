#!/usr/bin/env python3
"""Cross-platform development and runtime bootstrap for screencastgen."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
FRONTEND = ROOT / "web" / "frontend"


def is_wsl() -> bool:
    if platform.system() != "Linux":
        return False
    text = " ".join((platform.release(), platform.version())).lower()
    return "microsoft" in text or "wsl" in text


def has_nvidia() -> bool:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return False
    return subprocess.run(
        [executable, "-L"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0


def resolve_profile(requested: str) -> str:
    if requested != "auto":
        return requested
    if platform.system() == "Linux" and has_nvidia():
        return "local-gpu"
    return "remote-client"


def install_hint(missing: list[str]) -> str:
    system = platform.system()
    if system == "Darwin":
        packages = []
        for name in missing:
            package = {"node": "node", "npm": "node", "ffprobe": "ffmpeg"}.get(name, name)
            if package not in packages and package not in {
                "gcc",
                "g++",
                "make",
                "nvidia-smi",
            }:
                packages.append(package)
        if "uv" in missing and "uv" not in packages:
            packages.append("uv")
        return (
            "Install missing tools with Homebrew where available:\n"
            f"  brew install {' '.join(packages)}"
        )
    if system == "Windows":
        return (
            "Install the missing tools with winget, then open a new terminal:\n"
            "  winget install --id Git.Git -e\n"
            "  winget install --id astral-sh.uv -e\n"
            "  winget install --id OpenJS.NodeJS.LTS -e\n"
            "  winget install --id Gyan.FFmpeg -e"
        )
    distro = ""
    try:
        distro = Path("/etc/os-release").read_text(encoding="utf-8").lower()
    except OSError:
        pass
    if "fedora" in distro or "rhel" in distro:
        return "\n".join(
            [
                "Install the missing tools with dnf:",
                "  sudo dnf install git nodejs npm ffmpeg gcc-c++ make",
                "  curl -LsSf https://astral.sh/uv/install.sh | sh",
                "  exec \"$SHELL\"",
                "Install the NVIDIA driver separately when nvidia-smi is missing.",
            ]
        )
    return (
        "Install the missing tools on Debian/Ubuntu with:\n"
        "  sudo apt-get update\n"
        "  sudo apt-get install -y curl ca-certificates git nodejs npm ffmpeg build-essential\n"
        "  curl -LsSf https://astral.sh/uv/install.sh | sh\n"
        "  exec \"$SHELL\"\n"
        "build-essential provides gcc, g++, and make. Install the NVIDIA driver "
        "separately when nvidia-smi is missing."
    )


def preflight(profile: str) -> bool:
    commands = ["git", "uv", "node", "npm", "ffmpeg", "ffprobe"]
    if profile == "local-gpu":
        commands.extend(["gcc", "g++", "make", "nvidia-smi", "bash"])
    missing = [name for name in commands if shutil.which(name) is None]

    print(f"Platform: {platform.system()} {platform.machine()}")
    if is_wsl():
        print("Environment: WSL")
    print(f"Setup profile: {profile}")

    if profile == "local-gpu" and platform.system() != "Linux":
        print("ERROR: local-gpu is supported on Linux and NVIDIA-enabled WSL2.")
        print("Use --profile remote-client, or use WSL2 on Windows.")
        return False
    if missing:
        print(f"ERROR: missing required commands: {', '.join(missing)}")
        print(install_hint(missing))
        if "uv" in missing:
            print("uv installation: https://docs.astral.sh/uv/getting-started/installation/")
        return False
    if profile == "local-gpu" and not has_nvidia():
        print("ERROR: nvidia-smi cannot access an NVIDIA GPU.")
        if is_wsl():
            print(
                "Install a WSL-compatible NVIDIA Windows driver and enable GPU access in WSL2."
            )
        else:
            print("Install a compatible NVIDIA driver, or use --profile remote-client.")
        return False
    print("Prerequisite checks passed.")
    return True


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print(f"\n> {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def install(profile: str, model: str, server_url: str | None) -> None:
    run(["uv", "venv", "--python", "3.10", str(VENV)])
    python = str(venv_python())
    extras = "all,dev" if profile == "local-gpu" else "client,web,dev"
    run(["uv", "pip", "install", "--python", python, "-e", f".[{extras}]"])

    if (FRONTEND / "package-lock.json").exists():
        run(["npm", "ci"], cwd=FRONTEND)
    else:
        run(["npm", "install", "--no-package-lock"], cwd=FRONTEND)

    if profile == "local-gpu":
        run(["bash", str(ROOT / "scripts" / "install_latentsync.sh")])
        run(
            [
                python,
                "-m",
                "screencastgen",
                "download-models",
                "--backend",
                "qwen",
                "--model",
                model,
                "--package",
                "whisperx",
            ]
        )

    doctor = [
        python,
        "-m",
        "screencastgen",
        "doctor",
        "--profile",
        profile,
        "--model",
        model,
    ]
    if server_url:
        doctor.extend(["--server-url", server_url])
    run(doctor)
    run(["npm", "run", "build"], cwd=FRONTEND)

    activate = VENV / ("Scripts/activate" if os.name == "nt" else "bin/activate")
    print("\nSetup complete.")
    print(f"Activate the environment: {activate}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("auto", "local-gpu", "remote-client", "dev"),
        default="auto",
        help="Installation profile (default: auto)",
    )
    parser.add_argument(
        "--model", choices=("0.6B", "1.7B"), default="0.6B", help="Qwen model for local-gpu"
    )
    parser.add_argument("--server-url", help="Remote GPU URL to verify after installation")
    parser.add_argument("--check", action="store_true", help="Only check prerequisites")
    args = parser.parse_args(argv)

    profile = resolve_profile(args.profile)
    if not preflight(profile):
        return 1
    if args.check:
        return 0
    try:
        install(profile, args.model, args.server_url)
    except subprocess.CalledProcessError as exc:
        print(f"\nERROR: setup command failed with exit code {exc.returncode}.", file=sys.stderr)
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
