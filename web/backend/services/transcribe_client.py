"""Thin HTTP client for the GPU inference server's /transcribe endpoint."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)


def transcribe_upload(
    server_url: str,
    audio_path: str,
    *,
    language: str = "en-US",
    timeout: float = 300.0,
) -> Optional[str]:
    """Post *audio_path* to ``{server_url}/transcribe`` and return the text.

    Returns ``None`` on any failure (server unreachable, non-JSON reply,
    empty transcript). Callers should treat the transcript as best-effort
    metadata — upload must still succeed when transcription fails.
    """
    url = f"{server_url.rstrip('/')}/transcribe"
    boundary = "----ScreencastgenTranscribeBoundary"

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
    except OSError as exc:
        logger.warning("Cannot read audio for transcription: %s", exc)
        return None

    filename = os.path.basename(audio_path)
    parts: list[bytes] = []
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="language"\r\n\r\n'
            f"{language}\r\n"
        ).encode("utf-8")
    )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(audio_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(parts)
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        logger.warning("Transcription server unreachable at %s: %s", url, exc)
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Transcription server returned invalid JSON: %s", exc)
        return None

    text = (payload.get("text") or "").strip()
    return text or None
