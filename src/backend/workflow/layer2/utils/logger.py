"""
utils/logger.py — Centralized logger for Layer 2
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from config import LOG_DIR

os.makedirs(LOG_DIR, exist_ok=True)

_LOG_FILE = os.path.join(LOG_DIR, "run.log")
_FMT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=_FMT,
    datefmt=_DATE_FMT,
    handlers=[
        RotatingFileHandler(_LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
