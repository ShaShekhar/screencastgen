# CLI

> Argument parsing, subcommand dispatch, and pipeline invocation.

**Source:** [`screencastgen/cli.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/cli.py)
**Entry point:** `screencastgen` (console script) or `python -m screencastgen`

---

## Overview

The CLI is the primary user-facing entry point. It builds an `argparse` parser with subcommands, parses arguments, and dispatches to the appropriate pipeline runner.

---

## Functions

### `main(argv=None) -> int`
Top-level entry point. Parses args and dispatches to the selected subcommand runner.

### `_build_parser() -> argparse.ArgumentParser`
Constructs the argument parser with subcommands:
- `audio` — Run the [Audio Pipeline](../pipelines/audio-pipeline.md)
- `highlight` — Run the [Highlight Pipeline](../pipelines/highlight-pipeline.md)
- `lipsync` — Run the [Lipsync Pipeline](../pipelines/lipsync-pipeline.md)
- `visualize` — Run the [Visualization Pipeline](../pipelines/visualization-pipeline.md)
- `download-models` — Download ML models via [Models](models.md)
- `doctor` — Validate the active environment via [Doctor](doctor.md)

Registers backend-specific arguments from [TTS Registry](../providers/tts-registry.md) and alignment/lipsync provider args.

### `run_audio_pipeline(args) -> int`
### `run_highlight_pipeline(args) -> int`
### `run_lipsync_pipeline(args) -> int`
Thin wrappers that delegate to the corresponding pipeline runner in [Audio Pipeline](../pipelines/audio-pipeline.md), [Highlight Pipeline](../pipelines/highlight-pipeline.md), [Lipsync Pipeline](../pipelines/lipsync-pipeline.md).

### `run_visualization_pipeline(args) -> int`
Delegates to [Visualization Pipeline](../pipelines/visualization-pipeline.md).

### `run_download_models(args) -> int`
Delegates to `download_selected_models()` in [Models](models.md).

### `run_doctor(args) -> int`
Delegates to `run_doctor()` in [Doctor](doctor.md). The diagnostic module is imported only when the command runs.

---

## Dependencies

```
cli.py
├── screencastgen.__init__        (version)
├── Constants                  (defaults)
├── Audio Pipeline             (run_audio_pipeline)
├── Highlight Pipeline         (run_highlight_pipeline, parse_resolution)
├── Lipsync Pipeline           (run_lipsync_pipeline)
├── Visualization Pipeline      (run_visualization_pipeline)
├── Pipeline Common            (extract_and_chunk, synthesize_chunks)
├── Models                     (register/download)
├── Doctor                     (environment diagnostics)
├── TTS Registry               (backend names, arg registration)
├── Aligner                    (provider names)
└── Lipsync Facade             (provider names)
```

---

## Usage Examples

```bash
# Audio only
screencastgen audio MyBook.pdf --backend qwen --device cuda

# Highlighted text video
screencastgen highlight MyBook.pdf --backend qwen

# Lip-sync video
screencastgen lipsync MyBook.pdf --backend qwen --ref-audio voice.wav --ref-video face.mp4 --format reader

# Generated visualization
screencastgen visualize --prompt "Explain tangent slope" --renderer manimgl

# Remote GPU
screencastgen audio MyBook.pdf --backend remote --tts-server-url http://gpu:8100

# Download models
screencastgen download-models --backend qwen --package whisperx

# Validate an installed profile without changing it
screencastgen doctor --profile remote-client --server-url http://gpu:8100
```

---

## See Also

- [Inference Server](inference-server.md) — The other entry point (`screencastgen-server`)
- [Pipeline Overview](../../concepts/pipelines.md) — How pipelines are structured
- [Pipeline Types](../pipelines/pipeline-types.md) — Request dataclasses passed to runners
