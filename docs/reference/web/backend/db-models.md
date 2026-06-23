# DB Models

> SQLAlchemy table definitions for uploads and jobs.

**Source:** [`web/backend/models.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/models.py)

---

## Enums

### `PipelineType`

```
audio | highlight | lipsync | visualization
```

### `JobStatus`

```
pending | running | completed | failed
```

---

## Tables

### `UploadedFile`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `original_name` | String | Original filename |
| `stored_path` | String | Storage key / relative path |
| `size_bytes` | Integer | File size |
| `content_type` | String | MIME type |
| `ref_text` | Text, nullable | Job-time transcript cache for uploaded reference audio |
| `created_at` | DateTime | Upload timestamp |

### `Job`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `pipeline_type` | PipelineType | Which pipeline to run |
| `status` | JobStatus | Current state |
| `progress_current` | Integer | Progress numerator |
| `progress_total` | Integer | Progress denominator |
| `progress_phase` | String | Current phase name |
| `error_message` | Text, nullable | Error details |
| `config_json` | JSONB | Full pipeline configuration |
| `uploaded_file_id` | UUID (FK) | Input document |
| `ref_audio_file_id` | UUID (FK), nullable | Reference audio |
| `ref_video_file_id` | UUID (FK), nullable | Reference video |
| `output_path` | String, nullable | Output filename/path |
| `celery_task_id` | String, nullable | Celery task ID |
| `created_at` | DateTime | Job creation time |
| `updated_at` | DateTime | Last update time |

### Relationships

```
Job ──FK──▶ UploadedFile (uploaded_file_id)
Job ──FK──▶ UploadedFile (ref_audio_file_id)
Job ──FK──▶ UploadedFile (ref_video_file_id)
```

---

## Dependencies

```
DB Models
├── SQLAlchemy
└──▶ consumed by Jobs Router
     ├──▶ Uploads Router
     ├──▶ Pipeline Tasks
     └──▶ Schemas
```

---

## See Also

- [Schemas](schemas.md) — Pydantic models that mirror these tables
- [Web Database](web-database.md) — Session factories
- [Jobs Router](jobs-router.md) — CRUD operations on `Job`
- [Uploads Router](uploads-router.md) — Creates `UploadedFile` records
