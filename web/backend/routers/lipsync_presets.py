"""Bundled lip-sync presenter preset endpoints."""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..services.lipsync_presets import get_lipsync_preset, load_lipsync_presets

router = APIRouter(tags=["lipsync-presets"])


class LipsyncPresetResponse(BaseModel):
    id: str
    name: str
    language: str
    description: str
    ref_text: str
    has_audio: bool
    available: bool


@router.get("/lipsync-presets", response_model=list[LipsyncPresetResponse])
async def list_lipsync_presets():
    return [
        LipsyncPresetResponse(
            id=preset.id,
            name=preset.name,
            language=preset.language,
            description=preset.description,
            ref_text=preset.ref_text,
            has_audio=bool(preset.audio_file),
            available=preset.exists,
        )
        for preset in load_lipsync_presets()
    ]


@router.get("/lipsync-presets/{preset_id}/video")
async def lipsync_preset_video(preset_id: str):
    preset = get_lipsync_preset(preset_id)
    if not preset:
        raise HTTPException(404, "Lip-sync preset not found")
    if not preset.video_exists:
        raise HTTPException(
            404,
            f"Lip-sync preset '{preset_id}' has no video file at {preset.video_file}",
        )
    media_type = mimetypes.guess_type(preset.video_file)[0] or "video/mp4"
    return FileResponse(
        preset.video_abs_path,
        media_type=media_type,
        filename=preset.video_file,
    )


@router.get("/lipsync-presets/{preset_id}/audio")
async def lipsync_preset_audio(preset_id: str):
    preset = get_lipsync_preset(preset_id)
    if not preset:
        raise HTTPException(404, "Lip-sync preset not found")
    if not preset.audio_file or not preset.audio_exists:
        raise HTTPException(
            404,
            f"Lip-sync preset '{preset_id}' has no audio file at {preset.audio_file}",
        )
    media_type = mimetypes.guess_type(preset.audio_file)[0] or "audio/wav"
    return FileResponse(
        preset.audio_abs_path,
        media_type=media_type,
        filename=preset.audio_file,
    )
