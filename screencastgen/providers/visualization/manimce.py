"""Manim Community renderer placeholder."""

from __future__ import annotations

from .base import VisualizationRenderer, VisualizationRenderRequest, VisualizationRenderResult


class ManimCERenderer(VisualizationRenderer):
    """Command adapter for Manim Community Edition.

    Rendering is intentionally disabled until the pipeline is tested against
    Manim CE scene compatibility. The command builder exists so callers and
    tests can exercise provider selection without invoking Manim.
    """

    name = "manimce"

    def __init__(self, executable: str = "manim") -> None:
        self.executable = executable

    def build_command(self, request: VisualizationRenderRequest) -> list[str]:
        stem = request.output_name.rsplit(".", 1)[0]
        return [
            self.executable,
            "render",
            request.scene_file,
            request.scene_class,
            "-o",
            stem,
            "--media_dir",
            request.output_dir,
            "-r",
            f"{request.width},{request.height}",
            "--fps",
            str(request.fps),
        ]

    def render(self, request: VisualizationRenderRequest) -> VisualizationRenderResult:
        command = self.build_command(request)
        return VisualizationRenderResult(
            success=False,
            output_path=None,
            command=command,
            error_message="Manim Community renderer is not implemented yet",
        )
