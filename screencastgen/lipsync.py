"""Lip-sync video generation with provider dispatch."""

import os
import subprocess
import tempfile

from .backends.base import resolve_device

DEFAULT_LIPSYNC_PROVIDER = "auto"
_LIPSYNC_PROVIDER_NAMES = ["auto", "latentsync", "wav2lip"]


def get_lipsync_provider_names():
    """Return registered lip-sync provider names."""
    return list(_LIPSYNC_PROVIDER_NAMES)


def get_default_lipsync_provider() -> str:
    """Return the default lip-sync provider."""
    return DEFAULT_LIPSYNC_PROVIDER


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_path],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def _loop_video_to_duration(video_path: str, duration: float, output_path: str) -> str:
    """Loop a video to match the desired duration using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", video_path,
         "-t", str(duration), "-c", "copy", output_path],
        capture_output=True, check=True,
    )
    return output_path


def generate_lipsync_video(
    audio_path: str,
    reference_video_path: str,
    output_path: str,
    provider: str = DEFAULT_LIPSYNC_PROVIDER,
    device: str = "auto",
) -> str:
    """Generate a lip-synced video from audio and a reference face video."""
    if provider not in _LIPSYNC_PROVIDER_NAMES:
        raise ValueError(
            f"Unknown lip-sync provider {provider!r}. "
            f"Choose from: {', '.join(get_lipsync_provider_names())}"
        )

    device = resolve_device(device)

    if device == "cpu":
        print("  WARNING: Lip-sync generation requires a GPU for reasonable speed.")
        print("  Consider using the 'highlight' subcommand instead for CPU-only systems.")

    audio_duration = _get_audio_duration(audio_path)

    # Loop reference video if needed
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        looped_video = tmp.name

    try:
        _loop_video_to_duration(reference_video_path, audio_duration, looped_video)
        _run_provider(provider, looped_video, audio_path, output_path, device)
    finally:
        if os.path.exists(looped_video):
            os.unlink(looped_video)

    return output_path


def _run_provider(
    provider: str,
    video_path: str,
    audio_path: str,
    output_path: str,
    device: str,
):
    """Run the selected lip-sync provider."""
    if provider == "auto":
        try:
            _run_latentsync(video_path, audio_path, output_path, device)
            return
        except ImportError:
            try:
                _run_wav2lip(video_path, audio_path, output_path)
                return
            except ImportError:
                raise ImportError(
                    "No lip-sync provider found. Install LatentSync:\n"
                    "  git clone https://github.com/bytedance/LatentSync.git\n"
                    "  cd LatentSync && pip install -e .\n"
                    "Then download the checkpoint per the LatentSync README."
                )

    if provider == "latentsync":
        _run_latentsync(video_path, audio_path, output_path, device)
        return

    if provider == "wav2lip":
        _run_wav2lip(video_path, audio_path, output_path)
        return

    raise ValueError(
        f"Unknown lip-sync provider {provider!r}. "
        f"Choose from: {', '.join(get_lipsync_provider_names())}"
    )


def _find_latentsync_root() -> str:
    """Locate the LatentSync repo directory.

    Checks (in order):
    1. LATENTSYNC_ROOT environment variable
    2. The directory containing the installed ``latentsync`` package
    """
    env = os.environ.get("LATENTSYNC_ROOT")
    if env and os.path.isdir(env):
        return env

    try:
        import latentsync
        pkg_dir = os.path.dirname(os.path.abspath(latentsync.__file__))
        # The repo root is one level up from the latentsync package
        return os.path.dirname(pkg_dir)
    except ImportError:
        raise ImportError(
            "LatentSync not found. Install it with:\n"
            "  git clone https://github.com/bytedance/LatentSync.git\n"
            "  cd LatentSync && pip install -e .\n"
            "Or set LATENTSYNC_ROOT=/path/to/LatentSync"
        )


def _run_latentsync(video_path: str, audio_path: str, output_path: str, device: str):
    """Run LatentSync lip-sync generation as a subprocess.

    Invokes LatentSync via ``python -m scripts.inference`` from the repo
    root, avoiding sys.path manipulation and import conflicts.
    See: https://github.com/bytedance/LatentSync
    """
    import sys

    root = _find_latentsync_root()

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
        sys.executable, "-m", "scripts.inference",
        "--unet_config_path", config_path,
        "--inference_ckpt_path", ckpt_path,
        "--video_path", video_path,
        "--audio_path", audio_path,
        "--video_out_path", output_path,
        "--inference_steps", "20",
        "--guidance_scale", "1.5",
        "--seed", "1247",
        "--temp_dir", os.path.join(root, "temp"),
        "--enable_deepcache",
    ]

    result = subprocess.run(
        cmd, cwd=root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"LatentSync inference failed (exit code {result.returncode}):\n"
            f"{result.stderr}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(
            f"LatentSync completed but output file not found at {output_path}"
        )


def _run_wav2lip(video_path: str, audio_path: str, output_path: str):
    """Fallback: run Wav2Lip lip-sync generation."""
    from wav2lip import inference as wav2lip_infer

    wav2lip_infer.run(
        face=video_path,
        audio=audio_path,
        outfile=output_path,
    )
