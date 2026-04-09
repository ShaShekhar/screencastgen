"""Celery application configuration."""

from celery import Celery
from celery.signals import worker_process_init

from ..config import settings
from ..logging_config import setup_logging


@worker_process_init.connect
def _init_worker_logging(**_kwargs):
    setup_logging("worker")


# Also configure for the master process so import-time errors are captured.
setup_logging("worker")

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
