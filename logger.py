"""Centralized logging configuration for the funding MVP pipeline."""

import logging
import logging.handlers
from pathlib import Path


def get_logger(module_name: str) -> logging.Logger:
    """Get or create a logger for a specific module.

    Format: timestamp | level | module | message
    Console: INFO level
    File: DEBUG level (logs/app.log)
    """
    logger = logging.getLogger(module_name)

    # Only configure if not already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (DEBUG level)
    log_file = Path("logs") / "app.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
