# Web Makefile

> Development targets for the web application.

**Source:** [`web/Makefile`](https://github.com/ShaShekhar/screencastgen/blob/main/web/Makefile)

---

## Targets

| Target | Command | Description |
|--------|---------|-------------|
| `make install` | pip install + npm install | Install all dependencies |
| `make backend` | `uvicorn web.backend.main:app --reload` | Start FastAPI dev server (port 8000) |
| `make worker` | `celery -A ... worker --loglevel=info` | Start Celery worker |
| `make frontend` | `npm run dev` (Vite) | Start React dev server (port 5173) |
| `make migrate` | `alembic upgrade head` | Run database migrations |
| `make dev` | — | Print instructions for 3-terminal setup |
| `make docker-up` | `docker compose up --build` | Build and start all containers |
| `make docker-down` | `docker compose down -v` | Stop and remove volumes |

---

## Local Dev Setup

```bash
cd web
cp .env.example .env     # Configure DB, Redis, TTS server URLs
make install              # Install deps
make migrate              # Run migrations

# Then in 3 terminals:
make backend              # Terminal 1
make worker               # Terminal 2
make frontend             # Terminal 3
```

---

## See Also

- [Web Overview](../../concepts/web-architecture.md) — Web architecture
- [Docker Compose](docker-compose.md) — Container alternative
- [Web Config](../web/backend/web-config.md) — Environment settings
