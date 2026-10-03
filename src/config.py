"""Paths and environment loading."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("TGOCR_DATA_DIR", BASE_DIR / "data"))
IMAGES_DIR = DATA_DIR / "matched_images"
LOGS_DIR = DATA_DIR / "logs"
EXPORT_DIR = DATA_DIR / "exports"
SESSION_PATH = DATA_DIR / "session"  # Telethon appends ".session"

DEFAULT_LANGS = "eng+heb"


def ensure_dirs() -> None:
    for d in (DATA_DIR, IMAGES_DIR, LOGS_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (KEY=VALUE). Existing environment variables win."""
    path = path or BASE_DIR / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)
