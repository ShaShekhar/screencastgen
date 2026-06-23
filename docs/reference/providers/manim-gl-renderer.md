# ManimGL Renderer

> Subprocess adapter for rendering generated scenes with 3Blue1Brown ManimGL.

**Source:** [`screencastgen/providers/visualization/manimgl.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/visualization/manimgl.py)

---

## Behavior

`ManimGLRenderer.render()`:

1. Builds a `manimgl` command for the generated scene file/class.
2. Runs the renderer in a temporary `HOME` with a minimal safe environment.
3. Searches the render directory for a newly produced MP4.
4. Copies that MP4 to the requested output path if necessary.
5. Enforces `max_output_bytes`.
6. Returns a `VisualizationRenderResult` with command, logs, return code, and output metadata.

---

## Command Shape

```bash
manimgl generated_visualization.py GeneratedVisualizationScene \
  -w \
  --video_dir <output_dir> \
  --resolution <height>,<width> \
  --fps <fps>
```

ManimGL expects resolution as `height,width`.

---

## Failure Modes

| Condition | Result |
|-----------|--------|
| `manimgl` not found on `PATH` | `success=False`, renderer executable error |
| Subprocess timeout | `success=False`, timeout error with log excerpts |
| Non-zero exit | `success=False`, return code and logs |
| No MP4 found | `success=False`, missing-output error |
| Output too large | `success=False`, size guardrail error |

---

## See Also

- [Visualization Pipeline](../pipelines/visualization-pipeline.md)
- [Visualization Registry](visualization-registry.md)
- [ManimCE Renderer](manim-ce-renderer.md)
