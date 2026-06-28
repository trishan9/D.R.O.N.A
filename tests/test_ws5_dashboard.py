"""
WS5 smoke tests - dashboard session bridge and component helpers.

No Streamlit server, no browser, no Ollama. The AdvisingEngine is mocked so
only the bridge and pure formatting logic are tested.

Run with:  pytest tests/test_ws5_dashboard.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from drona.contracts import (
    AdvisingResponse,
    BiasFlag,
    DataTier,
    PathwayRecommendation,
    RetrievalCitation,
)
from drona.dashboard.components import (
    bias_colour,
    bias_label,
    confidence_emoji,
    format_bias_summary,
    format_citation_text,
    format_pathway_markdown,
    pathway_columns_layout,
    summarise_stats,
    tier_label,
)
from drona.dashboard.session_bridge import QueryEntry, SessionBridge


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_response(
    pathways: int = 2,
    bias_types: list[str] | None = None,
    refusal: bool = False,
    generation_ms: int = 250,
) -> AdvisingResponse:
    pw_list = [
        PathwayRecommendation(
            pathway_title=f"Pathway {i + 1}",
            rationale=f"Rationale {i + 1}",
            confidence="medium",
            citations=[
                RetrievalCitation(
                    source_type="job_posting",  # type: ignore[arg-type]
                    source_id=str(uuid.uuid4()),
                    tier=DataTier.NEPAL if i == 0 else DataTier.INTERNATIONAL,
                    excerpt="Sample job description text.",
                    relevance_score=0.05,
                )
            ],
        )
        for i in range(pathways)
    ]
    flags = [
        BiasFlag(
            bias_type=bt,  # type: ignore[arg-type]
            detected_signal=f"Signal for {bt}",
            mitigation_applied="Mitigation applied.",
        )
        for bt in (bias_types or [])
    ]
    return AdvisingResponse(
        query_id=str(uuid.uuid4()),
        summary="Summary text.",
        pathways=[] if refusal else pw_list,
        bias_flags=flags,
        refusal=refusal,
        refusal_reason="No data." if refusal else None,
        speak_text="Spoken response.",
        generation_time_ms=generation_ms,
    )


def _make_bridge() -> tuple[SessionBridge, dict]:
    state: dict = {}
    bridge = SessionBridge(state)
    return bridge, state


# ── Component helpers - pure functions ────────────────────────────────────────

class TestConfidenceEmoji:
    def test_high_returns_green(self) -> None:
        assert confidence_emoji("high") == "🟢"

    def test_medium_returns_yellow(self) -> None:
        assert confidence_emoji("medium") == "🟡"

    def test_low_returns_red(self) -> None:
        assert confidence_emoji("low") == "🔴"

    def test_unknown_returns_white(self) -> None:
        assert confidence_emoji("unknown") == "⚪"


class TestTierLabel:
    def test_nepal_contains_flag(self) -> None:
        assert "🇳🇵" in tier_label("nepal")

    def test_international_contains_globe(self) -> None:
        assert "🌐" in tier_label("international")

    def test_unknown_falls_back(self) -> None:
        result = tier_label("zz_unknown")
        assert len(result) > 0


class TestBiasHelpers:
    def test_bias_colour_returns_hex(self) -> None:
        colour = bias_colour("anchoring")
        assert colour.startswith("#")
        assert len(colour) == 7

    def test_bias_label_readable(self) -> None:
        label = bias_label("availability_heuristic")
        assert "Availability" in label

    def test_unknown_bias_colour_is_grey(self) -> None:
        colour = bias_colour("nonexistent_bias")
        assert colour == "#6e7781"


class TestFormatBiasSummary:
    def test_empty_flags_returns_empty(self) -> None:
        assert format_bias_summary([]) == []

    def test_one_flag_returns_one_entry(self) -> None:
        flags = [BiasFlag(
            bias_type="anchoring",  # type: ignore[arg-type]
            detected_signal="only Google",
            mitigation_applied="Show multiple options.",
        )]
        result = format_bias_summary(flags)
        assert len(result) == 1
        assert "label" in result[0]
        assert "signal" in result[0]
        assert "mitigation" in result[0]
        assert "colour" in result[0]

    def test_signal_preserved(self) -> None:
        flags = [BiasFlag(
            bias_type="loss_aversion",  # type: ignore[arg-type]
            detected_signal="scared of unemployment",
            mitigation_applied="Reframe positively.",
        )]
        result = format_bias_summary(flags)
        assert result[0]["signal"] == "scared of unemployment"


class TestFormatPathwayMarkdown:
    def test_contains_title(self) -> None:
        pw = PathwayRecommendation(
            pathway_title="Machine Learning Engineer",
            rationale="You have Python skills.",
            confidence="high",
        )
        md = format_pathway_markdown(pw, 1)
        assert "Machine Learning Engineer" in md

    def test_contains_confidence_emoji(self) -> None:
        pw = PathwayRecommendation(
            pathway_title="Data Analyst",
            rationale="Matches your SQL skills.",
            confidence="medium",
        )
        md = format_pathway_markdown(pw, 1)
        assert "🟡" in md

    def test_local_evidence_shown(self) -> None:
        pw = PathwayRecommendation(
            pathway_title="DevOps Engineer",
            rationale="Strong match.",
            local_market_evidence="Leapfrog Technology hires 5+ per year.",
            confidence="high",
        )
        md = format_pathway_markdown(pw, 1)
        assert "Nepal market evidence" in md
        assert "Leapfrog" in md

    def test_next_steps_shown(self) -> None:
        pw = PathwayRecommendation(
            pathway_title="Backend Developer",
            rationale="Matches.",
            next_concrete_steps=["Learn Docker", "Build a REST API"],
            confidence="medium",
        )
        md = format_pathway_markdown(pw, 1)
        assert "Docker" in md
        assert "REST API" in md

    def test_no_citations_no_source_line(self) -> None:
        pw = PathwayRecommendation(
            pathway_title="Analyst", rationale="ok", confidence="low"
        )
        md = format_pathway_markdown(pw, 1)
        assert "source" not in md.lower()

    def test_citations_count_shown(self) -> None:
        cit = RetrievalCitation(
            source_type="job_posting",  # type: ignore[arg-type]
            source_id="x",
            tier=DataTier.NEPAL,
            excerpt="text",
            relevance_score=0.05,
        )
        pw = PathwayRecommendation(
            pathway_title="Analyst", rationale="ok", confidence="high",
            citations=[cit],
        )
        md = format_pathway_markdown(pw, 1)
        assert "1 source" in md


class TestFormatCitationText:
    def test_contains_tier_label(self) -> None:
        cit = RetrievalCitation(
            source_type="job_posting",  # type: ignore[arg-type]
            source_id="x",
            tier=DataTier.NEPAL,
            excerpt="Python developer in Kathmandu.",
            relevance_score=0.05,
        )
        text = format_citation_text(cit)
        assert "🇳🇵" in text

    def test_contains_source_type(self) -> None:
        cit = RetrievalCitation(
            source_type="curriculum",  # type: ignore[arg-type]
            source_id="x",
            tier=DataTier.INTERNATIONAL,
            excerpt="Module content.",
            relevance_score=0.03,
        )
        text = format_citation_text(cit)
        assert "curriculum" in text


class TestPathwayColumnsLayout:
    def test_one_pathway_one_column(self) -> None:
        assert pathway_columns_layout(1) == [1]

    def test_two_pathways_two_columns(self) -> None:
        assert pathway_columns_layout(2) == [1, 1]

    def test_three_pathways_three_columns(self) -> None:
        assert pathway_columns_layout(3) == [1, 1, 1]

    def test_four_pathways_capped_at_three(self) -> None:
        # Max 3 per row; caller handles chunking
        assert len(pathway_columns_layout(4)) == 3

    def test_zero_pathways_returns_one_column(self) -> None:
        assert pathway_columns_layout(0) == [1]

    def test_all_weights_equal(self) -> None:
        layout = pathway_columns_layout(3)
        assert len(set(layout)) == 1  # all equal (anti-anchoring)


class TestSummariseStats:
    def test_empty_stats(self) -> None:
        stats = {
            "query_count": 0, "total_pathways": 0, "total_bias_flags": 0,
            "bias_type_counts": {}, "refusal_count": 0,
            "avg_generation_ms": None, "nepal_citations": 0, "intl_citations": 0,
        }
        result = summarise_stats(stats)
        assert any("0" in line for line in result)

    def test_bias_counts_shown_when_present(self) -> None:
        stats = {
            "query_count": 2, "total_pathways": 4, "total_bias_flags": 3,
            "bias_type_counts": {"anchoring": 2, "loss_aversion": 1},
            "refusal_count": 0, "avg_generation_ms": 300,
            "nepal_citations": 5, "intl_citations": 3,
        }
        result = summarise_stats(stats)
        text = "\n".join(result)
        assert "Anchoring" in text or "anchoring" in text.lower()
        assert "300ms" in text

    def test_nepal_percentage_computed(self) -> None:
        stats = {
            "query_count": 1, "total_pathways": 2, "total_bias_flags": 0,
            "bias_type_counts": {}, "refusal_count": 0, "avg_generation_ms": None,
            "nepal_citations": 3, "intl_citations": 1,
        }
        result = summarise_stats(stats)
        text = "\n".join(result)
        assert "75%" in text  # 3/(3+1) = 75%


# ── SessionBridge ─────────────────────────────────────────────────────────────

class TestSessionBridge:
    def _make_bridge_with_mock_engine(
        self, response: AdvisingResponse | None = None
    ) -> SessionBridge:
        state: dict = {}
        bridge = SessionBridge(state)
        mock_engine = MagicMock()
        mock_engine.advise.return_value = response or _make_response()
        state[SessionBridge._ENGINE_KEY] = mock_engine
        return bridge

    def test_initial_history_empty(self) -> None:
        bridge, _ = _make_bridge()
        assert bridge.history == []
        assert bridge.query_count == 0

    def test_submit_increments_query_count(self) -> None:
        bridge = self._make_bridge_with_mock_engine()
        bridge.submit("Career options?")
        assert bridge.query_count == 1

    def test_submit_appends_to_history(self) -> None:
        bridge = self._make_bridge_with_mock_engine()
        bridge.submit("What jobs suit me?")
        assert len(bridge.history) == 1
        assert isinstance(bridge.history[0], QueryEntry)

    def test_history_entry_preserves_query_text(self) -> None:
        bridge = self._make_bridge_with_mock_engine()
        bridge.submit("Python careers in Nepal")
        assert bridge.history[0].query_text == "Python careers in Nepal"

    def test_multiple_submits_accumulate(self) -> None:
        bridge = self._make_bridge_with_mock_engine()
        bridge.submit("Q1")
        bridge.submit("Q2")
        assert bridge.query_count == 2
        assert len(bridge.history) == 2

    def test_clear_history_resets(self) -> None:
        bridge = self._make_bridge_with_mock_engine()
        bridge.submit("Q1")
        bridge.clear_history()
        assert bridge.query_count == 0
        assert bridge.history == []

    def test_set_profile_stored_in_state(self) -> None:
        bridge, state = _make_bridge()
        bridge.set_profile(year=2, completed_modules=["4001COMP"], geography="nepal")
        profile = state[SessionBridge._PROFILE_KEY]
        assert profile["year"] == 2
        assert "4001COMP" in profile["completed"]
        assert profile["geography"] == "nepal"

    def test_stats_empty_session(self) -> None:
        bridge, _ = _make_bridge()
        stats = bridge.stats()
        assert stats["query_count"] == 0
        assert stats["total_pathways"] == 0

    def test_stats_after_query(self) -> None:
        bridge = self._make_bridge_with_mock_engine(
            _make_response(pathways=3, bias_types=["anchoring"])
        )
        bridge.submit("Test query")
        stats = bridge.stats()
        assert stats["query_count"] == 1
        assert stats["total_pathways"] == 3
        assert stats["total_bias_flags"] == 1
        assert "anchoring" in stats["bias_type_counts"]

    def test_stats_refusal_counted(self) -> None:
        bridge = self._make_bridge_with_mock_engine(
            _make_response(refusal=True)
        )
        bridge.submit("Obscure question")
        stats = bridge.stats()
        assert stats["refusal_count"] == 1

    def test_stats_generation_time_averaged(self) -> None:
        bridge = self._make_bridge_with_mock_engine(_make_response(generation_ms=200))
        bridge.submit("Q1")
        mock_engine = MagicMock()
        mock_engine.advise.return_value = _make_response(generation_ms=400)
        bridge._state[SessionBridge._ENGINE_KEY] = mock_engine
        bridge.submit("Q2")
        stats = bridge.stats()
        assert stats["avg_generation_ms"] == 300  # (200 + 400) / 2

    def test_state_shared_across_bridge_instances(self) -> None:
        """Two bridges over the same state dict share history."""
        state: dict = {}
        b1 = SessionBridge(state)
        b2 = SessionBridge(state)
        mock_engine = MagicMock()
        mock_engine.advise.return_value = _make_response()
        state[SessionBridge._ENGINE_KEY] = mock_engine
        b1.submit("Q from b1")
        assert b2.query_count == 1
