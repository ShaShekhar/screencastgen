"""Progress publishing for structured pipeline events."""

from __future__ import annotations

import json
import uuid

import redis

from screencastgen.pipelines.events import PipelineEvent

from ..config import settings


class JobProgressReporter:
    """Persist and publish structured pipeline progress for a job."""

    def __init__(self, job_id: str, db_session):
        self.job_id = job_id
        self.db_session = db_session
        self._redis = redis.Redis.from_url(settings.REDIS_URL)

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
                self.db_session.commit()
        except Exception:
            pass

        try:
            self._redis.publish(
                f"job:{self.job_id}:progress",
                json.dumps(
                    {
                        "job_id": self.job_id,
                        "status": event.status,
                        "phase": event.phase,
                        "current": event.current,
                        "total": event.total,
                        "message": event.message,
                    }
                ),
            )
        except Exception:
            pass

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
            pass
