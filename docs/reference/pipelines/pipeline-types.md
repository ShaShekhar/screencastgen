# Pipeline Types

> Request and result dataclasses for pipeline invocation.

**Source:** [`screencastgen/pipelines/types.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/pipelines/types.py)

---

## Request Hierarchy

```
BasePipelineRequest
    └── TTSRequest
        ├── AudioPipelineRequest
        ├── HighlightPipelineRequest
        └── LipsyncPipelineRequest

VisualizationPipelineRequest
RenderedVisualClip
```

### `BasePipelineRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pdf` | `str` | — | Input document path |
| `output` | `str` | `None` | Output filename |
| `output_dir` | `str` | `"audio"` | Output directory |
| `language` | `str` | `"en-US"` | Language code |
| `status_file` | `str` | `None` | Tracker JSON path |
| `clean` | `bool` | `False` | Clear previous state |
| `verbose` | `bool` | `False` | Verbose output |

### `TTSRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backend` | `str` | `"qwen"` | TTS backend name |
| `device` | `str` | `"auto"` | Compute device |
| `voice` | `str` | `None` | Voice identifier |
| `model` | `str` | `None` | Model name or size |
| `ref_audio` | `str` | `None` | Reference audio for cloning |
| `ref_text` | `str` | `None` | Reference transcript |
| `tts_server_url` | `str` | `None` | Remote TTS server URL |
| `aligner` | `str` | `"whisperx"` | Alignment provider |
| `tts_concurrency` | `int` | `1` | Number of chunks to synthesize in parallel |

### `AudioPipelineRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `no_concat` | `bool` | `False` | Skip concatenation step |

### `HighlightPipelineRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | `str` | `"epub"` | Output format: `epub` or `mp4` |
| `font_size` | `int` | `32` | Text font size |
| `resolution` | `str` | `"1280x720"` | Video resolution |
| `fps` | `int` | `24` | Frames per second |

### `LipsyncPipelineRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | `str` | `"reader"` | Output format: `reader`, `mp4`, or `epub` |
| `ref_video` | `str` | — | Reference face video |
| `lipsync_provider` | `str` | `"auto"` | Lip-sync provider |
| `face_position` | `str` | `"bottom-right"` | Presenter position |
| `face_scale` | `float` | `0.22` | Presenter scale for docked corner layouts |
| `latentsync_preset` | `str` | `"quality"` | Quality preset |

`reader` builds hosted assets and a standalone offline ZIP. The `epub` option is a text-and-narration accessibility export without presenter video.

### `VisualizationPipelineRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | `str` | — | Concept prompt to visualize |
| `output` | `str \| None` | `None` | MP4 filename, default `visualization.mp4` |
| `output_dir` | `str` | `"audio"` | Directory for source, metadata, and render output |
| `provider` | `str` | `"manimgl"` | Renderer provider: `manimgl` or `manimce` |
| `duration_seconds` | `int` | `30` | Target animation duration |
| `resolution` | `str` | `"1280x720"` | Render resolution |
| `fps` | `int` | `24` | Frames per second |
| `style` | `str` | `"clean"` | `clean`, `chalkboard`, `blueprint`, or `minimal` |
| `audience_level` | `str` | `"general"` | Labeling hint for generated scene |
| `iteration_of_job_id` | `str \| None` | `None` | Optional reference to a prior visualization job |
| `timeout_seconds` | `int` | `300` | Renderer subprocess timeout |
| `max_output_bytes` | `int` | `512 MiB` | Output size guardrail |

### `RenderedVisualClip`

Metadata describing a rendered visualization clip: path, duration, fps, dimensions, source prompt, and generated source code.

---

## Result

### `PipelineRunResult`

| Field | Type | Description |
|-------|------|-------------|
| `exit_code` | `int` | `0` means success |
| `output_name` | `str` | Output filename |
| `output_path` | `str` | Full output path |
| `error_message` | `str` | Error description when failed |
| `metadata` | `dict` | Pipeline-specific metadata stored by web jobs |

---

## Utility Function

### `coerce_request(request_type, value)`

Converts an `argparse.Namespace` or dict into the requested dataclass type. Used by both [CLI](../core/cli.md) and [Pipeline Tasks](../web/backend/pipeline-tasks.md).

---

## Dependencies

```
Pipeline Types
├── dataclasses (stdlib)
└──▶ consumed by Audio Pipeline
     ├──▶ Highlight Pipeline
     ├──▶ Lipsync Pipeline
     ├──▶ Visualization Pipeline
     ├──▶ CLI
     └──▶ Pipeline Tasks
```

---

## See Also

- [Types](../core/types.md) — Core data structures such as `WordTiming` and `AlignedChunk`
- [Schemas](../web/backend/schemas.md) — Web API request/response models that map into these
- [Pipeline Overview](../../concepts/pipelines.md) — How requests flow through pipelines
