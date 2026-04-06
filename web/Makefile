.PHONY: dev backend worker frontend migrate docker-up docker-down install

# --- Local development (requires PostgreSQL + Redis running locally) ---

install:
	pip install -e "../.[pydub]"
	pip install -r backend/requirements.txt
	cd frontend && npm install

backend:
	uvicorn web.backend.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A web.backend.tasks.celery_app:celery_app worker --loglevel=info --concurrency=1

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && alembic upgrade head

dev:
	@echo "Run these in separate terminals:"
	@echo "  make backend"
	@echo "  make worker"
	@echo "  make frontend"

# --- Docker ---

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
