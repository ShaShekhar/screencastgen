"""Lip-sync helper endpoints."""

from __future__ import annotations

import io
import os
import subprocess
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from PIL import Image

from screencastgen.constants import DEFAULT_BG_COLOR, DEFAULT_HIGHLIGHT_COLOR, DEFAULT_TEXT_COLOR
from screencastgen.extractor import extract_text, render_page_image_with_zoom
from screencastgen.highlight_renderer import HighlightRenderer

from ..database import async_session_factory
from ..models import UploadedFile
from ..services.storage import get_upload_abs_path

router = APIRouter(tags=["lipsync"])

OVERLAY_POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right"}
FACE_POSITIONS = OVERLAY_POSITIONS | {"left", "right", "center"}


@router.get("/lipsync/preview-frame")
async def preview_lipsync_frame(
    uploaded_file_id: UUID,
    ref_video_file_id: UUID,
    face_position: str = Query("bottom-right"),
    face_scale: float = Query(0.22, ge=0.1, le=0.9),
    width: int = Query(1280, ge=320, le=3840),
    height: int = Query(720, ge=240, le=2160),
    font_size: int = Query(32, ge=12, le=72),
):
    if face_position not in FACE_POSITIONS:
        raise HTTPException(400, "Invalid face_position")

    document, reference_video = await _get_uploads(uploaded_file_id, ref_video_file_id)
    document_path = _local_upload_path(document)
    reference_video_path = _local_upload_path(reference_video)

    try:
        frame = _compose_preview_frame(
            document_path=document_path,
            reference_video_path=reference_video_path,
            face_position=face_position,
            face_scale=face_scale,
            width=width,
            height=height,
            font_size=font_size,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not render preview frame: {exc}") from exc

    buf = io.BytesIO()
    frame.save(buf, format="PNG")
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


async def _get_uploads(
    uploaded_file_id: UUID,
    ref_video_file_id: UUID,
) -> tuple[UploadedFile, UploadedFile]:
    async with async_session_factory() as session:
        document = await session.get(UploadedFile, uploaded_file_id)
        reference_video = await session.get(UploadedFile, ref_video_file_id)

    if not document:
        raise HTTPException(404, "Uploaded document not found")
    if not reference_video:
        raise HTTPException(404, "Reference video not found")
    return document, reference_video


def _local_upload_path(uploaded: UploadedFile) -> str:
    path = get_upload_abs_path(uploaded.stored_path)
    if not os.path.isfile(path):
        raise HTTPException(404, f"Uploaded file not found on disk: {uploaded.original_name}")
    return path


def _compose_preview_frame(
    *,
    document_path: str,
    reference_video_path: str,
    face_position: str,
    face_scale: float,
    width: int,
    height: int,
    font_size: int,
) -> Image.Image:
    canvas = Image.new("RGB", (width, height), DEFAULT_BG_COLOR)
    face_img = _load_video_frame(reference_video_path)
    face_w, face_h, text_w, text_h = _layout_sizes(
        frame_w=width,
        frame_h=height,
        face_img=face_img,
        face_position=face_position,
        face_scale=face_scale,
    )
    text_img = _render_document_preview(document_path, text_w, text_h, font_size)
    face_img = face_img.resize((face_w, face_h), Image.LANCZOS)

    if face_position == "left":
        canvas.paste(face_img, (0, 0))
        canvas.paste(text_img, (face_w, 0))
    elif face_position == "right":
        canvas.paste(text_img, (0, 0))
        canvas.paste(face_img, (text_w, 0))
    elif face_position == "center":
        canvas.paste(face_img, ((width - face_w) // 2, 0))
        canvas.paste(text_img, (0, face_h))
    else:
        margin = max(16, int(min(width, height) * 0.03))
        x = margin if face_position.endswith("left") else width - face_w - margin
        y = margin if face_position.startswith("top") else height - face_h - margin
        text_x = width - text_w if face_position.endswith("left") else 0
        canvas.paste(text_img, (text_x, 0))
        canvas.paste(face_img, (x, y))

    return canvas


def _layout_sizes(
    *,
    frame_w: int,
    frame_h: int,
    face_img: Image.Image,
    face_position: str,
    face_scale: float,
) -> tuple[int, int, int, int]:
    src_face_w, src_face_h = face_img.size
    margin = max(16, int(min(frame_w, frame_h) * 0.03))

    if face_position in OVERLAY_POSITIONS:
        face_w = max(1, int(frame_w * face_scale))
        face_h = max(1, int(src_face_h * face_w / max(src_face_w, 1)))
        if face_h > frame_h - (margin * 2):
            face_h = max(1, frame_h - (margin * 2))
            face_w = max(1, int(src_face_w * face_h / max(src_face_h, 1)))
        rail_w = min(frame_w - 1, face_w + (margin * 2))
        return face_w, face_h, max(1, frame_w - rail_w), frame_h

    if face_position in ("left", "right"):
        return frame_w // 2, frame_h, frame_w // 2, frame_h

    face_w = frame_w // 2
    face_h = frame_h // 2
    return face_w, face_h, frame_w, max(1, frame_h - face_h)


def _load_video_frame(video_path: str) -> Image.Image:
    # Ask ffmpeg for a representative frame from the early part of the clip.
    # This avoids blank/fade-in frames at the start while keeping the preview cheap.
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        video_path,
        "-t",
        "10",
        "-vf",
        "thumbnail=60",
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and result.stdout:
        return Image.open(io.BytesIO(result.stdout)).convert("RGB")

    for timestamp in ("1", "0.5", "0"):
        fallback = [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            timestamp,
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ]
        fallback_result = subprocess.run(fallback, capture_output=True)
        if fallback_result.returncode == 0 and fallback_result.stdout:
            return Image.open(io.BytesIO(fallback_result.stdout)).convert("RGB")

    raise ValueError("could not read a frame from the reference video")


def _render_document_preview(
    document_path: str,
    width: int,
    height: int,
    font_size: int,
) -> Image.Image:
    ext = os.path.splitext(document_path)[1].lower()
    if ext == ".pdf":
        try:
            raw, _zoom = render_page_image_with_zoom(document_path, 1, target_width=width * 2)
            return _fit_image(raw, width, height)
        except Exception:
            pass

    text = _preview_text(document_path)
    renderer = HighlightRenderer(
        width=width,
        height=height,
        font_size=font_size,
        highlight_color=DEFAULT_HIGHLIGHT_COLOR,
        text_color=DEFAULT_TEXT_COLOR,
        bg_color=DEFAULT_BG_COLOR,
    )
    words = text.split()[:120] or ["Preview"]
    layout = renderer.layout_words(words)
    scroll = renderer.compute_scroll_offset(layout, 0)
    return renderer.render_frame(layout, active_index=0, scroll_offset=scroll)


def _fit_image(img: Image.Image, width: int, height: int) -> Image.Image:
    img = img.convert("RGB")
    scale = min(width / img.width, height / img.height)
    new_w = max(1, int(img.width * scale))
    new_h = max(1, int(img.height * scale))
    fitted = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (width, height), DEFAULT_BG_COLOR)
    canvas.paste(fitted, ((width - new_w) // 2, (height - new_h) // 2))
    return canvas


def _preview_text(document_path: str) -> str:
    try:
        text = extract_text(document_path)
    except Exception:
        text = ""
    text = " ".join(text.split())
    return text[:1600] if text else "Preview frame"
