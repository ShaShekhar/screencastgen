"""Celery application configuration."""

from celery import Celery

from ..config import settings

celery_app = Celery(
    "screencastgen_web",
    include=["web.backend.tasks.pipelines"],
)

celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    # Long timeout for GPU-heavy tasks
    visibility_timeout=86400,
)
