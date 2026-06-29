# Pipeline Tasks

> Celery task that constructs pipeline requests and runs pipelines.

**Source:** [`web/backend/tasks/pipelines.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/tasks/pipelines.py)

---

## Overview

This module bridges the web application and the core screencastgen pipelines. It reads job configuration from the database, resolves uploaded assets, constructs typed pipeline request objects, and runs the appropriate pipeline with a [Progress Reporter](progress-reporter.md).

---

## Task

### `run_pipeline_task(job_id: str)`

Main Celery task. Dispatched by [Jobs Router](jobs-router.md) when a job is created.

**Process:**
1. Load the [Job](db-models.md) record from the database.
2. Resolve the uploaded document path via [Storage Service](storage-service.md).
3. Create the local output directory.
4. Build a typed request object based on `pipeline_type`.
5. Create a [JobProgressReporter](progress-reporter.md) and pipeline reporter.
6. Run one of:
   - `audio` → [run_audio_pipeline()](../../pipelines/audio-pipeline.md)
   - `highlight` → [run_highlight_pipeline()](../../pipelines/highlight-pipeline.md)
   - `lipsync` → [run_lipsync_pipeline()](../../pipelines/lipsync-pipeline.md)
   - `visualization` → [run_visualization_pipeline()](../../pipelines/visualization-pipeline.md)
7. On success, call `upload_output()` for remote-storage backends.
8. Upload reader assets for highlight/lip-sync jobs and visualization source/metadata for visualization jobs.
9. Persist final job status and output path.

---

## Request Builders

### `_build_audio_request(job, pdf_path, output_dir)`

Builds `AudioPipelineRequest` from `config_json` and defaults.

Notable values:
- default backend is `remote`
- `tts_server_url` falls back to `settings.TTS_SERVER_URL`
- `tts_concurrency` falls back to `settings.TTS_CONCURRENCY`

### `_build_highlight_request(job, pdf_path, output_dir, db_session)`

Builds `HighlightPipelineRequest` and resolves voice inputs.

### `_resolve_highlight_voice(cfg, job, db_session)`

Voice resolution priority:
1. bundled voice via `voice_id`
2. uploaded reference audio via `ref_audio_file_id`
3. no explicit reference voice

When an uploaded reference audio file is used, the task reuses stored `UploadedFile.ref_text`
when available. Otherwise it calls `/transcribe` while processing the job and caches a
successful transcript for retries or later exports. If transcription returns no text,
request construction raises a clear error and the job is marked failed.

### `_build_lipsync_request(job, pdf_path, output_dir, db_session)`

Builds `LipsyncPipelineRequest`, resolving:
- optional reference audio path
- reference video path
- a cached transcript or an on-demand `/transcribe` call for uploaded reference audio
- `tts_concurrency`
- embedded reference-video audio extraction and transcription when no reference audio override is uploaded
- reader output defaults

### `_build_visualization_request(job, output_dir)`

Builds `VisualizationPipelineRequest` from `VisualizationConfig`. Visualization jobs do not require an uploaded document.

### `run_lipsync_epub_export_task(job_id: str)`

Re-runs a completed lip-sync job in `epub` mode against the existing output
directory. It reuses resumable synthesis and alignment state, writes a
text-and-narration EPUB without presenter video, uploads the result, and records
the independent `epub_export_*` state in `config_json`.

---

## Dependencies

```
Pipeline Tasks
├── Celery App              (task registration)
├── Progress Reporter       (JobProgressReporter)
├── Web Config              (TTS_SERVER_URL, TTS_CONCURRENCY)
├── Web Database            (sync session)
├── DB Models               (Job, JobStatus, UploadedFile)
├── Storage Service         (paths, upload_output)
├── Voices Service          (bundled voice resolution, lazy import)
├── Pipeline Types          (request dataclasses)
├── Audio Pipeline          (run_audio_pipeline)
├── Highlight Pipeline      (run_highlight_pipeline)
├── Lipsync Pipeline        (run_lipsync_pipeline)
├── Visualization Pipeline  (run_visualization_pipeline)
├── Aligner                 (get_default_alignment_provider)
├── Reader Assets           (reader asset upload names)
└── Transcribe Client       (on-demand reference audio transcription)
```

---

## See Also

- [Jobs Router](jobs-router.md) — Dispatches this task
- [Progress Reporter](progress-reporter.md) — Publishes progress events
- [Pipeline Overview](../../../concepts/pipelines.md) — How pipelines work
- [Celery App](celery-app.md) — Worker configuration
