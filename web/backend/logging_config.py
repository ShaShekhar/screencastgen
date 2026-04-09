"""Centralized logging setup for backend and worker processes.

Writes rotating log files under ``logs/`` (relative to the process CWD,
typically ``web/``) and also streams to the console so tmux scrollback
still works.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


_CONFIGURED: set[str] = set()


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure root logging once per process.

    Parameters
    ----------
    name:
        Short identifier used for the log filename, e.g. ``"backend"`` or
        ``"worker"``. The file is written to ``logs/<name>.log``.
    level:
        Root log level. Defaults to ``INFO``.
    """
    if name in _CONFIGURED:
        return logging.getLogger(name)

    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", f"{name}.log")

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if uvicorn/celery have already attached some.
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _CONFIGURED.add(name)
    logging.getLogger(name).info("Logging initialized -> %s", log_path)
    return logging.getLogger(name)
