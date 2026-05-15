"""Renderer provider contract for generated visualization scenes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class VisualizationRenderRequest:
    """A renderable Python scene file and controlled output target."""

    scene_file: str
    scene_class: str
    output_dir: str
    output_name: str
    width: int
    height: int
    fps: int
    timeout_seconds: int = 300
    max_output_bytes: int = 512 * 1024 * 1024

    @property
    def output_path(self) -> str:
        import os

        return os.path.join(self.output_dir, self.output_name)


@dataclass
class VisualizationRenderResult:
    """Result returned by renderer providers."""

    success: bool
    output_path: str | None
    command: list[str]
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    error_message: str | None = None
    metadata: dict = field(default_factory=dict)


class VisualizationRenderer:
    """Abstract renderer adapter."""

    name = "base"

    def build_command(self, request: VisualizationRenderRequest) -> Sequence[str]:
        raise NotImplementedError

    def render(self, request: VisualizationRenderRequest) -> VisualizationRenderResult:
        raise NotImplementedError
