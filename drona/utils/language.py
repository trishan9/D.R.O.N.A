"""
Language detection + helpers for D.R.O.N.A.'s bilingual (English/Nepali) advising.

Nepali is written in Devanagari (Unicode U+0900-U+097F). A query is treated as
Nepali when a meaningful share of its letters are Devanagari - this also catches
the common Romanised-plus-Devanagari code-switching Nepali students use ("mero
career kasari banaune, I want to do MSc abroad") by looking at letter ratio
rather than requiring a pure script.

Detection is deliberately cheap (no model, no network) so it runs inline in the
advising engine and on a Raspberry Pi.
"""

from __future__ import annotations

from typing import Literal

Language = Literal["en", "ne"]

# Devanagari block. We count letters only (ignore digits/punctuation/spaces).
_DEVANAGARI = range(0x0900, 0x0980)


def _is_devanagari(ch: str) -> bool:
    return ord(ch) in _DEVANAGARI


def devanagari_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are Devanagari (0..1)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(_is_devanagari(c) for c in letters) / len(letters)


def detect_language(text: str, threshold: float = 0.10) -> Language:
    """Return 'ne' if the text is (partly) Nepali/Devanagari, else 'en'.

    threshold is low on purpose: even a mostly-Romanised query with a couple of
    Devanagari words ("म backend engineer banna chahanchu, कसरी?") should be
    served in Nepali - code-switching is how Nepali students actually type. Pure
    English has ratio 0.0 and stays 'en'; a lone Devanagari name inside a long
    English sentence stays under the threshold and remains 'en'.
    """
    return "ne" if devanagari_ratio(text) >= threshold else "en"


def resolve_language(preference: str, query_text: str) -> Language:
    """Resolve the language to advise in.

    preference: 'en' | 'ne' force a language; 'auto' detects from the query.
    """
    pref = (preference or "auto").lower()
    if pref == "en":
        return "en"
    if pref == "ne":
        return "ne"
    return detect_language(query_text)


def language_name(lang: Language) -> str:
    return {"en": "English", "ne": "Nepali"}.get(lang, "English")
