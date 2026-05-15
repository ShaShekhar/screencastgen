"""Tests for the visualization pipeline and renderer adapters."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from screencastgen.pipelines.types import VisualizationPipelineRequest
from screencastgen.pipelines.visualization import run_visualization_pipeline
from screencastgen.providers.visualization.base import (
    VisualizationRenderer,
    VisualizationRenderRequest,
    VisualizationRenderResult,
)
from screencastgen.providers.visualization.manimce import ManimCERenderer
from screencastgen.providers.visualization.manimgl import ManimGLRenderer


class FakeRenderer(VisualizationRenderer):
    name = "fake"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.request: VisualizationRenderRequest | None = None

    def build_command(self, request: VisualizationRenderRequest) -> list[str]:
        return ["fake-render", request.scene_file, request.scene_class]

    def render(self, request: VisualizationRenderRequest) -> VisualizationRenderResult:
        self.request = request
        command = self.build_command(request)
        if self.fail:
            return VisualizationRenderResult(
                success=False,
                output_path=None,
                command=command,
                returncode=2,
                stderr="scene failed",
                error_message="fake render failed",
            )
        with open(request.output_path, "wb") as f:
            f.write(b"\x00\x00\x00\x18ftypmp42")
        return VisualizationRenderResult(
            success=True,
            output_path=request.output_path,
            command=command,
            returncode=0,
            stdout="ok",
        )


def test_manimgl_command_construction(tmp_path):
    req = VisualizationRenderRequest(
        scene_file=str(tmp_path / "scene.py"),
        scene_class="DemoScene",
        output_dir=str(tmp_path),
        output_name="demo.mp4",
        width=1280,
        height=720,
        fps=24,
    )

    command = ManimGLRenderer(executable="manimgl").build_command(req)

    assert command[:4] == ["manimgl", req.scene_file, "DemoScene", "-w"]
    assert "--video_dir" in command
    assert "--resolution" in command
    assert "720,1280" in command
    assert "--fps" in command
    assert "24" in command


def test_manimce_command_construction(tmp_path):
    req = VisualizationRenderRequest(
        scene_file=str(tmp_path / "scene.py"),
        scene_class="DemoScene",
        output_dir=str(tmp_path),
        output_name="demo.mp4",
        width=1280,
        height=720,
        fps=30,
    )

    command = ManimCERenderer(executable="manim").build_command(req)

    assert command[:4] == ["manim", "render", req.scene_file, "DemoScene"]
    assert "-o" in command
    assert "demo" in command
    assert "-r" in command
    assert "1280,720" in command
    assert "--fps" in command
    assert "30" in command


def test_visualization_pipeline_with_fake_renderer_succeeds(tmp_path):
    renderer = FakeRenderer()
    request = VisualizationPipelineRequest(
        prompt="Show why the derivative is a slope",
        output_dir=str(tmp_path),
        output="lesson.mp4",
        provider="manimgl",
        resolution="854x480",
        fps=12,
    )

    result = run_visualization_pipeline(request, renderer=renderer)

    assert result.exit_code == 0
    assert result.output_name == "lesson.mp4"
    assert result.output_path is not None
    assert os.path.isfile(result.output_path)
    assert os.path.isfile(tmp_path / "generated_visualization.py")
    assert result.metadata["scene_class"] == "GeneratedVisualizationScene"
    assert result.metadata["clip"]["width"] == 854
    assert renderer.request is not None
    assert renderer.request.fps == 12


def test_visualization_pipeline_with_fake_renderer_failure(tmp_path):
    result = run_visualization_pipeline(
        VisualizationPipelineRequest(
            prompt="Bad scene",
            output_dir=str(tmp_path),
            provider="manimgl",
        ),
        renderer=FakeRenderer(fail=True),
    )

    assert result.exit_code == 1
    assert "fake render failed" in (result.error_message or "")
    assert "scene failed" in (result.error_message or "")
    assert result.metadata["stderr_excerpt"] == "scene failed"


def test_visualization_schema_validation():
    from pydantic import ValidationError
    from web.backend.schemas import JobCreateRequest, VisualizationConfig

    cfg = VisualizationConfig(prompt="Explain vectors", provider="manimgl", width=1280, height=720, fps=24)
    req = JobCreateRequest(pipeline_type="visualization", visualization_config=cfg)
    assert req.uploaded_file_id is None

    with pytest.raises(ValidationError):
        VisualizationConfig(prompt="Explain vectors", provider="unknown")

    with pytest.raises(ValidationError):
        VisualizationConfig(prompt="Explain vectors", fps=120)


def test_visualization_dispatch_routes_to_pipeline(tmp_path):
    from screencastgen.pipelines.visualization import run_visualization_pipeline as expected
    from web.backend.models import PipelineType
    from web.backend.tasks.pipelines import _build_pipeline_dispatch

    job = SimpleNamespace(
        pipeline_type=PipelineType.visualization,
        config_json={
            "prompt": "Animate matrix multiplication",
            "provider": "manimgl",
            "width": 1280,
            "height": 720,
            "fps": 24,
        },
    )

    request, func = _build_pipeline_dispatch(job, None, str(tmp_path), db_session=None)

    assert isinstance(request, VisualizationPipelineRequest)
    assert request.prompt == "Animate matrix multiplication"
    assert func is expected
