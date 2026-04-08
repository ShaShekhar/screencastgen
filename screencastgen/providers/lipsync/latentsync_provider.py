"""LatentSync lip-sync provider."""

from __future__ import annotations

import os
import subprocess
import sys


def find_latentsync_root() -> str:
    """Locate the LatentSync repo directory."""
    env = os.environ.get("LATENTSYNC_ROOT")
    if env and os.path.isdir(env):
        return env

    try:
        import latentsync

        pkg_dir = os.path.dirname(os.path.abspath(latentsync.__file__))
        return os.path.dirname(pkg_dir)
    except ImportError as exc:
        raise ImportError(
            "LatentSync not found. Install it with:\n"
            "  git clone https://github.com/bytedance/LatentSync.git\n"
            "  cd LatentSync && pip install -e .\n"
            "Or set LATENTSYNC_ROOT=/path/to/LatentSync"
        ) from exc


def run_latentsync(video_path: str, audio_path: str, output_path: str, device: str):
    """Run LatentSync lip-sync generation as a subprocess."""
    root = find_latentsync_root()

    config_path = os.path.join(root, "configs", "unet", "stage2_512.yaml")
    ckpt_path = os.path.join(root, "checkpoints", "latentsync_unet.pt")

    if not os.path.isfile(config_path):
        raise FileNotFoundError(
            f"LatentSync config not found at {config_path}\n"
            f"Ensure LATENTSYNC_ROOT is set correctly or reinstall LatentSync."
        )
    if not os.path.isfile(ckpt_path):
        raise FileNotFoundError(
            f"LatentSync checkpoint not found at {ckpt_path}\n"
            f"Download it per the LatentSync README:\n"
            f"  https://github.com/bytedance/LatentSync#download-checkpoints"
        )

    cmd = [
        sys.executable,
        "-m",
        "scripts.inference",
        "--unet_config_path",
        config_path,
        "--inference_ckpt_path",
        ckpt_path,
        "--video_path",
        video_path,
        "--audio_path",
        audio_path,
        "--video_out_path",
        output_path,
        "--inference_steps",
        "20",
        "--guidance_scale",
        "1.5",
        "--seed",
        "1247",
        "--temp_dir",
        os.path.join(root, "temp"),
        "--enable_deepcache",
    ]

    result = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"LatentSync inference failed (exit code {result.returncode}):\n"
            f"{result.stderr}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(f"LatentSync completed but output file not found at {output_path}")
