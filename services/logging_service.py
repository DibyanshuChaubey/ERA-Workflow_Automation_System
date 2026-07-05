"""Run logging helpers."""

from __future__ import annotations

import logging
from pathlib import Path


def create_run_logger(log_file: Path) -> logging.Logger:
    """Create a dedicated logger for a single application run."""

    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"CampaignSuppressionManager.{log_file.stem}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)

    return logger
