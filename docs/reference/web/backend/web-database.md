# Web Database

> Async and sync SQLAlchemy session factories.

**Source:** [`web/backend/database.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/database.py)

---

## Overview

Provides both **async** (for FastAPI request handlers) and **sync** (for Celery workers) SQLAlchemy session factories. Uses PostgreSQL via asyncpg.

---

## Exports

| Export | Type | Used By |
|--------|------|---------|
| `async_session_factory` | `async_sessionmaker` | FastAPI routers |
| `sync_session_factory` | `sessionmaker` | Celery tasks |
| `get_async_session()` | FastAPI Dependency | Router dependency injection |
| `get_sync_session()` | context manager | Celery task code |

---

## Why Two Factories?

- **Async** — FastAPI handlers are async; SQLAlchemy's async engine uses `asyncpg` for non-blocking DB calls
- **Sync** — Celery workers run in separate processes; they use standard synchronous SQLAlchemy

Both connect to the same PostgreSQL database via different connection strings from [Web Config](web-config.md).

---

## Dependencies

```
Web Database
├── SQLAlchemy (async + sync)
├── asyncpg
├── Web Config         (DATABASE_URL, SYNC_DATABASE_URL)
├── DB Models          (table definitions)
└──▶ consumed by FastAPI App (lifecycle)
     ├──▶ Uploads Router
     ├──▶ Jobs Router
     ├──▶ Events Router
     └──▶ Pipeline Tasks
```

---

## See Also

- [DB Models](db-models.md) — Table definitions
- [Web Config](web-config.md) — Connection strings
- [FastAPI App](fast-api-app.md) — Engine lifecycle management
