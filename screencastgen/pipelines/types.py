"""Pipeline request/result types."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Optional, Type, TypeVar

from ..constants import (
    DEFAULT_FONT_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_STATUS_FILE,
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
)


@dataclass
class BasePipelineRequest:
    """Options shared by all pipeline runners."""

    pdf: str
    output: Optional[str] = None
    output_dir: str = DEFAULT_OUTPUT_DIR
    language: str = DEFAULT_LANGUAGE
    status_file: str = DEFAULT_STATUS_FILE
    clean: bool = False
    verbose: bool = False


@dataclass
class TTSRequest(BasePipelineRequest):
    """Common TTS-related options."""

    backend: str = "qwen"
    device: str = "auto"
    voice: Optional[str] = None
    model: Optional[str] = None
    ref_audio: Optional[str] = None
    ref_text: Optional[str] = None
    tts_server_url: Optional[str] = None
    aligner: str = "whisperx"
    tts_concurrency: int = 1


@dataclass
class AudioPipelineRequest(TTSRequest):
    """Input for the audio pipeline."""

    no_concat: bool = False


@dataclass
class HighlightPipelineRequest(TTSRequest):
    """Input for the highlight pipeline."""

    format: str = "epub"
    font_size: int = DEFAULT_FONT_SIZE
    resolution: str = f"{DEFAULT_VIDEO_WIDTH}x{DEFAULT_VIDEO_HEIGHT}"
    fps: int = DEFAULT_VIDEO_FPS


@dataclass
class LipsyncPipelineRequest(HighlightPipelineRequest):
    """Input for the lip-sync pipeline."""

    format: str = "reader"
    ref_video: str = ""
    lipsync_provider: str = "auto"
    face_position: str = "bottom-right"
    face_scale: float = 0.22
    latentsync_preset: str = "quality"


@dataclass
class VisualizationPipelineRequest:
    """Input for the prompt-to-Manim visualization pipeline."""

    prompt: str
    output: Optional[str] = None
    output_dir: str = DEFAULT_OUTPUT_DIR
    provider: str = "manimgl"
    duration_seconds: int = 30
    resolution: str = f"{DEFAULT_VIDEO_WIDTH}x{DEFAULT_VIDEO_HEIGHT}"
    fps: int = DEFAULT_VIDEO_FPS
    style: str = "clean"
    audience_level: str = "general"
    iteration_of_job_id: Optional[str] = None
    timeout_seconds: int = 300
    max_output_bytes: int = 512 * 1024 * 1024
    clean: bool = False
    verbose: bool = False


@dataclass
class RenderedVisualClip:
    """Metadata for a rendered visual clip that can be composed later."""

    path: str
    duration: Optional[float]
    fps: int
    width: int
    height: int
    source_prompt: str
    source_code: str


@dataclass
class PipelineRunResult:
    """Return value for a pipeline run."""

    exit_code: int
    output_name: Optional[str] = None
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _field_names(request_type: Type[Any]) -> set[str]:
    return {field.name for field in fields(request_type)}


RequestT = TypeVar("RequestT", bound=BasePipelineRequest)


def coerce_request(request_type: Type[RequestT], value: Any) -> RequestT:
    """Convert *value* into *request_type* when needed."""
    if isinstance(value, request_type):
        return value

    data = {}
    names = _field_names(request_type)
    if isinstance(value, dict):
        data.update({key: value[key] for key in names if key in value})
    else:
        for field in fields(request_type):
            if hasattr(value, field.name):
                data[field.name] = getattr(value, field.name)
    return request_type(**data)
