"""Lip-sync video generation facade."""

from __future__ import annotations

import os
import subprocess
import tempfile

from .providers.tts.base import resolve_device
from .providers.lipsync import (
    DEFAULT_LIPSYNC_PROVIDER,
    get_default_lipsync_provider,
    get_lipsync_provider_names,
    run_lipsync_provider,
)


def _resolve_device(device: str = "auto") -> str:
    """Backward-compatible alias for device resolution."""
    return resolve_device(device)


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _loop_video_to_duration(video_path: str, duration: float, output_path: str) -> str:
    """Loop a video to match the desired duration using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", video_path, "-t", str(duration), "-c", "copy", output_path],
        capture_output=True,
        check=True,
    )
    return output_path


def generate_lipsync_video(
    audio_path: str,
    reference_video_path: str,
    output_path: str,
    provider: str = DEFAULT_LIPSYNC_PROVIDER,
    device: str = "auto",
    latentsync_preset: str = "quality",
) -> str:
    """Generate a lip-synced video from audio and a reference face video."""
    if provider not in get_lipsync_provider_names():
        raise ValueError(
            f"Unknown lip-sync provider {provider!r}. "
            f"Choose from: {', '.join(get_lipsync_provider_names())}"
        )

    device = _resolve_device(device)

    if device == "cpu":
        print("  WARNING: Lip-sync generation requires a GPU for reasonable speed.")
        print("  Consider using the 'highlight' subcommand instead for CPU-only systems.")

    audio_duration = _get_audio_duration(audio_path)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        looped_video = tmp.name

    try:
        _loop_video_to_duration(reference_video_path, audio_duration, looped_video)
        _run_provider(
            provider,
            looped_video,
            audio_path,
            output_path,
            device,
            latentsync_preset=latentsync_preset,
        )
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
    *,
    latentsync_preset: str,
):
    """Run the selected lip-sync provider."""
    if provider == DEFAULT_LIPSYNC_PROVIDER:
        try:
            _run_latentsync(
                video_path,
                audio_path,
                output_path,
                device,
                preset=latentsync_preset,
            )
            return
        except ImportError:
            try:
                _run_wav2lip(video_path, audio_path, output_path)
                return
            except ImportError as exc:
                raise ImportError(
                    "No lip-sync backend found. Install LatentSync:\n"
                    "  scripts/install_latentsync.sh\n"
                    "Or set LATENTSYNC_ROOT and LATENTSYNC_PYTHON for an existing install."
                ) from exc

    if provider == "latentsync":
        _run_latentsync(
            video_path,
            audio_path,
            output_path,
            device,
            preset=latentsync_preset,
        )
        return

    if provider == "wav2lip":
        _run_wav2lip(video_path, audio_path, output_path)
        return

    raise ValueError(
        f"Unknown lip-sync provider {provider!r}. "
        f"Choose from: {', '.join(get_lipsync_provider_names())}"
    )


def _run_latentsync(
    video_path: str,
    audio_path: str,
    output_path: str,
    device: str,
    *,
    preset: str = "quality",
):
    """Compatibility wrapper for the LatentSync provider."""
    return run_lipsync_provider(
        "latentsync",
        video_path,
        audio_path,
        output_path,
        device=device,
        preset=preset,
    )


def _run_wav2lip(video_path: str, audio_path: str, output_path: str):
    """Compatibility wrapper for the Wav2Lip provider."""
    return run_lipsync_provider("wav2lip", video_path, audio_path, output_path, device="cpu")
