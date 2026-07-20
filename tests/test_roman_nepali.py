"""
Language routing for code-switched (Romanised) Nepali.

Most Nepali students type Nepali in Latin script, which contains no Devanagari
and therefore scored 0.0 on the script-ratio test and was served in English.
These tests pin both directions, because the failure modes are not symmetric:

  MISS  (Nepali served in English)  - bad, the student gets the wrong language.
  FALSE POSITIVE (English served in Nepali) - worse. A student who asked in
        English and gets a Nepali answer will assume the system is broken.

So the English cases below matter more than the Nepali ones, and the detector is
tuned to be conservative.
"""

from __future__ import annotations

import pytest

from drona.utils.language import (
    detect_language,
    is_roman_nepali,
    resolve_language,
    roman_nepali_markers,
)

# ── Romanised Nepali that MUST route to the Nepali model ─────────────────────

ROMAN_NEPALI = [
    "malai data science ramro lagcha, kun module ramro cha?",
    "mero career kasari banaune?",
    "ma dosro barsa ma chu, kun elective liney?",
    "kasari ma software engineer banna sakchu?",
    "cybersecurity padhne ki data science padhne?",
    "malai thaha chaina kun bato ramro cha",
    "ma lai job chahiyo, kasari apply garne?",
    "AI ko lagi kun module haru ramro cha?",
    "mero saathi le MBA garyo, ma pani garnu parcha?",
    "kati semester samma project garnu parcha?",
]


@pytest.mark.parametrize("text", ROMAN_NEPALI)
def test_romanised_nepali_routes_to_nepali(text: str):
    assert detect_language(text) == "ne", (
        f"{text!r} is Romanised Nepali but routed to English "
        f"(markers found: {roman_nepali_markers(text)})"
    )


# ── English that MUST STAY English (the expensive failure) ───────────────────

ENGLISH = [
    "Which modules prepare me for data engineering?",
    "What career paths are available for BSc Computing graduates in Nepal?",
    "How is the final year project assessed?",
    "Compare software engineering and ethical hacking outcomes.",
    "I want to work at Google, what is the roadmap?",
    "Does the programme include an industry placement or internship credit?",
    "What programming languages are used across the AI modules?",
    "My friend got a job in Australia so I should do the same, right?",
    # Contains 'ke' as part of nothing, and 'a'/'the' - must not trip the lexicon.
    "Can I take the machine learning elective in year three?",
    "What skills do I need for a data analyst role in Kathmandu?",
    # Deliberately adversarial: English words that resemble Romanised Nepali.
    "The cat sat on a mat in the sun.",
    "Please can you make a plan for my next semester?",
]


@pytest.mark.parametrize("text", ENGLISH)
def test_english_stays_english(text: str):
    assert detect_language(text) == "en", (
        f"{text!r} is English but routed to Nepali "
        f"(markers matched: {roman_nepali_markers(text)})"
    )


# ── Devanagari still works, and mixes still work ─────────────────────────────


def test_devanagari_still_detected():
    assert detect_language("मलाई डाटा साइन्स मन पर्छ") == "ne"


def test_devanagari_mixed_with_english_detected():
    assert detect_language("म backend engineer banna chahanchu, कसरी?") == "ne"


def test_romanised_mixed_with_english_nouns():
    """The realistic case: Nepali grammar carrying English technical nouns."""
    assert detect_language("malai machine learning ra cloud computing ramro lagcha") == "ne"


# ── Threshold behaviour ──────────────────────────────────────────────────────


def test_single_marker_in_long_english_sentence_does_not_flip():
    """One stray token is more likely a name or loanword than a language switch."""
    text = "I would like to know whether the ke module covers advanced databases"
    assert len(roman_nepali_markers(text)) == 1
    assert detect_language(text) == "en"


def test_single_marker_in_short_query_does_flip():
    assert is_roman_nepali("kasari?")
    assert detect_language("kasari?") == "ne"


def test_empty_and_symbol_only_are_english():
    assert detect_language("") == "en"
    assert detect_language("???  !!") == "en"


# ── Explicit preference still overrides detection ────────────────────────────


def test_explicit_preference_beats_detection():
    assert resolve_language("en", "malai data science ramro lagcha") == "en"
    assert resolve_language("ne", "Which modules prepare me for data engineering?") == "ne"
    assert resolve_language("auto", "malai data science ramro lagcha") == "ne"


# ── Frontend / backend parity ────────────────────────────────────────────────
#
# The browser shows the student which language is about to be used, so if the two
# implementations disagree the UI lies about what the server will do. The TS
# lexicon is generated from the Python one; these tests fail if they drift.


def _ts_source() -> str:
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "frontend" / "lib" / "language.ts"
    return p.read_text(encoding="utf-8")


def test_frontend_marker_lexicon_matches_backend():
    import re as _re

    from drona.utils.language import _ROMAN_NEPALI_MARKERS

    src = _ts_source()
    block = _re.search(r"ROMAN_NEPALI_MARKERS = new Set\(\[(.*?)\]\)", src, _re.DOTALL)
    assert block, "could not find the marker set in frontend/lib/language.ts"
    ts_words = set(_re.findall(r'"([a-z]+)"', block.group(1)))
    assert ts_words == set(_ROMAN_NEPALI_MARKERS), (
        "frontend and backend Romanised-Nepali lexicons have drifted; "
        f"only in TS: {sorted(ts_words - set(_ROMAN_NEPALI_MARKERS))}, "
        f"only in PY: {sorted(set(_ROMAN_NEPALI_MARKERS) - ts_words)}"
    )


def test_frontend_thresholds_match_backend():
    import re as _re

    from drona.utils.language import _ROMAN_MIN_MARKERS, _ROMAN_SHORT_QUERY_TOKENS

    src = _ts_source()
    mn = _re.search(r"ROMAN_MIN_MARKERS = (\d+)", src)
    sq = _re.search(r"ROMAN_SHORT_QUERY_TOKENS = (\d+)", src)
    assert mn and sq, "thresholds not found in frontend/lib/language.ts"
    assert int(mn.group(1)) == _ROMAN_MIN_MARKERS
    assert int(sq.group(1)) == _ROMAN_SHORT_QUERY_TOKENS
