"""
Logging: console + rotating file in logs/.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import settings

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

_FORMATTER = logging.Formatter(
    fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_FORMATTER)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        LOGS_DIR / "bot.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(_FORMATTER)
    logger.addHandler(file_handler)

    return logger
