"""ProgressBridge: intercepts stdout from screencastgen pipelines to update job progress."""

import io
import json
import re
import uuid

import redis

from ..config import settings


class ProgressBridge(io.TextIOBase):
    """Wraps sys.stdout during pipeline execution.

    Parses progress lines emitted by screencastgen's print() calls and:
    - Updates the Job row via a sync SQLAlchemy session
    - Publishes events to Redis pubsub for the SSE endpoint
    """

    CHUNK_PROGRESS_RE = re.compile(r"(?:Processing|Synthesizing) chunk (\d+)/(\d+)")
    ALIGN_RE = re.compile(r"Aligning chunk (\d+)")
    LIPSYNC_RE = re.compile(r"Generating lip-sync for chunk (\d+)")
    CREATED_CHUNKS_RE = re.compile(r"Created (\d+) chunks")

    PHASE_PATTERNS = {
        "Extracting text": "extracting",
        "Preprocessing text": "preprocessing",
        "Splitting into sentences": "splitting",
        "Creating chunks": "chunking",
        "Validating chunks": "validating",
        "Initializing": "initializing",
        "ALIGNMENT": "aligning",
        "RENDERING VIDEO": "rendering",
        "LIP-SYNC GENERATION": "lipsync",
        "COMPOSING FINAL VIDEO": "composing",
        "Concatenating": "concatenating",
    }

    def __init__(self, job_id: str, db_session, fallback_stdout=None):
        self.job_id = job_id
        self.db_session = db_session
        self.fallback = fallback_stdout
        self.captured_errors: list[str] = []
        self._redis = redis.Redis.from_url(settings.REDIS_URL)
        self._current_phase = "starting"
        self._current = 0
        self._total = 0

    def write(self, text: str) -> int:
        if self.fallback:
            self.fallback.write(text)

        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            self._parse_line(line)

        return len(text)

    def flush(self):
        if self.fallback:
            self.fallback.flush()

    def _parse_line(self, line: str):
        if line.startswith("Error"):
            self.captured_errors.append(line)

        # Check for phase changes
        for pattern, phase in self.PHASE_PATTERNS.items():
            if pattern in line:
                self._current_phase = phase
                self._publish()
                return

        # Check chunk progress
        m = self.CHUNK_PROGRESS_RE.search(line)
        if m:
            self._current = int(m.group(1))
            self._total = int(m.group(2))
            self._publish()
            return

        # Total chunks created
        m = self.CREATED_CHUNKS_RE.search(line)
        if m:
            self._total = int(m.group(1))
            self._publish()
            return

        # Alignment progress
        m = self.ALIGN_RE.search(line)
        if m:
            self._current = int(m.group(1))
            self._current_phase = "aligning"
            self._publish()
            return

        # Lipsync progress
        m = self.LIPSYNC_RE.search(line)
        if m:
            self._current = int(m.group(1))
            self._current_phase = "lipsync"
            self._publish()
            return

    def _publish(self):
        """Update DB and publish to Redis pubsub."""
        from ..models import Job

        try:
            job_uuid = uuid.UUID(self.job_id) if isinstance(self.job_id, str) else self.job_id
            job = self.db_session.get(Job, job_uuid)
            if job:
                job.progress_current = self._current
                job.progress_total = self._total
                job.progress_phase = self._current_phase
                self.db_session.commit()
        except Exception:
            pass

        event = json.dumps({
            "job_id": self.job_id,
            "status": "running",
            "phase": self._current_phase,
            "current": self._current,
            "total": self._total,
            "message": "",
        })
        try:
            self._redis.publish(f"job:{self.job_id}:progress", event)
        except Exception:
            pass

    def close(self):
        try:
            self._redis.close()
        except Exception:
            pass
