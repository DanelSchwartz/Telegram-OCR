"""OCR helpers: Tesseract discovery, in-memory image variants, text extraction."""
from __future__ import annotations

import io
import logging
import os
import shutil
from pathlib import Path
from typing import Callable

import pytesseract
from PIL import Image, ImageEnhance, ImageOps, ImageStat

try:  # optional extra variant
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None
    np = None

log = logging.getLogger(__name__)

_WINDOWS_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)
MAX_SIDE = 2600
MIN_SIDE = 1000
DARK_THRESHOLD = 110


class TesseractError(RuntimeError):
    pass


def configure_tesseract(explicit: str | None = None) -> str:
    """Locate the tesseract binary (arg, $TESSERACT_CMD, PATH, common Windows paths)."""
    candidates = [explicit, os.getenv("TESSERACT_CMD"), shutil.which("tesseract"), *_WINDOWS_PATHS]
    for cand in candidates:
        if cand and Path(cand).is_file():
            pytesseract.pytesseract.tesseract_cmd = str(cand)
            log.info("Using Tesseract: %s", cand)
            return str(cand)
    raise TesseractError(
        "Tesseract not found. Install it (Windows: https://github.com/UB-Mannheim/tesseract/wiki, "
        "Linux: apt install tesseract-ocr, macOS: brew install tesseract) "
        "or pass --tesseract-cmd / set TESSERACT_CMD."
    )


def resolve_languages(requested: str) -> str:
    """Keep only languages that are actually installed; fail if none are."""
    wanted = [lang for lang in requested.split("+") if lang]
    available = set(pytesseract.get_languages(config=""))
    usable = [lang for lang in wanted if lang in available]
    missing = [lang for lang in wanted if lang not in available]
    if missing:
        log.warning(
            "Missing Tesseract language data for: %s (Linux: apt install %s)",
            ", ".join(missing), " ".join(f"tesseract-ocr-{m}" for m in missing),
        )
    if not usable:
        raise TesseractError(f"None of the requested OCR languages are installed: {requested}")
    return "+".join(usable)


def _normalize_size(gray: Image.Image) -> Image.Image:
    w, h = gray.size
    longest = max(w, h)
    if longest > MAX_SIDE:
        scale = MAX_SIDE / longest
    elif longest < MIN_SIDE:
        scale = min(3.0, MIN_SIDE / longest)
    else:
        return gray
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return gray.resize(new_size, Image.Resampling.LANCZOS)


def build_variants(img: Image.Image) -> list[Image.Image]:
    """In-memory preprocessing variants, ordered cheapest/most-likely first."""
    img = ImageOps.exif_transpose(img)
    gray = _normalize_size(img.convert("L"))
    variants = [
        gray,
        ImageEnhance.Contrast(gray).enhance(2.0),
        ImageEnhance.Sharpness(gray).enhance(2.0),
    ]
    if ImageStat.Stat(gray).mean[0] < DARK_THRESHOLD:  # dark-mode screenshots
        inverted = ImageOps.invert(gray)
        variants.append(inverted)
        variants.append(ImageEnhance.Contrast(inverted).enhance(2.0))
    if cv2 is not None:
        arr = cv2.medianBlur(np.asarray(gray), 3)
        thr = cv2.adaptiveThreshold(
            arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
        )
        variants.append(Image.fromarray(thr))
    return variants


def ocr_texts(
    data: bytes, langs: str, stop_when: Callable[[str], bool] | None = None
) -> list[str]:
    """OCR the image bytes across variants. Blocking - call via asyncio.to_thread.

    If stop_when is given, stops at the first variant whose text satisfies it
    (big speed-up: usually one OCR pass is enough for a match).
    """
    with Image.open(io.BytesIO(data)) as img:
        variants = build_variants(img)

    texts: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        try:
            text = pytesseract.image_to_string(variant, lang=langs).strip()
        except pytesseract.TesseractError as exc:
            log.warning("Tesseract failed on a variant: %s", exc)
            continue
        if not text or text in seen:
            continue
        seen.add(text)
        texts.append(text)
        if stop_when and stop_when(text):
            break
    return texts
