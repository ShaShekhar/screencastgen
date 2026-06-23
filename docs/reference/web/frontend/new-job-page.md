# NewJob Page

> Upload document, configure pipeline, and submit job.

**Source:** [`web/frontend/src/pages/NewJob.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/pages/NewJob.tsx)
**Route:** `/jobs/new`

---

## Features

1. **Upload document** — PDF, TXT, or EPUB via [FileUploader](file-uploader.md) for document pipelines
2. **Select pipeline** — highlight, lipsync, or visualization via [PipelineSelector](pipeline-selector.md)
3. **Configure voice** — Bundled or custom via [VoiceSettings](voice-settings.md) (highlight) or [LipsyncSettings](lipsync-settings.md) (lipsync)
4. **Configure video** — Resolution, FPS, font size via [VideoSettings](video-settings.md)
5. **Configure prompt rendering** — Prompt, renderer, style, audience, resolution, FPS, and duration for visualization
6. **Preview lip-sync reader layout** — [LipsyncPreviewFrame](lipsync-preview-frame.md) shows the document with a draggable presenter before submission
7. **Submit** — Create job and navigate to [JobDetail Page](job-detail-page.md)

---

## State

| State | Type | Description |
|-------|------|-------------|
| `pipeline` | `PipelineType` | Selected pipeline (default: `"lipsync"`) |
| `uploadedFile` | `UploadedFile \| null` | Uploaded document |
| `highlightConfig` | `HighlightConfig` | Highlight pipeline config |
| `lipsyncConfig` | `LipsyncConfig` | Lipsync pipeline config |
| `visualizationConfig` | `VisualizationConfig` | Prompt-to-animation config |
| `submitting` | `boolean` | Submit in progress |
| `error` | `string \| null` | Error message |

---

## Default Configs

### Highlight
```
language: "en-US", format: "epub"
voice_id: null, ref_audio_file_id: null, width: 1280, height: 720
```

### Lipsync
```
ref_audio_file_id: null, ref_video_file_id: ""
format: "reader" (applied by the API default)
face_position: "bottom-right"
face_scale: 0.22, latentsync_preset: "quality"
font_size: 32, width: 1280, height: 720, fps: 24
```

### Visualization
```
prompt: "", provider: "manimgl", duration_seconds: 30
width: 1280, height: 720, fps: 24
style: "clean", audience_level: "general"
```

---

## Submit Validation

- Document must be uploaded for audio/highlight/lipsync
- For lipsync: `ref_video_file_id` is required; reference audio is optional
- For visualization: prompt must be non-empty

---

## API Calls

- `createJob(request)` from [Jobs API](jobs-api.md)

---

## Components Used

- [FileUploader](file-uploader.md) — Document upload
- [PipelineSelector](pipeline-selector.md) — Pipeline choice
- [VoiceSettings](voice-settings.md) — Voice configuration (highlight mode)
- [LipsyncSettings](lipsync-settings.md) — Full lipsync configuration
- [LipsyncPreviewFrame](lipsync-preview-frame.md) — Reader-layout preview for lip-sync jobs
- [VideoSettings](video-settings.md) — Video settings

---

## See Also

- [Jobs API](jobs-api.md) — createJob endpoint
- [Dashboard Page](dashboard-page.md) — Job listing
- [JobDetail Page](job-detail-page.md) — After submission
