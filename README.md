# screencastgen

Audio-synchronized document readers with text highlighting and lip-sync video.
Convert PDF, EPUB, plain-text, and other documents into narrated audio,
highlighted readers, or lip-synced talking-head presentations.

Supports pluggable TTS backends, alignment providers, and lip-sync providers. The supported implementations are Qwen for TTS, WhisperX for alignment, and LatentSync for lip-sync.

## Documentation

Read the [documentation site](https://shashekhar.github.io/screencastgen/) for
guided workflows, architecture, troubleshooting, and the developer reference.
The Markdown source is maintained in [`docs/`](docs/).

Preview documentation changes locally with:

```bash
pip install -e ".[docs]"
mkdocs serve
mkdocs build --strict
```

## Quick Start

Complete the platform-specific [Installation Guide](INSTALLATION.md), then run:

```bash
screencastgen doctor --profile auto
screencastgen lipsync MyBook.pdf --ref-audio voice.wav --ref-video face.mp4
```

The guide covers Windows, macOS, Linux, WSL2, remote GPUs, model weights, and
manual installation.

## Pipelines

### Lip-sync (`screencastgen lipsync`)

Generate a talking-head reader with voice cloning, synchronized lip movement,
and highlighted source content. The default output is a standalone reader ZIP:
extract it and open `index.html` locally. PDF inputs use the original page
images and matched word positions; other document formats use reflowed text.

```bash
screencastgen lipsync MyBook.pdf --ref-audio voice.wav --ref-video face.mp4
screencastgen lipsync MyBook.pdf --ref-audio voice.wav --ref-video face.mp4 --format mp4
screencastgen lipsync MyBook.pdf --ref-audio voice.wav --ref-video face.mp4 --format epub
```

The MP4 option bakes the document and presenter into one video. EPUB is a
secondary text-and-narration accessibility export: it intentionally omits the
presenter, and Media Overlay support varies between EPUB reading applications.
The offline reader ZIP is the portable format that preserves the complete
talking-head experience.

See [LatentSync Sidecar](INSTALLATION.md#latentsync-sidecar) for local setup.

### Highlight (`screencastgen highlight`)

PDF to synchronized video with word highlighting. For PDF inputs, the preferred path highlights words on the actual PDF page images using PyMuPDF word bounding boxes. For non-PDF inputs, or if PyMuPDF is unavailable, it falls back to a plain text-on-background renderer.

```bash
screencastgen highlight MyBook.pdf -o output.mp4
screencastgen highlight MyBook.pdf -o output.mp4 --aligner whisperx
```

### Audio (`screencastgen audio`)

Convert a document to a concatenated audio file. Qwen3-TTS runs locally by
default and supports voice cloning from a reference recording.

```bash
screencastgen audio MyBook.pdf --backend qwen --device cuda
screencastgen audio MyBook.pdf --backend qwen --model 1.7B --ref-audio voice.wav
```

## Provider Model

The runtime separates text-to-speech, alignment, and lip synchronization into
independently selectable provider layers.

| Layer     | Provider                   | Selection flag        | Purpose                                  |
| --------- | -------------------------- | --------------------- | ---------------------------------------- |
| TTS       | `qwen`                     | `--backend`           | Local speech generation and voice cloning |
| TTS       | `remote`                   | `--backend`           | Speech generation on a GPU server         |
| Alignment | `whisperx`                 | `--aligner`           | Word-level audio alignment                 |
| Lip-sync  | `latentsync` (`auto`)      | `--lipsync-provider`  | Audio-driven face animation                |

Remote deployments can offload TTS, alignment, and lip-sync inference to a GPU
host while document processing and media composition remain on the client. See
[Remote GPU Setup](INSTALLATION.md#remote-gpu-setup) for deployment commands,
[Inference Server](https://shashekhar.github.io/screencastgen/reference/core/inference-server/)
for the server API, and
[Remote GPU Client](https://shashekhar.github.io/screencastgen/reference/core/remote-gpu-client/)
for client behavior.

## Model Dependencies and References

The ML providers are maintained independently. Review their repositories, model
cards, licenses, and usage restrictions before distributing generated content or
deploying commercially.

| Component      | Used for                                    | Upstream resources                                                                                                                                                                    |
| -------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qwen3-TTS      | Default local TTS and voice cloning         | [GitHub](https://github.com/QwenLM/Qwen3-TTS), [0.6B model](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base), [1.7B model](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) |
| WhisperX       | Transcription and word-level alignment      | [GitHub](https://github.com/m-bain/whisperX)                                                                                                                                          |
| LatentSync 1.6 | Default diffusion-based lip synchronization | [GitHub](https://github.com/bytedance/LatentSync), [model weights](https://huggingface.co/ByteDance/LatentSync-1.6), [paper](https://arxiv.org/abs/2412.09262)                        |

This integration uses LatentSync's `latentsync_unet.pt` and Whisper `tiny.pt`
checkpoints. Upstream lists 18 GB as the minimum VRAM for LatentSync 1.6
inference and publishes its code under Apache 2.0. See the
[upstream README](https://github.com/bytedance/LatentSync) for current runtime
requirements and checkpoint details.

## CLI Options

```
Common options (all subcommands):
  pdf                     Path to the input PDF file
  -o, --output            Output filename
  --output-dir            Directory for chunk files (default: audio)
  --language              Language code (default: en-US)
  --status-file           Resume-state JSON file (default: processing_status.json)
  --clean                 Ignore previous state and start fresh
  -v, --verbose           Verbose output

TTS backend options (audio, highlight, lipsync):
  --backend               TTS backend: qwen, remote (default: qwen)
  --device                Device for local models: auto, cpu, cuda (default: auto)
  --voice                 Voice name (backend-specific)
  --model                 Model name/path (e.g. 0.6B, 1.7B for qwen)
  --ref-audio             Reference audio for voice cloning backends
  --ref-text              Transcript of reference audio
  --tts-server-url        URL of GPU inference server (for --backend remote)
  --aligner               Alignment provider (default: whisperx)

Video options (highlight, lipsync):
  --font-size             Font size (default: 32)
  --resolution            Video resolution WxH (default: 1280x720)
  --fps                   Frame rate (default: 24)
  --lipsync-provider      Lip-sync provider: auto, latentsync (default: auto)

Model download options:
  --backend               Backend whose models should be downloaded; repeat as needed
  --package               Downloadable package/model family to preload; repeat as needed
  --all                   Download all registered models/packages
  --model                 Backend-specific model selector (for qwen)

Environment diagnostics:
  screencastgen doctor --profile auto|local-gpu|remote-client|dev
  --model                 Qwen model whose cached weights should be checked
  --server-url            Remote GPU server whose /health endpoint should be checked
```

## How It Works

1. **Extract** text from every page of the PDF (PyPDF2)
2. **Preprocess** to fix common PDF artefacts (run-together words, missing spaces)
3. **Split** into sentences, breaking any that exceed the per-sentence byte limit
4. **Chunk** sentences into groups that fit within the backend's limit (backend-specific)
5. **Validate** every chunk before synthesis
6. **Synthesize** each chunk via the selected TTS backend, tracking progress in a JSON file
7. **Concatenate** all chunk files into a single output file (pydub or ffmpeg)

For highlight/lipsync pipelines, additional steps run after synthesis:

- **Align** audio with the selected alignment provider for word-level timestamps
- **PDF inputs**: extract PyMuPDF word bounding boxes, match aligned words back to page positions, and render highlighted PDF page images
- **Other inputs / fallback**: render highlighted text on a plain background
- **Lip-sync**: generate each page with the selected face animation provider, reporting per-page elapsed time, then build the final output

The lip-sync pipeline accepts a cooperative stop request from its host. With a
remote GPU, the page currently in progress is abandoned from the pipeline's
perspective; with local inference, cancellation is observed between pages. If at
least one page has completed, the final reader/video is built from that completed
prefix and result metadata records the completed and total page counts plus page
timings. Stopping before any page completes produces a failed run because there
is no usable output to build.

The remote GPU path preserves the same abstraction: the CPU-side client sends provider names to the server, and the server executes its configured default provider or an explicit per-request override.

The status file makes the process fully resumable -- if interrupted, re-run the same command and only unprocessed chunks will be re-synthesized.

## Web Application

Full-stack web UI wrapping all three pipelines. Stack: FastAPI + PostgreSQL + Celery/Redis + React/Tailwind.

See [Web Application Setup](INSTALLATION.md#web-application-setup) for Docker
and local-development instructions.

By default files are stored on the local filesystem. Set `P2A_STORAGE_BACKEND` to `gcs` or `s3` to store uploads and outputs in a cloud bucket. Pipelines always work against local directories; the storage layer handles downloading inputs and uploading outputs to the bucket.

### Lip-sync progress and stopping

The Job Detail page displays completed-page timings, a live timer for the page
currently generating, and total time spent. Completed timing data is persisted
with the job so it survives a browser reload; live events continue over SSE.

Selecting **Stop & build from completed pages** first opens an inline
confirmation warning to prevent accidental clicks. The user can either keep the
job running or confirm the stop. The worker stores the request in Redis, the
pipeline stops at the next supported cancellation point, and the output is built
from completed pages. A successfully shortened result is marked **Stopped early**
with its completed and total page counts.

The lip-sync setup screen also includes a reader-style preview. It uses the saved
reader theme and lets the presenter picture-in-picture be dragged within the
preview; the configured face position remains its initial placement.

New web jobs default to the **Talking-Head Reader** pipeline. Its primary
download is the standalone offline-reader ZIP; the reader header can also build
a baked MP4 or a text-and-narration EPUB on demand. Reference-audio uploads no
longer block on transcription: the worker transcribes the clip only when a job
actually consumes it and caches the result for retries and later exports.

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
