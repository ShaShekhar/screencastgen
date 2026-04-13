"""Centralized logging setup for screencastgen entry points.

Writes a rotating log file under ``logs/`` (relative to the process CWD)
and also streams to the console so tmux scrollback still works. Mirrors
the setup used by the web backend/worker for consistency.
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
        Short identifier used for the log filename, e.g. ``"inference_server"``.
        The file is written to ``logs/<name>.log``.
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
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _CONFIGURED.add(name)
    logging.getLogger(name).info("Logging initialized -> %s", log_path)
    return logging.getLogger(name)
