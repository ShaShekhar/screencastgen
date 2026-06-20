"""Client helpers for calling the GPU inference server remotely.

Used by the CPU VM pipeline when ``--backend remote`` to offload
alignment and lip-sync generation to the GPU VM.
"""

import json
import os
import time
import uuid
from typing import Callable, List, Optional

from .types import WordTiming


class LipsyncCancelled(Exception):
    """Raised when a remote lip-sync request is cancelled before completion."""


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


def _encode_multipart(fields: dict, files: list) -> tuple:
    """Encode form fields and file parts as multipart/form-data.

    ``files`` is a list of ``(name, filename, content_bytes, content_type)``.
    Returns ``(body_bytes, boundary)``.
    """
    boundary = "----ScreencastgenBoundary" + uuid.uuid4().hex
    body = b""
    for name, value in fields.items():
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode("utf-8")
    for name, filename, content, ctype in files:
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8")
        body += content + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")
    return body, boundary


def _get_json(url: str, timeout: int) -> dict:
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def _request_no_body(url: str, method: str, timeout: int) -> None:
    import urllib.request

    req = urllib.request.Request(url, data=b"" if method == "POST" else None, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


def remote_generate_lipsync(
    audio_path: str,
    reference_video_path: str,
    output_path: str,
    *,
    server_url: str = "http://localhost:8100",
    provider: str = "auto",
    latentsync_preset: str = "quality",
    poll_interval: float = 5.0,
    request_timeout: int = 120,
    should_cancel: Optional[Callable[[], bool]] = None,
    on_status: Optional[Callable[[float], None]] = None,
) -> str:
    """Generate a lip-synced video on the GPU server.

    The request is submitted as a background job and then polled, so an
    arbitrarily slow GPU never trips a socket timeout. ``should_cancel`` is
    polled between status checks; when it returns True the remote job is
    cancelled and :class:`LipsyncCancelled` is raised. ``on_status`` receives
    the elapsed generation time (seconds) on each poll.

    Falls back to the legacy synchronous protocol if the server replies with
    the video inline rather than a JSON job handle.
    """
    import urllib.request

    base = server_url.rstrip("/")

    with open(audio_path, "rb") as f:
        audio_data = f.read()
    with open(reference_video_path, "rb") as f:
        video_data = f.read()

    body, boundary = _encode_multipart(
        {"provider": provider, "latentsync_preset": latentsync_preset},
        [
            ("audio", os.path.basename(audio_path), audio_data, "application/octet-stream"),
            ("reference_video", os.path.basename(reference_video_path), video_data, "video/mp4"),
        ],
    )
    req = urllib.request.Request(
        f"{base}/lipsync",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=request_timeout) as resp:
            content_type = resp.headers.get_content_type()
            payload = resp.read()
    except Exception as exc:
        raise RuntimeError(f"Remote lip-sync submit failed ({base}/lipsync): {exc}") from exc

    # Legacy servers return the MP4 inline; newer ones return a JSON job handle.
    if content_type != "application/json":
        if not payload:
            raise RuntimeError("GPU server returned empty video")
        with open(output_path, "wb") as f:
            f.write(payload)
        return output_path

    job = json.loads(payload)
    lipsync_id = job.get("lipsync_id")
    if not lipsync_id:
        raise RuntimeError(f"GPU server did not return a lip-sync job id: {job}")

    poll_failures = 0
    try:
        while True:
            if should_cancel and should_cancel():
                try:
                    _request_no_body(
                        f"{base}/lipsync/{lipsync_id}/cancel", "POST", request_timeout
                    )
                except Exception:  # noqa: BLE001 — cancel is best-effort
                    pass
                raise LipsyncCancelled()

            time.sleep(poll_interval)

            try:
                status = _get_json(f"{base}/lipsync/{lipsync_id}", request_timeout)
                poll_failures = 0
            except Exception as exc:  # noqa: BLE001 — tolerate transient blips
                poll_failures += 1
                if poll_failures >= 5:
                    raise RuntimeError(
                        f"Lost contact with GPU server while polling lip-sync: {exc}"
                    ) from exc
                continue

            if on_status is not None:
                try:
                    on_status(float(status.get("elapsed") or 0.0))
                except Exception:  # noqa: BLE001
                    pass

            state = status.get("status")
            if state == "done":
                break
            if state in ("failed", "cancelled"):
                raise RuntimeError(
                    status.get("error") or f"Remote lip-sync {state}"
                )

        try:
            with urllib.request.urlopen(
                f"{base}/lipsync/{lipsync_id}/result", timeout=request_timeout
            ) as resp:
                video_bytes = resp.read()
        except Exception as exc:
            raise RuntimeError(f"Remote lip-sync result download failed: {exc}") from exc

        if not video_bytes:
            raise RuntimeError("GPU server returned empty video")
        with open(output_path, "wb") as f:
            f.write(video_bytes)
    finally:
        try:
            _request_no_body(f"{base}/lipsync/{lipsync_id}", "DELETE", request_timeout)
        except Exception:  # noqa: BLE001 — server-side cleanup is best-effort
            pass

    return output_path
