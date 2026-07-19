"""Tests for bilingual (English/Nepali) advising: language detection, the
routing LLM client, prompt language instruction, and context-window budgeting."""

from __future__ import annotations

from unittest.mock import MagicMock

from drona.advising.engine import make_query
from drona.advising.prompt_builder import _format_citations, build_prompt
from drona.advising.router_client import LanguageRoutingClient
from drona.contracts import DataTier, RetrievalCitation
from drona.utils.language import detect_language, resolve_language

# ── Language detection ──────────────────────────────────────────────────────────

def test_detect_pure_english():
    assert detect_language("How do I become a backend engineer in Nepal?") == "en"


def test_detect_pure_nepali():
    assert detect_language("म ब्याकइन्ड इन्जिनियर कसरी बन्न सक्छु?") == "ne"


def test_detect_codeswitched_is_nepali():
    # Romanised Nepali with some Devanagari - a real student phrasing.
    assert detect_language("म backend engineer banna chahanchu, कसरी?") == "ne"


def test_detect_empty_defaults_english():
    assert detect_language("") == "en"


def test_resolve_language_forced():
    assert resolve_language("en", "म नेपाली") == "en"
    assert resolve_language("ne", "pure english") == "ne"
    assert resolve_language("auto", "म नेपाली हुँ") == "ne"
    assert resolve_language("auto", "pure english") == "en"


# ── Prompt language instruction ─────────────────────────────────────────────────

def _cit(excerpt: str, tier: str = "nepal") -> RetrievalCitation:
    return RetrievalCitation(
        source_type="curriculum", source_id="X", tier=DataTier(tier),
        excerpt=excerpt, relevance_score=0.9,
    )


def test_prompt_adds_nepali_instruction():
    q = make_query("म कसरी job पाउँछु?")
    sys_en, _ = build_prompt(q, [_cit("SQL and databases")], [], language="en")
    sys_ne, _ = build_prompt(q, [_cit("SQL and databases")], [], language="ne")
    assert "NEPALI" in sys_ne and "Devanagari" in sys_ne
    assert "NEPALI" not in sys_en
    # JSON keys must stay English in both (parsing is language-independent)
    assert "keys" in sys_ne.lower()


# ── Context-window budgeting ────────────────────────────────────────────────────

def test_citation_budget_trims_to_fit():
    cits = [_cit("X" * 500, "nepal") for _ in range(20)]  # ~10k chars total
    full = _format_citations(cits, char_budget=None)
    trimmed = _format_citations(cits, char_budget=1500)
    assert len(trimmed) < len(full)
    assert "omitted to fit context" in trimmed
    # at least the first citation always survives
    assert "[1]" in trimmed


def test_citation_budget_keeps_all_when_small():
    cits = [_cit("short", "nepal")]
    out = _format_citations(cits, char_budget=10000)
    assert "omitted" not in out
    assert "short" in out


# ── Routing client ──────────────────────────────────────────────────────────────

def test_router_english_uses_primary():
    primary = MagicMock()
    primary.is_available.return_value = True
    nepali = MagicMock()
    nepali.is_available.return_value = True
    r = LanguageRoutingClient(primary=primary, nepali=nepali)
    client, route = r.client_for_language("en")
    assert client is primary and route == "en"


def test_router_nepali_uses_nepali_model():
    primary = MagicMock()
    primary.is_available.return_value = True
    nepali = MagicMock()
    nepali.is_available.return_value = True
    r = LanguageRoutingClient(primary=primary, nepali=nepali)
    client, route = r.client_for_language("ne")
    assert client is nepali and route == "ne"


def test_router_nepali_falls_back_when_model_down():
    primary = MagicMock()
    primary.is_available.return_value = True
    nepali = MagicMock()
    nepali.is_available.return_value = False
    r = LanguageRoutingClient(primary=primary, nepali=nepali)
    client, route = r.client_for_language("ne")
    assert client is primary and route == "ne-fallback"


def test_router_generate_dispatches_by_query_language(monkeypatch):
    monkeypatch.setattr(
        "drona.advising.router_client.settings.advisor_language", "auto", raising=False
    )
    primary = MagicMock()
    primary.is_available.return_value = True
    primary.generate.return_value = ([], "hi", False, None)
    nepali = MagicMock()
    nepali.is_available.return_value = True
    nepali.generate.return_value = ([], "नमस्ते", False, None)
    r = LanguageRoutingClient(primary=primary, nepali=nepali)

    r.generate("s", "u", make_query("pure english question"), [], [])
    assert primary.generate.called and not nepali.generate.called

    primary.generate.reset_mock()

    nepali.generate.reset_mock()
    r.generate("s", "u", make_query("म कसरी पढ्ने?"), [], [])
    assert nepali.generate.called and not primary.generate.called
