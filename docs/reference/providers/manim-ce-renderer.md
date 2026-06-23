# ManimCE Renderer

> Manim Community Edition command adapter placeholder.

**Source:** [`screencastgen/providers/visualization/manimce.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/visualization/manimce.py)

---

## Status

`ManimCERenderer` builds the expected Manim Community command, but `render()` intentionally returns `success=False` with:

```text
Manim Community renderer is not implemented yet
```

This lets CLI/web validation and provider selection be exercised without claiming Manim CE scene compatibility.

---

## Command Shape

```bash
manim render generated_visualization.py GeneratedVisualizationScene \
  -o visualization \
  --media_dir <output_dir> \
  -r <width>,<height> \
  --fps <fps>
```

---

## See Also

- [Visualization Pipeline](../pipelines/visualization-pipeline.md)
- [Visualization Registry](visualization-registry.md)
- [ManimGL Renderer](manim-gl-renderer.md)
