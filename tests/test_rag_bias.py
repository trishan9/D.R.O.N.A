"""
Tests for the span-grounding filter that gives the RAG bias detector its
precision.

These run in CI without a served model: the grounding check and the reply parser
are pure functions, and the detector itself is exercised with a stub client. The
end-to-end quality number comes from scripts/benchmark_bias_detectors.py, which
needs a real model and is not part of CI.
"""

from __future__ import annotations

from drona.advising.rag_bias import (
    RAGBiasDetector,
    _parse_flags,
    span_is_grounded,
)


class _StubClient:
    """Returns a canned reply, so parsing and filtering are tested in isolation."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, prompt: str, **_kwargs) -> str:
        self.prompts.append(prompt)
        return self.reply


# ── span grounding ───────────────────────────────────────────────────────────


def test_verbatim_span_is_grounded():
    q = "Google or nothing for me. What is the roadmap to get there?"
    assert span_is_grounded("Google or nothing", q)


def test_span_grounding_ignores_case_and_spacing():
    q = "I  want at  least Rs 200000 per month."
    assert span_is_grounded("at least rs 200000", q)


def test_invented_span_is_rejected():
    """The failure this filter exists to catch: a quote that is not in the text."""
    q = "Which semester covers operating systems?"
    assert not span_is_grounded("my friend got a job at Google", q)


def test_empty_span_is_rejected():
    assert not span_is_grounded("", "Which semester covers operating systems?")
    assert not span_is_grounded("   ", "Which semester covers operating systems?")


def test_lightly_reworded_span_survives():
    """Models paraphrase quotes; a mostly-overlapping quote is still evidence."""
    q = "I have already spent three years on this path, changing now is too late."
    assert span_is_grounded("already spent three years", q)


def test_whole_question_quote_is_rejected():
    """The loophole that made substring-only grounding useless.

    Every false positive observed on held-out v2 quoted the entire question as
    its evidence. That passes a substring check trivially, so coverage is capped:
    pointing at everything is not pointing at anything.
    """
    q = "Compare the typical career outcomes for software engineering and ethical hacking."
    assert not span_is_grounded(q, q)
    assert not span_is_grounded("म दोस्रो वर्षमा छु। कुन electives उपलब्ध छन्?",
                                "म दोस्रो वर्षमा छु। कुन electives उपलब्ध छन्?")


def test_short_genuine_span_still_grounded_in_long_question():
    q = ("I have been telling recruiters I am a Java developer for two years, "
         "so switching now feels dishonest to me.")
    assert span_is_grounded("switching now feels dishonest", q)


def test_devanagari_span_is_grounded():
    q = "मलाई खाली Kathmandu मै काम गर्न मन छ, अरू ठाउँ सोच्दिनँ।"
    assert span_is_grounded("खाली Kathmandu मै", q)
    assert not span_is_grounded("मेरो साथीले भन्यो", q)


# ── reply parsing ────────────────────────────────────────────────────────────


def test_parse_flags_extracts_pairs():
    raw = '[{"bias": "anchoring", "evidence": "Google or nothing"}]'
    assert _parse_flags(raw) == [("anchoring", "Google or nothing")]


def test_parse_flags_tolerates_surrounding_prose():
    raw = 'Sure! Here is the answer:\n[{"bias": "confirmation", "evidence": "right?"}]\nDone.'
    assert _parse_flags(raw) == [("confirmation", "right?")]


def test_parse_flags_drops_unknown_bias_types():
    raw = '[{"bias": "made_up_bias", "evidence": "x"}, {"bias": "anchoring", "evidence": "y"}]'
    assert _parse_flags(raw) == [("anchoring", "y")]


def test_parse_flags_on_neutral_and_garbage():
    assert _parse_flags("[]") == []
    assert _parse_flags("") == []
    assert _parse_flags("no json here") == []


# ── detector behaviour ───────────────────────────────────────────────────────


def test_ungrounded_flag_is_dropped_by_detector():
    """A hallucinated bias on a neutral question must not reach the student."""
    query = "Which semester covers operating systems?"
    stub = _StubClient('[{"bias": "availability_heuristic", "evidence": "my senior said"}]')
    det = RAGBiasDetector(client=stub)
    det._pool, det._pool_matrix = [], None  # noqa: SLF001
    det._neighbours = lambda _q: []  # type: ignore[method-assign]  # noqa: SLF001
    assert det.detect(query) == []


def test_grounded_flag_is_kept_with_its_span():
    query = "Google or nothing for me. What is the roadmap?"
    stub = _StubClient('[{"bias": "anchoring", "evidence": "Google or nothing"}]')
    det = RAGBiasDetector(client=stub)
    det._neighbours = lambda _q: []  # type: ignore[method-assign]  # noqa: SLF001
    flags = det.detect(query)
    assert [f.bias_type for f in flags] == ["anchoring"]
    # The span is carried through to the student-facing explanation.
    assert "Google or nothing" in flags[0].detected_signal
    assert flags[0].mitigation_applied


def test_grounding_can_be_disabled_for_ablation():
    query = "Which semester covers operating systems?"
    stub = _StubClient('[{"bias": "anchoring", "evidence": "not in the text"}]')
    det = RAGBiasDetector(client=stub, require_grounding=False)
    det._neighbours = lambda _q: []  # type: ignore[method-assign]  # noqa: SLF001
    assert [f.bias_type for f in det.detect(query)] == ["anchoring"]


def test_detector_falls_back_to_rules_when_model_fails():
    """Losing bias detection silently would be worse than being slow."""

    class _Broken:
        def complete(self, *_a, **_k):
            raise RuntimeError("model down")

    det = RAGBiasDetector(client=_Broken())
    det._neighbours = lambda _q: []  # type: ignore[method-assign]  # noqa: SLF001
    # A query the regex layer definitely catches.
    flags = det.detect("My friend got a job at Google so I should do the same, right?")
    assert flags, "expected the rule-based fallback to still produce flags"


def test_empty_query_short_circuits():
    det = RAGBiasDetector(client=_StubClient("[]"))
    assert det.detect("   ") == []
