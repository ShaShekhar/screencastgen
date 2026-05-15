"""ManimGL renderer provider."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .base import VisualizationRenderer, VisualizationRenderRequest, VisualizationRenderResult


def _excerpt(text: str, limit: int = 8000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _safe_env() -> dict[str, str]:
    """Return a minimal environment for a renderer subprocess."""
    keys = [
        "PATH",
        "LANG",
        "LC_ALL",
        "DISPLAY",
        "XDG_RUNTIME_DIR",
        "LD_LIBRARY_PATH",
        "LIBGL_ALWAYS_SOFTWARE",
        "PYTHONPATH",
    ]
    return {key: value for key in keys if (value := os.environ.get(key))}


def _find_rendered_mp4(render_dir: str, *, since: float) -> str | None:
    candidates = [
        str(path)
        for path in Path(render_dir).rglob("*.mp4")
        if path.is_file() and os.path.getmtime(path) >= since
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


class ManimGLRenderer(VisualizationRenderer):
    """Render scenes with 3Blue1Brown ManimGL (``manimgl``)."""

    name = "manimgl"

    def __init__(self, executable: str = "manimgl") -> None:
        self.executable = executable

    def build_command(self, request: VisualizationRenderRequest) -> list[str]:
        return [
            self.executable,
            request.scene_file,
            request.scene_class,
            "-w",
            "--video_dir",
            request.output_dir,
            "--resolution",
            f"{request.height},{request.width}",
            "--fps",
            str(request.fps),
        ]

    def render(self, request: VisualizationRenderRequest) -> VisualizationRenderResult:
        command = self.build_command(request)
        if shutil.which(self.executable) is None:
            return VisualizationRenderResult(
                success=False,
                output_path=None,
                command=command,
                error_message=f"Renderer executable not found: {self.executable}",
            )

        os.makedirs(request.output_dir, exist_ok=True)
        started_at = time.time()
        with tempfile.TemporaryDirectory(prefix="manimgl-home-") as home_dir:
            env = _safe_env()
            env["HOME"] = home_dir
            try:
                proc = subprocess.run(
                    command,
                    cwd=os.path.dirname(request.scene_file) or None,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=request.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                return VisualizationRenderResult(
                    success=False,
                    output_path=None,
                    command=command,
                    stdout=_excerpt(exc.stdout or ""),
                    stderr=_excerpt(exc.stderr or ""),
                    error_message=f"Render timed out after {request.timeout_seconds} seconds",
                )

        stdout = _excerpt(proc.stdout or "")
        stderr = _excerpt(proc.stderr or "")
        if proc.returncode != 0:
            return VisualizationRenderResult(
                success=False,
                output_path=None,
                command=command,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                error_message=f"Renderer exited with code {proc.returncode}",
            )

        rendered = _find_rendered_mp4(request.output_dir, since=started_at)
        if rendered is None:
            return VisualizationRenderResult(
                success=False,
                output_path=None,
                command=command,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                error_message="Renderer completed but no MP4 output was found",
            )

        output_path = request.output_path
        if os.path.abspath(rendered) != os.path.abspath(output_path):
            shutil.copyfile(rendered, output_path)

        size = os.path.getsize(output_path)
        if size > request.max_output_bytes:
            return VisualizationRenderResult(
                success=False,
                output_path=None,
                command=command,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                error_message=(
                    f"Rendered output is {size} bytes, exceeding "
                    f"{request.max_output_bytes} bytes"
                ),
            )

        return VisualizationRenderResult(
            success=True,
            output_path=output_path,
            command=command,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            metadata={"rendered_path": rendered, "size_bytes": size},
        )
