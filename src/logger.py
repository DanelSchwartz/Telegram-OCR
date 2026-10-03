"""Single logging setup for the whole app."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from src.config import LOGS_DIR


def setup_logging(verbose: bool = False) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    file_handler = RotatingFileHandler(
        LOGS_DIR / "telegram_ocr.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(file_handler)
    root.addHandler(console)

    logging.getLogger("telethon").setLevel(logging.WARNING)
