# Docker Compose

> Container orchestration for the full web stack.

**Source:** [`web/docker-compose.yml`](https://github.com/ShaShekhar/screencastgen/blob/main/web/docker-compose.yml)

---

## Services

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| `postgres` | `postgres:16-alpine` | 5432 | Database |
| `redis` | `redis:7-alpine` | 6379 | Celery broker + pubsub |
| `backend` | Built from `web/` | 8000 | [FastAPI App](../web/backend/fast-api-app.md) |
| `worker` | Built from `web/` | — | [Celery App](../web/backend/celery-app.md) worker |
| `frontend` | Built from `web/frontend/` | 5173 | React dev server |

---

## Environment Variables

| Variable | Value | Used By |
|----------|-------|---------|
| `P2A_DATABASE_URL` | `postgresql+asyncpg://...` | [Web Database](../web/backend/web-database.md) (async) |
| `P2A_SYNC_DATABASE_URL` | `postgresql://...` | [Web Database](../web/backend/web-database.md) (sync) |
| `P2A_REDIS_URL` | `redis://redis:6379/0` | [Celery App](../web/backend/celery-app.md), [Events Router](../web/backend/events-router.md) |
| `P2A_UPLOAD_DIR` | `/data/uploads` | [Storage Service](../web/backend/storage-service.md) |
| `P2A_OUTPUT_DIR` | `/data/outputs` | [Storage Service](../web/backend/storage-service.md) |
| `P2A_ALLOWED_ORIGINS` | `["http://localhost:5173", ...]` | [FastAPI App](../web/backend/fast-api-app.md) CORS |

---

## Volumes

- `pgdata` — PostgreSQL data persistence
- `redisdata` — Redis data persistence
- `/data` — Shared between backend and worker for uploads/outputs

---

## Usage

```bash
cd web
docker compose up --build         # Start all services
docker compose down -v            # Stop and remove volumes
```

---

## See Also

- [Web Overview](../../concepts/web-architecture.md) — Full web architecture
- [Web Config](../web/backend/web-config.md) — Settings these env vars configure
- [Web Makefile](web-makefile.md) — Local dev alternative
