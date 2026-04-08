"""Structured pipeline progress events."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, Optional, TextIO


@dataclass
class PipelineEvent:
    """Structured progress update emitted by the pipeline layer."""

    status: str = "running"
    phase: str = "starting"
    current: int = 0
    total: int = 0
    message: str = ""


EventCallback = Callable[[PipelineEvent], None]


class PipelineReporter:
    """Bridge console logging and structured progress callbacks."""

    def __init__(
        self,
        *,
        stream: Optional[TextIO] = None,
        on_event: Optional[EventCallback] = None,
    ):
        self.stream = stream if stream is not None else sys.stdout
        self.on_event = on_event
        self.phase = "starting"
        self.current = 0
        self.total = 0

    def line(self, message: str) -> None:
        """Write a human-readable line to the configured stream."""
        if self.stream is not None:
            print(message, file=self.stream)

    def emit(
        self,
        *,
        phase: Optional[str] = None,
        current: Optional[int] = None,
        total: Optional[int] = None,
        message: str = "",
        status: str = "running",
    ) -> PipelineEvent:
        """Publish a structured event, updating retained progress state."""
        if phase is not None:
            self.phase = phase
        if current is not None:
            self.current = current
        if total is not None:
            self.total = total

        event = PipelineEvent(
            status=status,
            phase=self.phase,
            current=self.current,
            total=self.total,
            message=message,
        )
        if self.on_event is not None:
            self.on_event(event)
        return event

    def phase_start(self, phase: str, message: str) -> None:
        """Announce a new pipeline phase."""
        self.line(message)
        self.emit(phase=phase)
