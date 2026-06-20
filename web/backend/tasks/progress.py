"""Progress publishing for structured pipeline events."""

from __future__ import annotations

import json
import logging
import uuid

import redis

from screencastgen.pipelines.events import PipelineEvent

from ..config import settings

logger = logging.getLogger(__name__)


class JobProgressReporter:
    """Persist and publish structured pipeline progress for a job."""

    def __init__(self, job_id: str, db_session):
        self.job_id = job_id
        self.db_session = db_session
        self._redis = redis.Redis.from_url(settings.REDIS_URL)

    @property
    def _cancel_key(self) -> str:
        return f"job:{self.job_id}:cancel"

    def is_cancelled(self) -> bool:
        """Return True once a stop has been requested for this job."""
        try:
            return self._redis.get(self._cancel_key) is not None
        except Exception:
            logger.exception("Failed to read cancel flag for job %s", self.job_id)
            return False

    def clear_cancel(self) -> None:
        """Drop any stale stop request so a later re-run isn't cancelled."""
        try:
            self._redis.delete(self._cancel_key)
        except Exception:
            logger.exception("Failed to clear cancel flag for job %s", self.job_id)

    def handle_event(self, event: PipelineEvent) -> None:
        """Update DB state and publish a progress event."""
        from ..models import Job

        try:
            job_uuid = uuid.UUID(self.job_id) if isinstance(self.job_id, str) else self.job_id
            job = self.db_session.get(Job, job_uuid)
            if job:
                job.progress_current = event.current
                job.progress_total = event.total
                job.progress_phase = event.phase
                # Persist per-page lip-sync timing so a browser reload mid-run
                # still shows the pages completed so far.
                if event.data and event.data.get("event") == "page_done":
                    cfg = dict(job.config_json or {})
                    cfg["lipsync_progress"] = event.data
                    job.config_json = cfg
                self.db_session.commit()
        except Exception:
            logger.exception("Failed to persist progress for job %s", self.job_id)
            try:
                self.db_session.rollback()
            except Exception:
                logger.exception("Rollback failed for job %s", self.job_id)

        payload = {
            "job_id": self.job_id,
            "status": event.status,
            "phase": event.phase,
            "current": event.current,
            "total": event.total,
            "message": event.message,
            "data": event.data,
        }
        logger.info("progress %s", payload)
        try:
            self._redis.publish(
                f"job:{self.job_id}:progress",
                json.dumps(payload),
            )
        except Exception:
            logger.exception(
                "Failed to publish progress to Redis for job %s", self.job_id
            )

    def publish_terminal(self, *, status: str, phase: str, current: int, total: int, message: str = "") -> None:
        """Publish a terminal event after the pipeline exits."""
        self.handle_event(
            PipelineEvent(
                status=status,
                phase=phase,
                current=current,
                total=total,
                message=message,
            )
        )

    def close(self):
        try:
            self._redis.close()
        except Exception:
            logger.exception("Failed to close Redis client for job %s", self.job_id)
