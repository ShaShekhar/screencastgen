# Celery App

> Celery worker configuration.

**Source:** [`web/backend/tasks/celery_app.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/tasks/celery_app.py)

---

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Broker | Redis (from [Web Config](web-config.md)) | Task queue |
| Backend | Redis | Result storage |
| Serialization | JSON | Task/result format |
| Task tracking | Enabled | Track task state |
| Acks | Late | Acknowledge after completion |
| Timeout | 24 hours | Soft time limit |

### Worker Process Init
Sets up logging via [Web Logging](web-logging.md) when the worker process starts.

---

## Tasks

| Task | Module | Description |
|------|--------|-------------|
| `run_pipeline_task` | [Pipeline Tasks](pipeline-tasks.md) | Run a pipeline for a job |

---

## Usage

```bash
# Start worker
celery -A web.backend.tasks.celery_app:celery_app worker --loglevel=info

# Or via Makefile
cd web && make worker
```

---

## Dependencies

```
Celery App
├── Celery
├── Redis
├── Web Config         (REDIS_URL)
├── Web Logging        (setup_logging)
└──▶ hosts Pipeline Tasks
```

---

## See Also

- [Pipeline Tasks](pipeline-tasks.md) — The task this worker runs
- [Progress Reporter](progress-reporter.md) — Publishes progress from worker
- [Jobs Router](jobs-router.md) — Dispatches tasks to this worker
- [Docker Compose](../../configuration/docker-compose.md) — Worker container configuration
