"""Lip-sync video generation using LatentSync.

Imports are deferred so the module can be imported without heavy ML deps.
"""

import os
import subprocess
import tempfile


def _resolve_device(device: str = "auto") -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


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
    device: str = "auto",
) -> str:
    """Generate a lip-synced video from audio and a reference face video.

    Uses LatentSync (ByteDance) for diffusion-based lip-sync generation.
    Falls back to a simpler approach if LatentSync is not installed.

    Args:
        audio_path: Path to the audio file to lip-sync.
        reference_video_path: Path to the reference face video (~10 seconds).
        output_path: Path for the output lip-synced video.
        device: Device to use (auto, cpu, cuda).

    Returns:
        Path to the generated video.
    """
    device = _resolve_device(device)

    if device == "cpu":
        print("  WARNING: Lip-sync generation requires a GPU for reasonable speed.")
        print("  Consider using the 'highlight' subcommand instead for CPU-only systems.")

    audio_duration = _get_audio_duration(audio_path)

    # Loop reference video if needed
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        looped_video = tmp.name

    try:
        _loop_video_to_duration(reference_video_path, audio_duration, looped_video)

        # Try LatentSync first
        try:
            _run_latentsync(looped_video, audio_path, output_path, device)
        except ImportError:
            # Fallback: try Wav2Lip
            try:
                _run_wav2lip(looped_video, audio_path, output_path)
            except ImportError:
                raise ImportError(
                    "No lip-sync backend found. Install LatentSync or Wav2Lip:\n"
                    "  pip install latentsync   (recommended)\n"
                    "  pip install wav2lip\n"
                    "Or see: https://github.com/bytedance/LatentSync"
                )
    finally:
        if os.path.exists(looped_video):
            os.unlink(looped_video)

    return output_path


def _run_latentsync(video_path: str, audio_path: str, output_path: str, device: str):
    """Run LatentSync lip-sync generation."""
    from latentsync.inference import inference as latentsync_infer

    latentsync_infer(
        video_path=video_path,
        audio_path=audio_path,
        output_path=output_path,
        device=device,
    )


def _run_wav2lip(video_path: str, audio_path: str, output_path: str):
    """Fallback: run Wav2Lip lip-sync generation."""
    from wav2lip import inference as wav2lip_infer

    wav2lip_infer.run(
        face=video_path,
        audio=audio_path,
        outfile=output_path,
    )
