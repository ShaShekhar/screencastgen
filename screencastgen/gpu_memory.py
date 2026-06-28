"""Best-effort GPU memory cleanup helpers."""

from __future__ import annotations

import gc
import logging

logger = logging.getLogger(__name__)


def release_torch_cuda_cache() -> None:
    """Release unreachable Python objects and cached PyTorch CUDA blocks."""
    gc.collect()
    try:
        import torch
    except ImportError:
        return

    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except RuntimeError as exc:
        logger.debug("CUDA cache cleanup failed: %s", exc)
