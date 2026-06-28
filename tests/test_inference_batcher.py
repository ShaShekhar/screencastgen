"""Tests for the GPU inference batcher."""

from __future__ import annotations

import threading
import time

from screencastgen.inference_batcher import BatchingSynthesizer


class _Backend:
    def __init__(self):
        self.calls = 0

    def synthesize_batch(self, **_kwargs):
        self.calls += 1
        return [b"audio"]


def test_batcher_honors_shared_run_lock():
    backend = _Backend()
    run_lock = threading.Lock()
    batcher = BatchingSynthesizer(
        backend=backend,
        max_batch=1,
        batch_window_ms=0,
        run_lock=run_lock,
    )
    batcher.start()

    run_lock.acquire()
    try:
        future = batcher.submit(
            text="hello",
            language="en-US",
            ref_audio_bytes=None,
            ref_audio_suffix=None,
            ref_text=None,
        )
        time.sleep(0.05)
        assert not future.done()
        assert backend.calls == 0
    finally:
        run_lock.release()

    assert future.result(timeout=1) == b"audio"
    assert backend.calls == 1
    batcher.stop()
