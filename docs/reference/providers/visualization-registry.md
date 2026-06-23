# Visualization Registry

> Renderer factory for prompt-generated visualization scenes.

**Source:** [`screencastgen/providers/visualization/__init__.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/visualization/__init__.py)

---

## Overview

The visualization registry selects a renderer implementing the [VisualizationRenderer](manim-gl-renderer.md) contract from `base.py`.

Unlike the TTS/alignment/lip-sync registries, this registry is currently a small direct factory rather than a spec-based lazy importer.

---

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `get_renderer_names()` | `["manimgl", "manimce"]` | Available renderer names |
| `get_default_renderer_name()` | `"manimgl"` | CLI/web default |
| `create_renderer(name)` | `VisualizationRenderer` | Instantiates `ManimGLRenderer` or `ManimCERenderer` |

---

## Provider Contract

`base.py` defines:

| Type | Purpose |
|------|---------|
| `VisualizationRenderRequest` | Scene file/class, output target, resolution, fps, timeout, and max output bytes |
| `VisualizationRenderResult` | Success flag, output path, command, return code, log excerpts, error, metadata |
| `VisualizationRenderer` | Abstract `build_command()` and `render()` methods |

---

## See Also

- [Visualization Pipeline](../pipelines/visualization-pipeline.md) — Pipeline that calls this registry
- [ManimGL Renderer](manim-gl-renderer.md) — Implemented renderer
- [ManimCE Renderer](manim-ce-renderer.md) — Stub renderer
