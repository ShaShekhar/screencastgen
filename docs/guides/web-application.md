# Run the web application

The web UI wraps the pipelines with upload management, background Celery jobs,
live progress over server-sent events, and browser reader output.

## Docker Compose

From the repository root:

```bash
cd web
docker compose up --build
```

Open `http://localhost:5173`; the API is available at
`http://localhost:8000`.

## Local development

Start PostgreSQL and Redis, then run:

```bash
cd web
cp .env.example .env
make install
make migrate
```

Use separate terminals for `make backend`, `make worker`, and `make frontend`.
Configure the GPU server and storage backend in `web/.env` before starting the
services.

For component relationships and request flow, see
[Web architecture](../concepts/web-architecture.md). Backend and frontend module
details are under the [developer reference](../reference/index.md).
