# screencastgen

Audio-synchronized document readers with text highlighting and lip-sync video.
Convert PDF, EPUB, plain-text, and other documents into narrated audio,
highlighted readers, or LipSync Reader presentations.

Supports pluggable TTS backends, alignment providers, and lip-sync providers.
The supported implementations are Qwen for TTS, WhisperX for alignment, and
LatentSync for lip-sync.

## Documentation

Read the [documentation site](https://shashekhar.github.io/screencastgen/) for
guided workflows, architecture, troubleshooting, and the developer reference.
The Markdown source is maintained in [`docs/`](docs/).

Try the hosted
[interactive demo reader](https://shashekhar.github.io/screencastgen/demo-reader/)
to see synchronized narration, text highlighting, and the presenter view.

Preview documentation changes locally with:

```bash
pip install -e ".[docs]"
mkdocs serve
mkdocs build --strict
```

## Quick Start

Start with the [Getting Started guide](docs/getting-started/index.md) for
installation, environment verification, and first pipeline commands. The
[Installation Guide](INSTALLATION.md) covers Docker-based GPU VM deployments and
source installation.

## Pipelines

screencastgen includes three document pipelines:

- [Lip-sync](docs/guides/lip-sync.md): generate a LipSync Reader or EPUB from
  a document, reference voice, and reference face video.
- [Highlight](docs/guides/highlight.md): generate synchronized word
  highlighting over PDF page images or reflowed document text.
- [Audio](docs/guides/audio.md): generate narrated audio from a document.

See the [pipeline overview](docs/concepts/pipelines.md) for shared processing
stages and the [CLI reference](docs/reference/core/cli.md) for command options.

## Model Dependencies and References

The ML providers are maintained independently. Review their repositories, model
cards, licenses, and usage restrictions before distributing generated content or
deploying commercially.

| Component      | Used for                                    | Resources                                                                                                                                                                             |
| -------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qwen3-TTS      | Default local TTS and voice cloning         | [GitHub](https://github.com/QwenLM/Qwen3-TTS), [0.6B model](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base), [1.7B model](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) |
| WhisperX       | Transcription and word-level alignment      | [GitHub](https://github.com/m-bain/whisperX)                                                                                                                                          |
| LatentSync 1.6 | Default diffusion-based lip synchronization | [GitHub](https://github.com/bytedance/LatentSync), [model weights](https://huggingface.co/ByteDance/LatentSync-1.6), [paper](https://arxiv.org/abs/2412.09262)                        |

This integration uses LatentSync's `latentsync_unet.pt` and Whisper `tiny.pt`
checkpoints. LatentSync lists 18 GB as the minimum VRAM for LatentSync 1.6
inference and publishes its code under Apache 2.0. See the
[LatentSync README](https://github.com/bytedance/LatentSync) for current runtime
requirements and checkpoint details.

## Web Application

Full-stack web UI wrapping all three pipelines. Stack: FastAPI + PostgreSQL +
Celery/Redis + React/Tailwind.

See [Web Application Setup](INSTALLATION.md#web-application-setup) for Docker
and local-development instructions.

By default files are stored on the local filesystem. Set `P2A_STORAGE_BACKEND`
to `gcs` or `s3` to store uploads and outputs in a cloud bucket. Pipelines
always work against local directories; the storage layer handles downloading
inputs and uploading outputs to the bucket.

New web jobs default to the **LipSync Reader** pipeline. The recommended output
is the standalone offline reader ZIP, which preserves the synchronized document,
narration, and presenter experience for local playback.

## Future Directions

The following ideas are exploratory. They are not committed features and do not
have release dates.

- **Presenter background replacement**: Use person segmentation to isolate the
  presenter and replace, blur, or stylize the background.
- **Subject-aware video effects**: Use face and object detection with tracking
  for overlays, masking, reframing, and other controlled visual effects.
- **Diagram-driven presentations**: Animate diagrams created with draw.io or
  Excalidraw in sync with generated narration, with either voice-only output or
  an optional lip-synced presenter overlay.

## Citation

If screencastgen contributes to your research or published work, cite this
repository:

```bibtex
@software{screencastgen,
  author  = {Shekhar, Shashank},
  title   = {screencastgen: Audio-Synchronized Document Readers with Text Highlighting and Lip-Sync Video},
  year    = {2026},
  version = {2.0.0},
  url     = {https://github.com/ShaShekhar/screencastgen}
}
```
