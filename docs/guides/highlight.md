# Generate synchronized highlighting

The highlight pipeline adds word-level alignment to synthesized narration. PDF
inputs use the original page images and word positions; other supported formats
fall back to rendered text.

## EPUB reader output

EPUB is the default output format:

```bash
screencastgen highlight book.pdf --format epub -o book-highlight.epub
```

## MP4 output

```bash
screencastgen highlight book.pdf \
  --format mp4 \
  --resolution 1280x720 \
  --fps 24 \
  -o book-highlight.mp4
```

The local path requires the Qwen and WhisperX dependencies. To offload model
work, add `--backend remote --tts-server-url http://gpu-vm:8100`.

Use `--font-size` to tune fallback text rendering. PDF page-image rendering
keeps the source layout and matches aligned words to their original bounding
boxes.

See [Pipeline overview](../concepts/pipelines.md) for processing stages and the
[Highlight Pipeline reference](../reference/pipelines/highlight-pipeline.md)
for implementation details.
