# Jobs Router

> Job CRUD operations and Celery task dispatch.

**Source:** [`web/backend/routers/jobs.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/routers/jobs.py)

---

## Endpoints

### `POST /api/jobs`
Create a job and dispatch it to the Celery worker.

**Request body:** [JobCreateRequest](schemas.md)

**Process:**
1. Validate uploaded file exists for document pipelines
2. Validate reference files exist (if provided)
3. Build `config_json` from request
4. Create [Job](db-models.md) record with `pending` status
5. Call `run_pipeline_task.delay(str(job.id))` → [Pipeline Tasks](pipeline-tasks.md)
6. Store `celery_task_id` on the job

**Response:** [JobResponse](schemas.md)

### `GET /api/jobs`
List jobs with optional filtering and pagination.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | `str` | `None` | Filter by status |
| `limit` | `int` | 20 | Results per page (1-100) |
| `offset` | `int` | 0 | Pagination offset |

**Response:** [JobListResponse](schemas.md)

### `GET /api/jobs/{job_id}`
Get a single job by ID.

**Response:** [JobResponse](schemas.md)

### `DELETE /api/jobs/{job_id}`
Delete a job and clean up its files.

**Process:**
1. Delete job record from database
2. Call [delete_job_files()](storage-service.md) to remove output directory

### `POST /api/jobs/{job_id}/stop`
Request an early stop for a running lip-sync job.

Validation:

- Returns `404` when the job does not exist.
- Returns `400` unless the job uses the lip-sync pipeline.
- Returns `400` unless the job is `pending` or `running`.

After validation, the endpoint writes `job:{id}:cancel` to Redis with a 24-hour
expiry and returns `{ "detail": "stop requested" }`. The worker polls this flag
via [Progress Reporter](progress-reporter.md) and, for remote GPU work, forwards cancellation to the
inference server. The frontend requires a separate inline confirmation before it
calls this endpoint; the API itself remains suitable for programmatic clients.

### `GET /api/jobs/{job_id}/download`
Download the job's output file. The response type depends on the configured [storage backend](storage-service.md):

- **Local:** `FileResponse` (direct file stream)
- **GCS/S3:** `RedirectResponse` to a time-limited signed URL

### `POST /api/jobs/{job_id}/export-mp4`
Trigger an on-demand baked MP4 export for a completed lip-sync reader job. The task stores export state in `job.config_json`:

- `export_status`: `running`, `done`, or `failed`
- `export_output`: output filename when complete
- `export_error`: error message when failed

### `GET /api/jobs/{job_id}/export-mp4/status`
Return current export state.

### `GET /api/jobs/{job_id}/export-mp4/download`
Download the exported composited MP4 when `export_status == "done"`.

### `POST /api/jobs/{job_id}/export-epub`
Trigger an on-demand text-and-narration EPUB export for a completed lip-sync
reader job. The presenter is intentionally omitted because EPUB reading systems
do not reliably synchronize video with Media Overlays. The task stores separate
state in `job.config_json`:

- `epub_export_status`: `running`, `done`, or `failed`
- `epub_export_output`: output filename when complete
- `epub_export_error`: error message when failed

### `GET /api/jobs/{job_id}/export-epub/status`
Return the current EPUB export state using the common `export_status`,
`export_output`, and `export_error` response keys.

### `GET /api/jobs/{job_id}/export-epub/download`
Download the exported EPUB when `epub_export_status == "done"`.

---

## Dependencies

```
Jobs Router
├── Web Database       (async session)
├── DB Models          (Job, JobStatus, UploadedFile)
├── Schemas            (JobCreateRequest, JobResponse, JobListResponse)
├── Storage Service    (delete_job_files, get_download_response)
└── Pipeline Tasks     (main, MP4-export, and EPUB-export tasks; lazy imports)
```

---

## See Also

- [Uploads Router](uploads-router.md) — Upload files referenced by jobs
- [Events Router](events-router.md) — SSE progress for running jobs
- [Pipeline Tasks](pipeline-tasks.md) — Celery task that runs the pipeline
- [Jobs API](../frontend/jobs-api.md) — Frontend client for these endpoints
