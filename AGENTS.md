# Repository Guidelines

## Project Structure & Module Organization
`screencastgen/` contains the Python package and CLI pipelines. Core entry points live in `screencastgen/cli.py` and `screencastgen/__main__.py`; pluggable runtime implementations live under `screencastgen/providers/` (`tts/`, `align/`, `lipsync/`); document, audio, alignment, and video helpers are split across focused modules such as `extractor.py`, `aligner.py`, and `video_composer.py`.

`web/` holds the full-stack UI. `web/backend/` is a FastAPI app with Alembic migrations, routers, services, and Celery tasks. `web/frontend/` is a Vite + React + TypeScript SPA; pages live in `src/pages/`, shared UI in `src/components/`, and HTTP clients in `src/api/`.

Cross-platform environment management lives in `scripts/setup.py`, while non-mutating runtime diagnostics live in `screencastgen/doctor.py`. Keep installation workflows in `INSTALLATION.md`; keep `README.md` focused on product usage and link to the installation guide instead of duplicating setup instructions.

## Build, Test, and Development Commands
Use the managed setup from the repository root:

```bash
python3 scripts/setup.py --check
python3 scripts/setup.py --profile auto
source .venv/bin/activate
```

On Windows PowerShell, use `py scripts/setup.py` and activate with `.venv\Scripts\Activate.ps1`. The `auto` profile selects `local-gpu` on Linux or WSL2 when `nvidia-smi` can access an NVIDIA GPU; otherwise it selects `remote-client`. Native Windows and macOS do not support the local CUDA stack. Use `--profile dev` for development without local GPU models. See `INSTALLATION.md` for manual extras, model downloads, LatentSync, remote GPU, and web setup.

Validate the active environment without changing it:

```bash
screencastgen doctor --profile auto
screencastgen doctor --profile local-gpu --model 1.7B
screencastgen doctor --profile remote-client --server-url http://gpu-vm:8100
screencastgen doctor --profile dev
```

`doctor` returns nonzero when a required check fails. Warnings, such as omitting `--server-url` for a remote client, do not fail the command. Keep setup and doctor profile resolution consistent when adding platforms or capabilities.

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
Tests live in `tests/` and use pytest. Run the smallest relevant test module first, then the complete suite when practical:

```bash
python -m pytest tests/test_setup_and_doctor.py -q
python -m pytest -q
```

For setup or diagnostic changes, test profile selection, platform rejection, non-mutating `--check` behavior, exit codes, and remote-server capability validation. Preserve deferred imports for optional ML dependencies so tests, help text, and `doctor` can run without loading large models.

Also run the relevant manual check: the CLI command you changed, `npm run build` in `web/frontend/` for frontend changes, and backend startup via `make backend` for API changes. Do not require GPU model downloads in ordinary unit tests; mock platform, executable, cache, and network detection instead.

## Commit & Pull Request Guidelines
Git history currently uses short imperative subjects, for example `Initial commit: screencastgen project`. Keep commit titles concise and action-oriented.

PRs should explain the user-visible change, list verification steps, note any new environment variables or model requirements, and include screenshots for frontend work. Call out changes that affect resumable processing, Celery jobs, or the remote GPU server contract.
