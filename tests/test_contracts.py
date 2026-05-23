"""Smoke tests for the contracts module. Run with: pytest tests/test_contracts.py"""

from datetime import datetime

from drona.contracts import (
    AdvisingQuery,
    AdvisingResponse,
    BiasFlag,
    CurriculumModule,
    DataTier,
    GestureType,
    InteractionAction,
    JobPosting,
    PathwayRecommendation,
    RetrievalCitation,
    StudentProfile,
)


def test_job_posting_basic():
    p = JobPosting(
        posting_id="mj_001",
        source="merojob",
        tier=DataTier.NEPAL,
        title="Junior Python Developer",
        employer="Leapfrog Technology",
        location="Kathmandu",
        skills_required=["Python", "Django", "PostgreSQL"],
        salary_min_npr=30000,
        salary_max_npr=50000,
    )
    assert p.tier == DataTier.NEPAL
    assert not p.is_synthetic


def test_curriculum_module():
    m = CurriculumModule(
        module_code="4001COMP",
        title="Introduction to Programming",
        year=1,
        semester=1,
        credits=20,
        learning_outcomes=["Understand variables", "Write basic functions"],
        skills_developed=["Python", "problem-solving"],
    )
    assert m.year == 1
    assert m.is_core


def test_advising_query_with_profile():
    profile = StudentProfile(
        session_id="sess_abc",
        year_of_study=1,
        declared_interests=["AI", "building things"],
        aspirations=["work in Nepal initially, maybe abroad later"],
        aspiration_geography="any",
    )
    q = AdvisingQuery(
        query_id="q_001",
        query_text="I'm in first semester. Should I focus on AI?",
        profile=profile,
    )
    assert q.max_pathways == 3  # default anti-anchoring
    assert q.require_local_first


def test_advising_response_structure():
    citation = RetrievalCitation(
        source_type="job_posting",
        source_id="mj_001",
        tier=DataTier.NEPAL,
        excerpt="Junior Python Developer at Leapfrog, NPR 30k-50k",
        relevance_score=0.87,
    )
    pathway = PathwayRecommendation(
        pathway_title="Backend / Python development",
        rationale="Matches your interest in building things; strong Kathmandu demand",
        matched_softwarica_modules=["4001COMP", "5002COMP"],
        local_market_evidence="12 of 50 sampled postings list Python+Django",
        next_concrete_steps=["Complete 4001COMP", "Build one portfolio project"],
        citations=[citation],
        confidence="high",
    )
    bias = BiasFlag(
        bias_type="availability_heuristic",
        detected_signal="user mentioned 'AI is the future'",
        mitigation_applied="surfaced 2 non-AI pathways with current Nepali demand data",
    )
    r = AdvisingResponse(
        query_id="q_001",
        summary="Three pathways worth considering; backend has strongest current local demand.",
        pathways=[pathway],
        bias_flags=[bias],
        speak_text="I see three pathways for you. Want me to walk through them?",
    )
    assert not r.refusal
    assert len(r.bias_flags) == 1


def test_interaction_action_serializable():
    a = InteractionAction(
        action_id="act_001",
        gesture=GestureType.POINT,
        target_direction=(0.5, 0.0, 0.3),
        speech_text="Look at the dashboard here",
        duration_seconds=2.0,
    )
    # Must serialize cleanly (this is what ROS2 will need in Phase 2)
    payload = a.model_dump_json()
    assert "point" in payload
    assert "act_001" in payload
