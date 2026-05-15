"""Visualization renderer provider registry."""

from __future__ import annotations

from .base import VisualizationRenderer, VisualizationRenderRequest, VisualizationRenderResult
from .manimce import ManimCERenderer
from .manimgl import ManimGLRenderer


def get_renderer_names() -> list[str]:
    return ["manimgl", "manimce"]


def get_default_renderer_name() -> str:
    return "manimgl"


def create_renderer(name: str | None = None) -> VisualizationRenderer:
    provider = (name or get_default_renderer_name()).lower()
    if provider == "manimgl":
        return ManimGLRenderer()
    if provider == "manimce":
        return ManimCERenderer()
    raise ValueError(f"Unknown visualization renderer: {name}")


__all__ = [
    "ManimCERenderer",
    "ManimGLRenderer",
    "VisualizationRenderer",
    "VisualizationRenderRequest",
    "VisualizationRenderResult",
    "create_renderer",
    "get_default_renderer_name",
    "get_renderer_names",
]
