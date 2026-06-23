# FastAPI App

> Application setup, middleware, lifespan, and router mounting.

**Source:** [`web/backend/main.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/main.py)

---

## Application

```python
app = FastAPI(title="screencastgen API", version="2.0.0")
```

### Lifespan Events

| Event | Action |
|-------|--------|
| Startup | Create database tables |
| Shutdown | Dispose database engine |

### Middleware

- **CORSMiddleware** — Configurable origins from [Settings.ALLOWED_ORIGINS](web-config.md)

### Routers (under `/api` prefix)

| Prefix | Router | Description |
|--------|--------|-------------|
| `/api/uploads` | [Uploads Router](uploads-router.md) | File upload |
| `/api/jobs` | [Jobs Router](jobs-router.md) | Job CRUD + dispatch |
| `/api/jobs/{id}/events` | [Events Router](events-router.md) | SSE progress |
| `/api/voices` | [Voices Router](voices-router.md) | Voice library |
| `/api/jobs/{id}/reader/...` | [Reader Router](reader-router.md) | Browser reader assets |

### Health Check

```
GET /api/health → {"status": "ok"}
```

---

## Dependencies

```
FastAPI App
├── FastAPI + uvicorn
├── Web Config         (Settings)
├── Web Database       (engine lifecycle)
├── Uploads Router
├── Jobs Router
├── Events Router
├── Voices Router
└── Reader Router
```

---

## See Also

- [Web Overview](../../../concepts/web-architecture.md) — Full web architecture
- [Web Config](web-config.md) — Environment settings
- [Web Database](web-database.md) — Database setup
