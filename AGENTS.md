# Repository Guidelines

## Project Structure & Module Organization
`screencastgen/` contains the Python package and CLI pipelines. Core entry points live in `screencastgen/cli.py` and `screencastgen/__main__.py`; pluggable runtime implementations live under `screencastgen/providers/` (`tts/`, `align/`, `lipsync/`); document, audio, alignment, and video helpers are split across focused modules such as `extractor.py`, `aligner.py`, and `video_composer.py`.

`web/` holds the full-stack UI. `web/backend/` is a FastAPI app with Alembic migrations, routers, services, and Celery tasks. `web/frontend/` is a Vite + React + TypeScript SPA; pages live in `src/pages/`, shared UI in `src/components/`, and HTTP clients in `src/api/`.

## Build, Test, and Development Commands
Install the package from the repo root:

```bash
pip install -e .
pip install -e ".[highlight]"   # adds video pipeline deps
pip install -e ".[all]"         # full local stack
```

Run the CLI locally with `screencastgen audio book.pdf` or `python -m screencastgen highlight book.pdf`.

For the web app:

```bash
cd web
make install
make migrate
make backend
make worker
make frontend
docker compose up --build
```

Use `docker compose` for the full local stack; use the `make` targets for backend/frontend development against local PostgreSQL and Redis.

## Coding Style & Naming Conventions
Follow existing style: 4-space indentation in Python, 2-space indentation in frontend TypeScript/TSX, `snake_case` for Python functions/modules, and `PascalCase` for React components such as `JobDetail.tsx`. Keep modules focused and prefer descriptive filenames over large utility files.

This repo does not currently ship formatter or linter configs. Match surrounding code closely. Preserve deferred imports for heavy optional ML dependencies so help text and lightweight installs continue to work.

## Testing Guidelines
There is no committed automated test suite yet. Before opening a PR, run the smallest relevant manual check: the CLI command you changed, `npm run build` in `web/frontend/`, and backend startup via `make backend` for API changes. Add new tests alongside the feature when introducing test infrastructure.

## Commit & Pull Request Guidelines
Git history currently uses short imperative subjects, for example `Initial commit: screencastgen project`. Keep commit titles concise and action-oriented.

PRs should explain the user-visible change, list verification steps, note any new environment variables or model requirements, and include screenshots for frontend work. Call out changes that affect resumable processing, Celery jobs, or the remote GPU server contract.
