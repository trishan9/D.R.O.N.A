"""
Language detection + helpers for D.R.O.N.A.'s bilingual (English/Nepali) advising.

Two signals, because Nepali students write Nepali two different ways.

1. DEVANAGARI SCRIPT (U+0900-U+097F). A query is Nepali when a meaningful share
   of its letters are Devanagari.

2. ROMANISED NEPALI. This is the common case in practice - most students type
   Nepali in Latin script on a phone or laptop keyboard ("malai data science
   ramro lagcha, kun module ramro?"). That text contains ZERO Devanagari, so a
   script-ratio test scores it 0.0 and routes it to the English model. The
   previous implementation documented itself as handling code-switching but only
   did so when at least one Devanagari character was present; pure Romanised
   Nepali was silently served in English.

   Romanised Nepali is detected from a lexicon of high-frequency function words
   (pronouns, copulas, postpositions, question words) that are unambiguous
   against English. Content words are deliberately excluded - they are exactly
   where Nepali and English collide, and a false positive is worse than a miss
   here: answering an English question in Nepali is far more jarring to a student
   than the reverse.

Detection is deliberately cheap (no model, no network) so it runs inline in the
advising engine and on a Raspberry Pi.
"""

from __future__ import annotations

import re
from typing import Literal

Language = Literal["en", "ne"]

# Devanagari block. We count letters only (ignore digits/punctuation/spaces).
_DEVANAGARI = range(0x0900, 0x0980)

# High-frequency Romanised Nepali function words.
#
# Curated for NON-COLLISION with English, which is the whole difficulty. Words
# like "man", "bat", "sake", "chin", "gar", "pan", "kata" are real Romanised
# Nepali but are also English words or common English substrings, so they are
# excluded - including them makes ordinary English questions detect as Nepali.
# Function words are used rather than content words because a code-switched
# sentence keeps its Nepali grammar while borrowing English nouns:
# "malai data science ramro lagcha" is grammatically Nepali throughout.
_ROMAN_NEPALI_MARKERS = frozenset({
    # pronouns / person
    "ma", "malai", "mero", "mera", "hami", "hamro", "timi", "timro", "tapai",
    "tapailai", "usko", "uslai", "hamilai", "mailey", "maile",
    # copulas / auxiliaries
    "cha", "chha", "chan", "chhan", "chu", "chhu", "chau", "hoina", "hunna",
    "huncha", "hunchha", "thiyo", "thie", "bhayo", "bhaeko", "bhanne", "bhaneko",
    "hunu", "garnu", "garna", "garne", "gareko", "garchu", "garchha", "garcha",
    # question words
    "kasari", "kina", "kun", "kati", "kaha", "kahile", "ke", "kasto", "kasle",
    # postpositions / connectives (unambiguous ones only)
    "lai", "bata", "sanga", "samma", "bhanda", "lagi", "pachi", "agadi",
    "ani", "tara", "athawa", "pani", "matra", "athava",
    # very common adjectives/adverbs in student questions
    "ramro", "naramro", "dherai", "thorai", "ahile", "aile", "abo", "aba",
    "sakchu", "sakcha", "sakchha", "chahanchu", "chahanchhu", "parcha",
    "parchha", "padhne", "padhai", "padhchu", "banna", "banne", "bhaye",
    "jagir", "sikne", "sikchu", "herne", "herchu", "milcha", "milchha",
})

# Two independent markers, or one in a very short query. A single marker inside a
# long English sentence is more likely a name or a loanword than a language
# switch, so it is not enough on its own.
_ROMAN_MIN_MARKERS = 2
_ROMAN_SHORT_QUERY_TOKENS = 6


def _is_devanagari(ch: str) -> bool:
    return ord(ch) in _DEVANAGARI


def devanagari_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are Devanagari (0..1)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(_is_devanagari(c) for c in letters) / len(letters)


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^A-Za-z]+", text.lower()) if t]


def roman_nepali_markers(text: str) -> list[str]:
    """Which Romanised-Nepali function words appear (diagnostics + tests)."""
    return [t for t in _tokens(text) if t in _ROMAN_NEPALI_MARKERS]


def is_roman_nepali(text: str) -> bool:
    """True if Latin-script text looks like Nepali rather than English.

    Requires two markers, or one in a short query, so a stray token inside an
    otherwise English sentence does not flip the language.
    """
    toks = _tokens(text)
    if not toks:
        return False
    hits = [t for t in toks if t in _ROMAN_NEPALI_MARKERS]
    if len(hits) >= _ROMAN_MIN_MARKERS:
        return True
    return bool(hits) and len(toks) <= _ROMAN_SHORT_QUERY_TOKENS


def detect_language(text: str, threshold: float = 0.10) -> Language:
    """Return 'ne' if the text is (partly) Nepali/Devanagari, else 'en'.

    threshold is low on purpose: even a mostly-Romanised query with a couple of
    Devanagari words ("म backend engineer banna chahanchu, कसरी?") should be
    served in Nepali - code-switching is how Nepali students actually type. Pure
    English has ratio 0.0 and stays 'en'; a lone Devanagari name inside a long
    English sentence stays under the threshold and remains 'en'.
    """
    if devanagari_ratio(text) >= threshold:
        return "ne"
    # No Devanagari - the query may still be Nepali typed in Latin script, which
    # is how most students actually write it.
    return "ne" if is_roman_nepali(text) else "en"


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
