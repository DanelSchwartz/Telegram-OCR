"""Keyword matching against OCR text (tolerant to OCR noise, Hebrew-aware)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

_NIQQUD = re.compile(r"[\u0591-\u05C7]")
_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)
SHORT_KEYWORD_LEN = 4  # below this, require an exact whole-word match


@dataclass(frozen=True)
class Match:
    keyword: str
    score: float


def normalize(text: str) -> str:
    """NFKC, strip niqqud, casefold, collapse punctuation to single spaces."""
    text = unicodedata.normalize("NFKC", text)
    text = _NIQQUD.sub("", text).casefold()
    return _NON_WORD.sub(" ", text).strip()


def find_matches(text: str, keywords: list[str], threshold: float = 85) -> list[Match]:
    """Return matching keywords sorted by score (desc). Empty keywords are ignored."""
    norm_text = normalize(text)
    if not norm_text:
        return []
    padded = f" {norm_text} "
    matches: list[Match] = []
    for keyword in keywords:
        norm_kw = normalize(keyword)
        if not norm_kw:
            continue
        if len(norm_kw.replace(" ", "")) < SHORT_KEYWORD_LEN:
            if f" {norm_kw} " in padded:
                matches.append(Match(keyword, 100.0))
            continue
        score = 100.0 if norm_kw in norm_text else fuzz.partial_ratio(norm_kw, norm_text)
        if score >= threshold:
            matches.append(Match(keyword, round(float(score), 1)))
    return sorted(matches, key=lambda m: -m.score)
