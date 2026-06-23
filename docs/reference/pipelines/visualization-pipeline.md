# Visualization Pipeline

> Prompt-to-Manim pipeline that generates source code, renders an MP4, and records render metadata.

**Source:** [`screencastgen/pipelines/visualization.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/pipelines/visualization.py)

---

## Function

### `run_visualization_pipeline(request, reporter, renderer) -> PipelineRunResult`

Validates a [VisualizationPipelineRequest](pipeline-types.md), writes a generated Manim scene to `generated_visualization.py`, renders it through a visualization provider, and writes `visualization_metadata.json`.

---

## Steps

```
1. Validate prompt, resolution, FPS, and provider
2. Generate ManimGL-compatible source from prompt/style/audience_level
3. Write generated_visualization.py into output_dir
4. Create renderer via Visualization Registry
5. Render to output MP4
6. Probe output duration when moviepy is available
7. Write visualization_metadata.json with prompt, source, command, logs, and clip metadata
```

The built-in scene generator is deterministic template code, not an LLM call. It uses the prompt to produce title/idea labels and a generic animated mathematical curve scene.

---

## Outputs

| File | Description |
|------|-------------|
| `visualization.mp4` | Rendered MP4 output, or the sanitized custom output name |
| `generated_visualization.py` | Generated Manim scene source |
| `visualization_metadata.json` | Prompt, provider, generated source, render command, stdout/stderr excerpts, and clip metadata |

---

## Validation

| Field | Rule |
|-------|------|
| `prompt` | Required after trimming |
| `resolution` | Between `320x240` and `3840x2160` |
| `fps` | 1 to 60 |
| `provider` | `manimgl` or `manimce` |
| `style` | `clean`, `chalkboard`, `blueprint`, or `minimal` |

---

## Dependencies

```
Visualization Pipeline
├── Pipeline Types             (VisualizationPipelineRequest, RenderedVisualClip)
├── Pipeline Events            (PipelineReporter)
├── Highlight Pipeline         (parse_resolution)
└── Visualization Registry     (renderer provider selection)
```

---

## See Also

- [CLI](../core/cli.md) — `screencastgen visualize`
- [Schemas](../web/backend/schemas.md) — `VisualizationConfig`
- [Pipeline Tasks](../web/backend/pipeline-tasks.md) — Web worker dispatch for visualization jobs
- [ManimGL Renderer](../providers/manim-gl-renderer.md) — Primary renderer adapter
