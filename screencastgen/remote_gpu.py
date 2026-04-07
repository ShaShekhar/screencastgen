"""Client helpers for calling the GPU inference server remotely.

Used by the CPU VM pipeline when ``--backend remote`` to offload
alignment and lip-sync generation to the GPU VM.
"""

import json
import os
from typing import List
from urllib.parse import urljoin

from .types import WordTiming


def remote_align_chunk(
    audio_path: str,
    text: str,
    *,
    server_url: str = "http://localhost:8100",
    language: str = "en-US",
    provider: str = "whisperx",
    timeout: int = 300,
) -> List[WordTiming]:
    """Send audio + text to the GPU server for alignment."""
    import urllib.request

    url = f"{server_url.rstrip('/')}/align"

    # Build multipart/form-data manually (no requests dependency)
    boundary = "----ScreencastgenBoundary9876543210"
    body_parts = []

    # Audio file part
    with open(audio_path, "rb") as f:
        audio_data = f.read()
    filename = os.path.basename(audio_path)
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    )
    body_parts.append(audio_data)
    body_parts.append(b"\r\n")

    # Text field
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="text"\r\n\r\n'
        f"{text}\r\n"
    )

    # Language field
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="language"\r\n\r\n'
        f"{language}\r\n"
    )

    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="provider"\r\n\r\n'
        f"{provider}\r\n"
    )

    body_parts.append(f"--{boundary}--\r\n")

    # Encode body
    body = b""
    for part in body_parts:
        if isinstance(part, str):
            body += part.encode("utf-8")
        else:
            body += part

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        raise RuntimeError(f"Remote alignment failed ({url}): {exc}") from exc

    return [
        WordTiming(word=w["word"], start=w["start"], end=w["end"])
        for w in data.get("words", [])
    ]


def remote_generate_lipsync(
    audio_path: str,
    reference_video_path: str,
    output_path: str,
    *,
    server_url: str = "http://localhost:8100",
    provider: str = "auto",
    timeout: int = 600,
) -> str:
    """Send audio + reference video to the GPU server for lip-sync generation."""
    import urllib.request

    url = f"{server_url.rstrip('/')}/lipsync"

    boundary = "----ScreencastgenBoundary1234567890"
    body_parts = []

    # Audio file part
    with open(audio_path, "rb") as f:
        audio_data = f.read()
    audio_filename = os.path.basename(audio_path)
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="{audio_filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    )
    body_parts.append(audio_data)
    body_parts.append(b"\r\n")

    # Reference video file part
    with open(reference_video_path, "rb") as f:
        video_data = f.read()
    video_filename = os.path.basename(reference_video_path)
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="reference_video"; filename="{video_filename}"\r\n'
        f"Content-Type: video/mp4\r\n\r\n"
    )
    body_parts.append(video_data)
    body_parts.append(b"\r\n")

    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="provider"\r\n\r\n'
        f"{provider}\r\n"
    )

    body_parts.append(f"--{boundary}--\r\n")

    # Encode body
    body = b""
    for part in body_parts:
        if isinstance(part, str):
            body += part.encode("utf-8")
        else:
            body += part

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            video_bytes = resp.read()
    except Exception as exc:
        raise RuntimeError(f"Remote lip-sync failed ({url}): {exc}") from exc

    if not video_bytes:
        raise RuntimeError("GPU server returned empty video")

    with open(output_path, "wb") as f:
        f.write(video_bytes)

    return output_path
