"""
WS2 smoke tests — advising intelligence layer.

These tests do NOT load ML models, hit Ollama, or touch ChromaDB.
They verify the logic, contracts, and schema validation using stubs and
in-memory fixtures only.

Run with:  pytest tests/test_ws2_advising.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from drona.advising.bias_detector import BiasDetector, _first_matches
from drona.advising.engine import AdvisingEngine, make_query, _build_summary, _default_speak
from drona.advising.prompt_builder import build_prompt, _format_citations, _format_profile
from drona.contracts import (
    AdvisingQuery,
    AdvisingResponse,
    BiasFlag,
    DataTier,
    PathwayRecommendation,
    RetrievalCitation,
    StudentProfile,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_citation(
    source_type: str = "job_posting",
    tier: DataTier = DataTier.NEPAL,
    excerpt: str = "Senior Python Developer, Leapfrog Technology, Kathmandu. 3 yrs exp.",
    score: float = 0.05,
) -> RetrievalCitation:
    return RetrievalCitation(
        source_type=source_type,  # type: ignore[arg-type]
        source_id=str(uuid.uuid4()),
        tier=tier,
        excerpt=excerpt,
        relevance_score=score,
    )


def _make_profile(
    year: int = 2,
    modules: list[str] | None = None,
    skills: list[str] | None = None,
    ratings: dict[str, int] | None = None,
) -> StudentProfile:
    return StudentProfile(
        session_id=str(uuid.uuid4()),
        year_of_study=year,
        completed_modules=modules or ["4001COMP", "4002COMP"],
        declared_skills=skills or ["Python", "SQL"],
        self_assessed_skill_levels=ratings or {},
    )


def _make_advising_query(text: str, profile: StudentProfile | None = None) -> AdvisingQuery:
    return AdvisingQuery(
        query_id=str(uuid.uuid4()),
        query_text=text,
        profile=profile or _make_profile(),
    )


# ── BiasDetector tests ────────────────────────────────────────────────────────

class TestBiasDetector:
    def setup_method(self) -> None:
        self.detector = BiasDetector()

    def test_clean_query_returns_no_flags(self) -> None:
        flags = self.detector.detect(
            "What career paths are available for BSc Computing graduates in Nepal?"
        )
        assert flags == []

    def test_detects_availability_heuristic_friend(self) -> None:
        flags = self.detector.detect("My friend got a job at Leapfrog. Should I try there?")
        types = [f.bias_type for f in flags]
        assert "availability_heuristic" in types

    def test_detects_availability_heuristic_heard(self) -> None:
        flags = self.detector.detect("I heard AI pays really well these days.")
        types = [f.bias_type for f in flags]
        assert "availability_heuristic" in types

    def test_detects_anchoring_only_google(self) -> None:
        flags = self.detector.detect("I only want to work at Google, nowhere else.")
        types = [f.bias_type for f in flags]
        assert "anchoring" in types

    def test_detects_anchoring_fixed_on(self) -> None:
        flags = self.detector.detect("I'm fixed on becoming a data scientist, it's decided.")
        types = [f.bias_type for f in flags]
        assert "anchoring" in types

    def test_detects_confirmation_bias(self) -> None:
        flags = self.detector.detect("Python is definitely the best language, right?")
        types = [f.bias_type for f in flags]
        assert "confirmation" in types

    def test_detects_loss_aversion(self) -> None:
        flags = self.detector.detect(
            "I'm scared of being unemployed after graduation. What's the safest path?"
        )
        types = [f.bias_type for f in flags]
        assert "loss_aversion" in types

    def test_detects_consistency_bias(self) -> None:
        flags = self.detector.detect(
            "I've already told my parents I'll be a data scientist. I can't change now."
        )
        types = [f.bias_type for f in flags]
        assert "consistency" in types

    def test_detects_dunning_kruger_overconfidence_text(self) -> None:
        flags = self.detector.detect(
            "I know Python very well, I can easily build any web app."
        )
        types = [f.bias_type for f in flags]
        assert "dunning_kruger" in types

    def test_detects_dunning_kruger_from_profile(self) -> None:
        profile = _make_profile(
            modules=["4001COMP"],  # only 1 module
            skills=["Python", "ML"],
            ratings={"Python": 5, "ML": 5},  # all 5s
        )
        flags = self.detector.detect("How do I get a senior ML role?", profile=profile)
        types = [f.bias_type for f in flags]
        assert "dunning_kruger" in types

    def test_detects_dunning_kruger_underconfidence_profile(self) -> None:
        profile = _make_profile(
            modules=["4001COMP", "4002COMP", "4003COMP", "4004COMP"],  # 4 modules
            skills=["Python"],
            ratings={"Python": 1},  # all low
        )
        flags = self.detector.detect("I'm not sure I'm good enough for any job.", profile=profile)
        types = [f.bias_type for f in flags]
        assert "dunning_kruger" in types

    def test_at_most_one_flag_per_type(self) -> None:
        flags = self.detector.detect(
            "My friend says AI is the future and I know Python very well."
        )
        types = [f.bias_type for f in flags]
        assert len(types) == len(set(types)), "Duplicate bias types detected"

    def test_flag_fields_are_non_empty(self) -> None:
        flags = self.detector.detect("I'm scared of failing so I only want safe jobs.")
        for f in flags:
            assert f.detected_signal, f"{f.bias_type} detected_signal is empty"
            assert f.mitigation_applied, f"{f.bias_type} mitigation_applied is empty"

    def test_flag_validates_against_contract(self) -> None:
        flags = self.detector.detect("My classmate got into Microsoft. Should I aim there?")
        for f in flags:
            # Pydantic will raise if the flag doesn't match the BiasFlag schema
            assert isinstance(f, BiasFlag)


# ── Prompt builder tests ──────────────────────────────────────────────────────

class TestPromptBuilder:
    def test_build_prompt_returns_two_strings(self) -> None:
        query = _make_advising_query("What jobs use Python in Kathmandu?")
        citations = [_make_citation()]
        bias_flags: list[BiasFlag] = []
        system, user = build_prompt(query, citations, bias_flags)
        assert isinstance(system, str) and len(system) > 50
        assert isinstance(user, str) and len(user) > 50

    def test_system_prompt_contains_max_pathways(self) -> None:
        query = _make_advising_query("Tell me about software careers.")
        query.max_pathways = 5
        system, _ = build_prompt(query, [], [])
        assert "5" in system

    def test_system_prompt_contains_bias_instruction_when_flagged(self) -> None:
        query = _make_advising_query("I'm scared of unemployment, what's safe?")
        flags = [BiasFlag(
            bias_type="loss_aversion",
            detected_signal="scared of",
            mitigation_applied="reframe as positive goals",
        )]
        system, _ = build_prompt(query, [], flags)
        assert "LOSS_AVERSION" in system

    def test_no_bias_section_when_no_flags(self) -> None:
        query = _make_advising_query("What is data science?")
        system, _ = build_prompt(query, [], [])
        assert "BIAS MITIGATION" not in system

    def test_user_prompt_contains_query_text(self) -> None:
        text = "How do I become a DevOps engineer in Kathmandu?"
        query = _make_advising_query(text)
        _, user = build_prompt(query, [], [])
        assert text in user

    def test_citations_sorted_nepal_first(self) -> None:
        nepal_cit = _make_citation(tier=DataTier.NEPAL, excerpt="Nepal job data")
        intl_cit = _make_citation(tier=DataTier.INTERNATIONAL, excerpt="US job data")
        formatted = _format_citations([intl_cit, nepal_cit])
        nepal_pos = formatted.find("NEPAL")
        intl_pos = formatted.find("INTERNATIONAL")
        assert nepal_pos < intl_pos, "Nepal citations should appear before International"

    def test_empty_citations_returns_placeholder(self) -> None:
        result = _format_citations([])
        assert "No retrieved" in result

    def test_profile_format_includes_year(self) -> None:
        query = _make_advising_query("Career advice?", _make_profile(year=3))
        _, user = build_prompt(query, [], [])
        assert "Year of study: 3" in user


# ── Engine tests (fully mocked) ────────────────────────────────────────────────

class TestAdvisingEngine:
    """Tests for the engine with mocked retriever, reranker, and LLM."""

    def _make_stub_doc(self) -> MagicMock:
        doc = MagicMock()
        doc.id = str(uuid.uuid4())
        doc.text = "Python developer roles in Kathmandu require 2+ years experience."
        doc.metadata = {"tier": "nepal", "source_type": "job_posting"}
        doc.rrf_score = 0.05
        return doc

    def _make_engine(
        self,
        docs: list | None = None,
        reranked: list | None = None,
        llm_returns: tuple | None = None,
    ) -> AdvisingEngine:
        stub_docs = docs if docs is not None else [self._make_stub_doc() for _ in range(3)]
        stub_reranked = reranked if reranked is not None else stub_docs

        mock_retriever = MagicMock()
        mock_retriever.retrieve_raw.return_value = stub_docs

        mock_reranker = MagicMock()
        mock_reranker.rerank_docs.return_value = stub_reranked

        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        if llm_returns:
            mock_llm.generate.return_value = llm_returns
        else:
            pathway = PathwayRecommendation(
                pathway_title="Software Developer",
                rationale="Matches your Python skills",
                confidence="medium",
            )
            mock_llm.generate.return_value = (
                [pathway],
                "I found a great pathway for you.",
                False,
                None,
            )

        return AdvisingEngine(
            retriever=mock_retriever,
            reranker=mock_reranker,
            llm=mock_llm,
        )

    def test_advise_returns_advising_response(self) -> None:
        engine = self._make_engine()
        query = make_query("What jobs suit a Python developer in Nepal?")
        response = engine.advise(query)
        assert isinstance(response, AdvisingResponse)

    def test_advise_non_refusal_has_pathways(self) -> None:
        engine = self._make_engine()
        query = make_query("Career paths for BSc Computing?")
        response = engine.advise(query)
        assert not response.refusal
        assert len(response.pathways) >= 1

    def test_advise_refusal_when_no_docs(self) -> None:
        engine = self._make_engine(docs=[], reranked=[])
        query = make_query("Some very specific question with no data")
        response = engine.advise(query)
        assert response.refusal
        assert response.requires_human_followup

    def test_advise_refusal_when_llm_unavailable(self) -> None:
        stub_docs = [self._make_stub_doc() for _ in range(3)]
        mock_retriever = MagicMock()
        mock_retriever.retrieve_raw.return_value = stub_docs
        mock_reranker = MagicMock()
        mock_reranker.rerank_docs.return_value = stub_docs
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = False

        engine = AdvisingEngine(
            retriever=mock_retriever,
            reranker=mock_reranker,
            llm=mock_llm,
        )
        query = make_query("What is data science?")
        response = engine.advise(query)
        assert response.refusal

    def test_advise_refusal_when_llm_fails(self) -> None:
        engine = self._make_engine(
            llm_returns=([], "Sorry, I could not generate a response.", True, "JSON parse error")
        )
        query = make_query("Explain cloud computing careers.")
        response = engine.advise(query)
        assert response.refusal

    def test_response_query_id_matches_request(self) -> None:
        engine = self._make_engine()
        query = make_query("Test query")
        response = engine.advise(query)
        assert response.query_id == query.query_id

    def test_response_has_speak_text(self) -> None:
        engine = self._make_engine()
        query = make_query("What careers suit me?")
        response = engine.advise(query)
        assert response.speak_text and len(response.speak_text) > 0

    def test_response_has_generation_time(self) -> None:
        engine = self._make_engine()
        query = make_query("What are the best CS careers?")
        response = engine.advise(query)
        assert response.generation_time_ms is not None
        assert response.generation_time_ms >= 0

    def test_bias_flags_propagate_to_response(self) -> None:
        engine = self._make_engine()
        query = make_query(
            "My friend got into Google. I'm scared of not making it. Tell me I'm good enough."
        )
        response = engine.advise(query)
        # Multiple biases present in query — at least one should be detected
        assert len(response.bias_flags) >= 1


# ── make_query convenience helper tests ───────────────────────────────────────

class TestMakeQuery:
    def test_returns_advising_query(self) -> None:
        q = make_query("What is backend development?")
        assert isinstance(q, AdvisingQuery)

    def test_defaults_are_sane(self) -> None:
        q = make_query("Test")
        assert q.max_pathways == 3
        assert q.profile.session_id != ""
        assert q.query_id != ""

    def test_accepts_profile_fields(self) -> None:
        q = make_query(
            "Career in ML?",
            year=3,
            completed=["4001COMP", "4002COMP"],
            skills=["Python"],
            geography="nepal",
        )
        assert q.profile.year_of_study == 3
        assert "4001COMP" in q.profile.completed_modules
        assert q.profile.aspiration_geography == "nepal"


# ── Internal helper tests ─────────────────────────────────────────────────────

class TestInternalHelpers:
    def test_build_summary_no_pathways(self) -> None:
        result = _build_summary([], [])
        assert "No relevant" in result

    def test_build_summary_with_pathways(self) -> None:
        p = PathwayRecommendation(pathway_title="ML Engineer", rationale="test", confidence="high")
        result = _build_summary([p], [_make_citation()])
        assert "ML Engineer" in result
        assert "1" in result  # 1 citation

    def test_default_speak_no_pathways(self) -> None:
        result = _default_speak([])
        assert len(result) > 0

    def test_default_speak_one_pathway(self) -> None:
        p = PathwayRecommendation(pathway_title="DevOps Engineer", rationale="test", confidence="medium")
        result = _default_speak([p])
        assert "DevOps Engineer" in result

    def test_default_speak_multiple_pathways(self) -> None:
        ps = [
            PathwayRecommendation(pathway_title="ML Engineer", rationale="r", confidence="high"),
            PathwayRecommendation(pathway_title="Data Analyst", rationale="r", confidence="medium"),
        ]
        result = _default_speak(ps)
        assert "2" in result
        assert "ML Engineer" in result

    def test_first_matches_returns_empty_for_no_match(self) -> None:
        import re
        pats = [re.compile(r"\bXYZQQQ\b")]
        assert _first_matches("hello world", pats) == []

    def test_first_matches_deduplicates(self) -> None:
        import re
        pats = [re.compile(r"\bhello\b"), re.compile(r"\bhello\b")]
        result = _first_matches("hello world hello", pats)
        assert result == ["hello"]
