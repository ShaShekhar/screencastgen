# Generate an educational visualization

The visualization pipeline turns a prompt into Manim source and renders an MP4
with the selected visualization provider.

```bash
screencastgen visualize \
  --prompt "Explain the geometric meaning of the Pythagorean theorem" \
  --renderer manimgl \
  --style clean \
  --duration 30 \
  -o pythagorean-theorem.mp4
```

Generated source and render metadata are kept with the output so the scene can
be inspected and reproduced. Use `--resolution`, `--fps`, and
`--audience-level` to control presentation details.

The Manim executable for the selected provider must be installed separately
and available on `PATH`. See the
[Visualization Pipeline reference](../reference/pipelines/visualization-pipeline.md)
for provider and artifact details.
