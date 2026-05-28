from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def configure_logging(storage_root: Path) -> Path:
    """Configure console + rotating file logging under storage/logs/."""
    global _CONFIGURED

    log_dir = storage_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if _CONFIGURED:
        return log_dir

    level_name = os.environ.get("VIDEOMAKER_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(level)

    api_log = RotatingFileHandler(
        log_dir / "api.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    api_log.setFormatter(formatter)
    api_log.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(api_log)

    worker_log = RotatingFileHandler(
        log_dir / "worker.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    worker_log.setFormatter(formatter)
    worker_log.setLevel(level)

    worker_logger = logging.getLogger("videomaker.worker")
    worker_logger.setLevel(level)
    worker_logger.propagate = True
    worker_logger.addHandler(worker_log)

    logging.getLogger("uvicorn.access").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)

    _CONFIGURED = True
    return log_dir
