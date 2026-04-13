"""Coalescing batcher that folds concurrent /synthesize requests into one forward pass.

The inference server receives individual ``/synthesize`` requests but wants to
feed Qwen3-TTS a list of texts so a single model call produces multiple audio
clips. ``BatchingSynthesizer`` holds a background worker thread that:

  1. Pops a pending request to seed a batch.
  2. Waits up to ``batch_window_ms`` to collect additional requests that share
     the same reference voice (the only cross-item constraint Qwen3-TTS imposes
     in voice-clone mode).
  3. Calls ``backend.synthesize_batch(...)`` once and resolves each queued
     future with its slice of the result.

Client-side request concurrency (``--tts-concurrency``) feeds this batcher;
the two together convert serial HTTP traffic into fat GPU batches.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import threading
import time
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, Deque, List, Optional

logger = logging.getLogger(__name__)


_NO_REF_KEY = "__no_ref__"


def _normalize_language(language: Optional[str]) -> str:
    return (language or "en-US").strip().lower()


def _batch_key(
    language: Optional[str],
    ref_audio_bytes: Optional[bytes],
    ref_text: Optional[str],
    ref_audio_suffix: Optional[str],
) -> str:
    lang_key = _normalize_language(language)
    if not ref_audio_bytes:
        return f"{lang_key}:{_NO_REF_KEY}"
    h = hashlib.sha1()
    h.update(ref_audio_bytes)
    h.update(b"\0")
    h.update((ref_text or "").encode("utf-8"))
    h.update(b"\0")
    h.update((ref_audio_suffix or ".wav").encode("utf-8"))
    return f"{lang_key}:{h.hexdigest()}"


@dataclass
class _QueueItem:
    text: str
    language: str
    batch_key: str
    ref_audio_bytes: Optional[bytes]
    ref_audio_suffix: Optional[str]
    ref_text: Optional[str]
    future: Future


class BatchingSynthesizer:
    """Background batcher that coalesces /synthesize requests into batched model calls."""

    def __init__(
        self,
        backend: Any,
        max_batch: int = 8,
        batch_window_ms: int = 30,
    ):
        self._backend = backend
        self._max_batch = max(1, int(max_batch))
        self._window_s = max(0.0, float(batch_window_ms) / 1000.0)

        self._queue: Deque[_QueueItem] = deque()
        self._cv = threading.Condition()
        self._stop = False
        self._worker: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = threading.Thread(
            target=self._run,
            name="tts-batcher",
            daemon=True,
        )
        self._worker.start()

    def stop(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(
        self,
        text: str,
        language: str,
        ref_audio_bytes: Optional[bytes],
        ref_audio_suffix: Optional[str],
        ref_text: Optional[str],
    ) -> Future:
        """Enqueue a single synthesis request and return a Future yielding audio bytes."""
        item = _QueueItem(
            text=text,
            language=language,
            batch_key=_batch_key(language, ref_audio_bytes, ref_text, ref_audio_suffix),
            ref_audio_bytes=ref_audio_bytes,
            ref_audio_suffix=ref_audio_suffix,
            ref_text=ref_text,
            future=Future(),
        )
        with self._cv:
            self._queue.append(item)
            self._cv.notify()
        return item.future

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while True:
            batch = self._collect_batch()
            if batch is None:
                return
            self._run_batch(batch)

    def _collect_batch(self) -> Optional[List[_QueueItem]]:
        """Block until work exists, then pop up to max_batch compatible items."""
        with self._cv:
            while not self._queue and not self._stop:
                self._cv.wait()
            if self._stop and not self._queue:
                return None

            first = self._queue.popleft()
            batch: List[_QueueItem] = [first]
            self._drain_compatible(batch, first.batch_key)

        if len(batch) >= self._max_batch or self._window_s == 0:
            return batch

        # Wait briefly to let more concurrent requests land, then take another pass.
        deadline = threading.Event()
        deadline.wait(self._window_s)

        with self._cv:
            self._drain_compatible(batch, first.batch_key)
        return batch

    def _drain_compatible(self, batch: List[_QueueItem], batch_key: str) -> None:
        """Pop items from the front of the queue that share *batch_key*."""
        while self._queue and len(batch) < self._max_batch:
            head = self._queue[0]
            if head.batch_key != batch_key:
                break
            batch.append(self._queue.popleft())

    def _run_batch(self, batch: List[_QueueItem]) -> None:
        """Materialize refs, call synthesize_batch, resolve futures."""
        ref_tmp_path: Optional[str] = None
        try:
            first = batch[0]
            if first.ref_audio_bytes:
                fd, ref_tmp_path = tempfile.mkstemp(
                    suffix=first.ref_audio_suffix or ".wav"
                )
                os.close(fd)
                with open(ref_tmp_path, "wb") as fh:
                    fh.write(first.ref_audio_bytes)

            texts = [it.text for it in batch]
            language = first.language
            ref_text = first.ref_text

            started = time.monotonic()
            logger.info(
                "synthesize_batch: size=%d ref=%s lang=%s",
                len(batch),
                "clone" if ref_tmp_path else "custom",
                language,
            )
            audio_list = self._backend.synthesize_batch(
                texts=texts,
                language=language,
                ref_audio_path=ref_tmp_path,
                ref_text=ref_text,
            )
            logger.info(
                "synthesize_batch: done size=%d elapsed=%.2fs",
                len(batch),
                time.monotonic() - started,
            )

            if len(audio_list) != len(batch):
                raise RuntimeError(
                    f"synthesize_batch returned {len(audio_list)} items for "
                    f"{len(batch)} inputs"
                )

            for item, audio in zip(batch, audio_list):
                item.future.set_result(audio)
        except Exception as exc:  # noqa: BLE001
            for item in batch:
                if not item.future.done():
                    item.future.set_exception(exc)
        finally:
            if ref_tmp_path and os.path.exists(ref_tmp_path):
                try:
                    os.unlink(ref_tmp_path)
                except OSError:
                    pass
