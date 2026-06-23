"""Pydantic request/response schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

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
    # Output format: "epub" = EPUB3 with Media Overlays (audio + word sync),
    # "mp4" = rendered video with page images and highlighted text.
    format: str = "epub"

    # Voice selection: either a bundled voice id or an uploaded reference
    # audio file id. Both are optional — when neither is set, the GPU
    # server's default voice is used.
    voice_id: Optional[str] = None
    ref_audio_file_id: Optional[UUID] = None
    ref_text: Optional[str] = None

    font_size: int = DEFAULT_FONT_SIZE
    width: int = DEFAULT_VIDEO_WIDTH
    height: int = DEFAULT_VIDEO_HEIGHT
    fps: int = DEFAULT_VIDEO_FPS

    @model_validator(mode="after")
    def _voice_xor(self) -> "HighlightConfig":
        if self.voice_id and self.ref_audio_file_id:
            raise ValueError(
                "Provide either voice_id (bundled) or ref_audio_file_id (uploaded), not both"
            )
        if self.format not in ("epub", "mp4"):
            raise ValueError("format must be 'epub' or 'mp4'")
        return self


class LipsyncConfig(BaseModel):
    ref_audio_file_id: Optional[UUID] = None
    ref_video_file_id: UUID
    backend: str = "remote"
    aligner: str = "whisperx"
    face_position: str = "bottom-right"
    face_scale: float = 0.22
    latentsync_preset: str = "quality"
    font_size: int = DEFAULT_FONT_SIZE
    width: int = DEFAULT_VIDEO_WIDTH
    height: int = DEFAULT_VIDEO_HEIGHT
    fps: int = DEFAULT_VIDEO_FPS
    format: str = "reader"
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_format(self) -> "LipsyncConfig":
        if self.format not in ("reader", "mp4", "epub"):
            raise ValueError("format must be 'reader', 'mp4', or 'epub'")
        return self


class VisualizationConfig(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    provider: str = "manimgl"
    duration_seconds: int = Field(default=30, ge=3, le=600)
    width: int = Field(default=DEFAULT_VIDEO_WIDTH, ge=320, le=3840)
    height: int = Field(default=DEFAULT_VIDEO_HEIGHT, ge=240, le=2160)
    fps: int = Field(default=DEFAULT_VIDEO_FPS, ge=1, le=60)
    style: str = "clean"
    audience_level: str = "general"
    iteration_of_job_id: Optional[UUID] = None
    model_config = {"extra": "forbid"}

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt is required")
        return value

    @field_validator("provider")
    @classmethod
    def _valid_provider(cls, value: str) -> str:
        if value not in ("manimgl", "manimce"):
            raise ValueError("provider must be 'manimgl' or 'manimce'")
        return value

    @field_validator("style")
    @classmethod
    def _valid_style(cls, value: str) -> str:
        if value not in ("clean", "chalkboard", "blueprint", "minimal"):
            raise ValueError("style must be one of clean, chalkboard, blueprint, minimal")
        return value


# --- Requests ---

class JobCreateRequest(BaseModel):
    pipeline_type: str  # audio, highlight, lipsync, visualization
    uploaded_file_id: Optional[UUID] = None
    audio_config: Optional[AudioConfig] = None
    highlight_config: Optional[HighlightConfig] = None
    lipsync_config: Optional[LipsyncConfig] = None
    visualization_config: Optional[VisualizationConfig] = None
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _required_config(self) -> "JobCreateRequest":
        if self.pipeline_type in ("audio", "highlight", "lipsync") and self.uploaded_file_id is None:
            raise ValueError("uploaded_file_id is required for document pipelines")
        if self.pipeline_type == "lipsync" and self.lipsync_config is None:
            raise ValueError("lipsync_config is required for lipsync jobs")
        if self.pipeline_type == "visualization" and self.visualization_config is None:
            raise ValueError("visualization_config is required for visualization jobs")
        return self


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
    uploaded_file_id: Optional[UUID]
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
