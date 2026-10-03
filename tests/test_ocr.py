import io
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from src.ocr import build_variants


def test_build_variants_without_tesseract():
    img = Image.new("RGB", (400, 200), "black")  # dark -> inverted variants included
    variants = build_variants(img)
    assert len(variants) >= 5
    assert all(v.mode == "L" for v in variants[:3])
    assert max(variants[0].size) >= 1000  # small images get upscaled


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_end_to_end_ocr_english():
    from src.ocr import configure_tesseract, ocr_texts, resolve_languages

    configure_tesseract()
    langs = resolve_languages("eng")
    img = Image.new("RGB", (900, 200), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 64)
    except OSError:
        font = ImageFont.load_default()
    d.text((20, 50), "Secret Password 1234", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    texts = ocr_texts(buf.getvalue(), langs)
    assert any("password" in t.lower() for t in texts)
