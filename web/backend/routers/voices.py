"""Reference voice library, language list, and sample-preview endpoints."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..config import settings
from ..database import async_session_factory
from ..models import UploadedFile
from ..services.languages import SUPPORTED_LANGUAGES
from ..services.storage import get_upload_abs_path
from ..services.voices import get_voice, load_voices

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voices"])

# A short, language-neutral preview line. The frontend can override this.
DEFAULT_PREVIEW_TEXT = (
    "This is a short preview of the selected voice. "
    "If you like how it sounds, use it for the whole document."
)


# ---------------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------------

class VoiceResponse(BaseModel):
    id: str
    name: str
    language: str
    description: str
    ref_text: str
    available: bool


@router.get("/voices", response_model=list[VoiceResponse])
async def list_voices():
    return [
        VoiceResponse(
            id=v.id,
            name=v.name,
            language=v.language,
            description=v.description,
            ref_text=v.ref_text,
            available=v.exists,
        )
        for v in load_voices()
    ]


@router.get("/voices/{voice_id}/audio")
async def voice_audio(voice_id: str):
    voice = get_voice(voice_id)
    if not voice:
        raise HTTPException(404, "Voice not found")
    if not voice.exists:
        raise HTTPException(
            404,
            f"Voice '{voice_id}' has no backing audio file at {voice.file}",
        )
    return FileResponse(voice.abs_path, media_type="audio/wav", filename=voice.file)


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------

class LanguageResponse(BaseModel):
    code: str
    name: str


@router.get("/languages", response_model=list[LanguageResponse])
async def list_languages():
    return [LanguageResponse(**lang) for lang in SUPPORTED_LANGUAGES]


# ---------------------------------------------------------------------------
# Sample preview
# ---------------------------------------------------------------------------

class PreviewRequest(BaseModel):
    text: Optional[str] = None
    language: str = "en-US"
    voice_id: Optional[str] = None
    ref_audio_file_id: Optional[UUID] = None
    ref_text: Optional[str] = None
    # When set, the preview text is drawn from the user's uploaded
    # document instead of the generic DEFAULT_PREVIEW_TEXT — gives a
    # more representative sample of how the chosen voice will read
    # the actual content.
    uploaded_file_id: Optional[UUID] = None
    model_config = {"extra": "forbid"}


PREVIEW_MIN_CHARS = 200
PREVIEW_MAX_CHARS = 400


def _snippet_from_document(text: str) -> Optional[str]:
    """Return a ~200-char preview snippet, extending to a sentence end."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return None
    if len(cleaned) <= PREVIEW_MIN_CHARS:
        return cleaned

    end = PREVIEW_MIN_CHARS
    for i in range(PREVIEW_MIN_CHARS, min(len(cleaned), PREVIEW_MAX_CHARS)):
        if cleaned[i] in ".!?":
            end = i + 1
            break
    else:
        end = min(len(cleaned), PREVIEW_MAX_CHARS)
    return cleaned[:end].strip()


async def _resolve_ref_audio(req: PreviewRequest) -> tuple[Optional[str], Optional[str]]:
    """Return (ref_audio_path, ref_text) for the request, if any."""
    if req.voice_id:
        voice = get_voice(req.voice_id)
        if not voice:
            raise HTTPException(404, f"Voice '{req.voice_id}' not found")
        if not voice.exists:
            raise HTTPException(404, f"Voice '{req.voice_id}' has no audio file")
        return voice.abs_path, req.ref_text or voice.ref_text

    if req.ref_audio_file_id:
        async with async_session_factory() as session:
            uploaded = await session.get(UploadedFile, req.ref_audio_file_id)
            if not uploaded:
                raise HTTPException(404, "Uploaded reference audio not found")
        return get_upload_abs_path(uploaded.stored_path), req.ref_text or uploaded.ref_text

    return None, req.ref_text


def _post_synthesize(
    server_url: str,
    text: str,
    language: str,
    ref_audio_path: Optional[str],
    ref_text: Optional[str],
) -> bytes:
    """Call the GPU inference server's /synthesize endpoint.

    Uses multipart/form-data when a reference audio is supplied, JSON
    otherwise. Multipart support requires the inference server's
    /synthesize endpoint to accept the optional `ref_audio` file (see
    ``screencastgen/inference_server.py``).
    """
    url = f"{server_url.rstrip('/')}/synthesize"

    if ref_audio_path:
        boundary = "----ScreencastgenPreviewBoundary"
        body_parts: list[bytes] = []

        def add_field(name: str, value: str) -> None:
            body_parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")
            )

        add_field("text", text)
        add_field("language", language)
        if ref_text:
            add_field("ref_text", ref_text)

        with open(ref_audio_path, "rb") as f:
            audio_bytes = f.read()
        filename = os.path.basename(ref_audio_path)
        body_parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="ref_audio"; filename="{filename}"\r\n'
                f"Content-Type: audio/wav\r\n\r\n"
            ).encode("utf-8")
        )
        body_parts.append(audio_bytes)
        body_parts.append(b"\r\n")
        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))

        body = b"".join(body_parts)
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
    else:
        payload = json.dumps({"text": text, "language": language}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


@router.post("/voices/preview")
async def voice_preview(req: PreviewRequest):
    """Generate a short audio sample using the chosen voice + language.

    Returns the raw audio bytes (audio/wav). Intended for the New Job
    page so users can listen before committing to a full document.
    """
    ref_audio_path, ref_text = await _resolve_ref_audio(req)

    text = (req.text or "").strip()
    if not text and req.uploaded_file_id:
        async with async_session_factory() as session:
            uploaded = await session.get(UploadedFile, req.uploaded_file_id)
        if uploaded:
            try:
                from screencastgen.extractor import extract_text

                doc_text = extract_text(get_upload_abs_path(uploaded.stored_path))
                snippet = _snippet_from_document(doc_text)
                if snippet:
                    text = snippet
            except Exception:  # noqa: BLE001
                logger.exception("Could not extract preview snippet from document")

    if not text:
        text = DEFAULT_PREVIEW_TEXT

    server_url = settings.TTS_SERVER_URL
    try:
        audio_bytes = _post_synthesize(
            server_url=server_url,
            text=text,
            language=req.language,
            ref_audio_path=ref_audio_path,
            ref_text=ref_text,
        )
    except urllib.error.URLError as exc:
        logger.exception("Sample preview failed")
        raise HTTPException(
            502,
            f"TTS server unreachable at {server_url}: {exc.reason}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Sample preview failed")
        raise HTTPException(500, f"Sample preview failed: {exc}") from exc

    if not audio_bytes:
        raise HTTPException(502, "TTS server returned empty audio")

    return Response(content=audio_bytes, media_type="audio/wav")
