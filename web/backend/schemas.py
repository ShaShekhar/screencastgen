"""Pydantic request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from screencastgen.constants import (
    DEFAULT_FONT_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
)


# --- Config sub-models for each pipeline ---

class AudioConfig(BaseModel):
    backend: str = "remote"
    language: str = DEFAULT_LANGUAGE
    tts_server_url: Optional[str] = None
    aligner: str = "whisperx"
    model_config = {"extra": "forbid"}


class HighlightConfig(AudioConfig):
    font_size: int = DEFAULT_FONT_SIZE
    width: int = DEFAULT_VIDEO_WIDTH
    height: int = DEFAULT_VIDEO_HEIGHT
    fps: int = DEFAULT_VIDEO_FPS


class LipsyncConfig(BaseModel):
    ref_audio_file_id: UUID
    ref_video_file_id: UUID
    ref_text: Optional[str] = None
    backend: str = "remote"
    aligner: str = "whisperx"
    lipsync_provider: str = "auto"
    device: str = "auto"
    face_position: str = "left"
    font_size: int = DEFAULT_FONT_SIZE
    width: int = DEFAULT_VIDEO_WIDTH
    height: int = DEFAULT_VIDEO_HEIGHT
    fps: int = DEFAULT_VIDEO_FPS
    model_config = {"extra": "forbid"}


# --- Requests ---

class JobCreateRequest(BaseModel):
    pipeline_type: str  # audio, highlight, lipsync
    uploaded_file_id: UUID
    audio_config: Optional[AudioConfig] = None
    highlight_config: Optional[HighlightConfig] = None
    lipsync_config: Optional[LipsyncConfig] = None
    model_config = {"extra": "forbid"}


# --- Responses ---

class UploadResponse(BaseModel):
    id: UUID
    original_name: str
    size_bytes: int
    content_type: str


class JobResponse(BaseModel):
    id: UUID
    pipeline_type: str
    status: str
    progress_current: int
    progress_total: int
    progress_phase: str
    error_message: Optional[str]
    config_json: dict
    uploaded_file_id: UUID
    ref_audio_file_id: Optional[UUID]
    ref_video_file_id: Optional[UUID]
    output_path: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int


class ProgressEvent(BaseModel):
    job_id: str
    status: str
    phase: str
    current: int
    total: int
    message: str = ""
