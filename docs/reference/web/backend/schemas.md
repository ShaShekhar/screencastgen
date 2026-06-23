# Schemas

> Pydantic request and response models for the REST API.

**Source:** [`web/backend/schemas.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/schemas.py)

---

## Config Sub-Models

### `AudioConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backend` | `str` | `"remote"` | TTS backend |
| `language` | `str` | `"en-US"` | TTS language |
| `tts_server_url` | `str \| None` | `None` | Remote GPU server URL override |
| `aligner` | `str` | `"whisperx"` | Alignment provider |

### `HighlightConfig`

Extends `AudioConfig`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | `str` | `"epub"` | Output format: `epub` or `mp4` |
| `voice_id` | `str \| None` | `None` | Bundled voice ID |
| `ref_audio_file_id` | `UUID \| None` | `None` | Uploaded reference audio |
| `ref_text` | `str \| None` | `None` | Reference transcript override |
| `font_size` | `int` | `32` | Text font size |
| `width` | `int` | `1280` | Video width |
| `height` | `int` | `720` | Video height |
| `fps` | `int` | `24` | Frames per second |

Validation rules:
- `voice_id` and `ref_audio_file_id` are mutually exclusive
- `format` must be `epub` or `mp4`

### `LipsyncConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ref_audio_file_id` | `UUID \| None` | `None` | Optional reference audio override |
| `ref_video_file_id` | `UUID` | required | Reference video upload |
| `backend` | `str` | `"remote"` | TTS backend |
| `aligner` | `str` | `"whisperx"` | Alignment provider |
| `face_position` | `str` | `"bottom-right"` | Face overlay position |
| `face_scale` | `float` | `0.22` | Face overlay scale |
| `latentsync_preset` | `str` | `"quality"` | Quality preset |
| `font_size` | `int` | `32` | Subtitle font size |
| `width` | `int` | `1280` | Video width |
| `height` | `int` | `720` | Video height |
| `fps` | `int` | `24` | Frames per second |
| `format` | `str` | `"reader"` | `reader`, `mp4`, or `epub` |

Validation rules:
- `format` must be `reader`, `mp4`, or `epub`

### `VisualizationConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | `str` | required | Concept prompt, 1-4000 chars |
| `provider` | `str` | `"manimgl"` | Renderer provider: `manimgl` or `manimce` |
| `duration_seconds` | `int` | `30` | 3-600 seconds |
| `width` | `int` | `1280` | 320-3840 |
| `height` | `int` | `720` | 240-2160 |
| `fps` | `int` | `24` | 1-60 |
| `style` | `str` | `"clean"` | `clean`, `chalkboard`, `blueprint`, or `minimal` |
| `audience_level` | `str` | `"general"` | Labeling hint passed into generated scene |
| `iteration_of_job_id` | `UUID \| None` | `None` | Optional prior visualization job reference |

---

## Request Models

### `JobCreateRequest`

| Field | Type | Description |
|-------|------|-------------|
| `pipeline_type` | `str` | `audio`, `highlight`, `lipsync`, or `visualization` |
| `uploaded_file_id` | `UUID \| None` | Input document upload ID; not required for visualization |
| `audio_config` | `AudioConfig \| None` | Config for audio jobs |
| `highlight_config` | `HighlightConfig \| None` | Config for highlight jobs |
| `lipsync_config` | `LipsyncConfig \| None` | Config for lipsync jobs |
| `visualization_config` | `VisualizationConfig \| None` | Config for visualization jobs |

---

## Response Models

### `UploadResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `UUID` | Uploaded file ID |
| `original_name` | `str` | Original filename |
| `size_bytes` | `int` | File size |
| `content_type` | `str` | MIME type |

### `JobResponse`

Mirrors the [Job](db-models.md) table and uses `from_attributes=True`.

### `JobListResponse`

| Field | Type |
|-------|------|
| `jobs` | `list[JobResponse]` |
| `total` | `int` |

### `ProgressEvent`

| Field | Type |
|-------|------|
| `job_id` | `str` |
| `status` | `str` |
| `phase` | `str` |
| `current` | `int` |
| `total` | `int` |
| `message` | `str` |

Note: the SSE payload published by [Progress Reporter](progress-reporter.md) may include an additional `data` object for lip-sync page progress. That field is not part of this Pydantic response model.

---

## Dependencies

```
Schemas
├── Pydantic
├── DB Models      (mirrors persisted structures)
└──▶ consumed by Jobs Router
     ├──▶ Uploads Router
     └──▶ Events Router
```

---

## See Also

- [DB Models](db-models.md) — Database tables these mirror
- [Pipeline Types](../../pipelines/pipeline-types.md) — Core pipeline request types these map into
- [Jobs Router](jobs-router.md) — Uses these for request validation
