# Audio Pipeline

> Extract → chunk → synthesize → concatenate into a single audio file.

**Source:** [`screencastgen/pipelines/audio.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/pipelines/audio.py)

---

## Function

### `run_audio_pipeline(request, reporter, backend_factory) -> PipelineRunResult`

**Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `request` | `AudioPipelineRequest` ([Pipeline Types](pipeline-types.md)) | Pipeline configuration |
| `reporter` | `PipelineReporter` ([Pipeline Events](pipeline-events.md)) | Progress output |
| `backend_factory` | callable (optional) | Override for backend creation |

**Returns:** [PipelineRunResult](pipeline-types.md) with `exit_code`, `output_name`, `output_path`

---

## Steps

```
1. Create TTS backend       ← TTS Registry
2. Extract and chunk         ← Pipeline Common → Extractor + Text Processing
3. Validate chunks           ← Pipeline Common
4. Synthesize audio chunks   ← Pipeline Common → TTSBackend.synthesize()
5. Concatenate               ← Concatenator (unless --no-concat)
```

---

## Configuration

Key fields from [AudioPipelineRequest](pipeline-types.md):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pdf` | `str` | — | Input document path |
| `backend` | `str` | `"qwen"` | TTS backend name |
| `device` | `str` | `"auto"` | Compute device |
| `no_concat` | `bool` | `False` | Skip concatenation |
| `output_dir` | `str` | `"audio"` | Output directory |
| `clean` | `bool` | `False` | Clear previous state |

---

## Dependencies

```
Audio Pipeline
├── Pipeline Common   (extract, validate, synthesize)
├── Pipeline Events   (PipelineReporter)
├── Pipeline Types    (AudioPipelineRequest, PipelineRunResult)
├── Concatenator      (merge audio files)
└── TTS Registry      (create backend)
```

---

## See Also

- [Pipeline Overview](../../concepts/pipelines.md) — Shared pipeline design
- [Highlight Pipeline](highlight-pipeline.md) — Extends audio with alignment + video
- [Data Flow](../../concepts/data-flow.md) — Audio pipeline flow diagram
