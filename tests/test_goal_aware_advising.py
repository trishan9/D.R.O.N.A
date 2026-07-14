"""Goal-aware advising: diverse aspiration tracks (employment, postgrad abroad,
startup, research, freelance) flow through the SFT generator, the prompt, and the
API request. Guards the feature that lets DRONA handle "get into MIT" or "build a
startup" as gracefully as "get a job in Nepal".
"""

from __future__ import annotations

from drona.advising.prompt_builder import build_prompt
from drona.api.schemas import AdviseRequest
from drona.contracts import (
    STUDENT_GOALS,
    AdvisingQuery,
    CareerPathway,
    CurriculumModule,
    DataTier,
    StudentProfile,
)
from drona.finetune import qa_generator


def _pathways() -> list[CareerPathway]:
    return [
        CareerPathway(
            pathway_id=f"pw_{i}", title=t, tier=DataTier.INTERNATIONAL,
            description=f"{t} do things.", typical_skills=["Python", "SQL", "Machine learning"],
        )
        for i, t in enumerate([
            "Data Scientists", "Software Developers", "Information Security Analysts",
            "Web and Digital Interface Designers", "Database Administrators",
        ])
    ]


def _modules() -> list[CurriculumModule]:
    real = [
        CurriculumModule(module_code="ST5001CEM", title="Machine Learning", year=2,
                         description="ML", skills_developed=["Machine learning", "Python"]),
        CurriculumModule(module_code="ST6001CEM", title="Individual Project", year=3,
                         description="Capstone", skills_developed=["Research", "Python"]),
    ]
    guides = [
        CurriculumModule(module_code="GUIDE-GRAD", title="Postgrad Guide", year=1,
                         description="Grad school abroad", content="MS/PhD, IELTS, funding."),
        CurriculumModule(module_code="GUIDE-STARTUP", title="Startup Guide", year=1,
                         description="Founding", content="MVP, users, YC."),
        CurriculumModule(module_code="GUIDE-AIROLES", title="AI Roles Guide", year=1,
                         description="AI-era roles", content="ML engineer, augmentation."),
    ]
    return real + guides


def test_all_goal_tracks_are_generated():
    pairs = qa_generator.generate_qa_pairs(_pathways(), _modules(), [], target_count=300)
    goals = {p.profile.goal for p in pairs}
    # Every non-"undecided" track the SFT teaches should appear.
    for g in ("employment", "postgrad_abroad", "startup", "research", "freelance"):
        assert g in goals, f"missing goal track: {g}"


def test_gold_answers_carry_goal_type_and_ground_on_guides():
    pairs = qa_generator.generate_qa_pairs(_pathways(), _modules(), [], target_count=300)
    postgrad = next(p for p in pairs if p.profile.goal == "postgrad_abroad")
    # Each gold pathway is labelled with a goal_type the UI can render.
    gtypes = {pw.get("goal_type") for pw in postgrad.target_response["pathways"]}
    assert gtypes == {"postgrad_abroad"}
    # The postgrad answer is grounded on the grad-school guide anchor.
    assert "GUIDE-GRAD" in postgrad.anchor_ids
    # Track-appropriate content, not generic employment advice.
    joined = str(postgrad.target_response).lower()
    assert any(w in joined for w in ("statement of purpose", "ielts", "assistantship", "phd"))


def test_matched_modules_are_real_teaching_modules_not_guides():
    pairs = qa_generator.generate_qa_pairs(_pathways(), _modules(), [], target_count=120)
    for p in pairs:
        for pw in p.target_response["pathways"]:
            for code in pw["matched_softwarica_modules"]:
                assert not code.startswith(("GUIDE-", "INFO-")), code


def test_prompt_includes_goal_specific_guidance():
    q = AdvisingQuery(
        query_id="q1", query_text="How do I get into MIT for a Master's?",
        profile=StudentProfile(session_id="s", goal="postgrad_abroad",
                               target_institutions=["MIT"], timeline_years=2),
    )
    system, user = build_prompt(q, [], [])
    assert "GOAL-SPECIFIC GUIDANCE (postgrad_abroad)" in system
    assert "goal_type" in system  # response schema advertises the label
    assert "Primary goal: postgraduate study abroad" in user
    assert "MIT" in user


def test_advise_request_passes_goal_fields_through():
    req = AdviseRequest(
        query_text="I want to build a startup", goal="startup",
        target_institutions=["Y Combinator"], timeline_years=3,
    )
    query = req.to_query()
    assert query.profile.goal == "startup"
    assert query.profile.target_institutions == ["Y Combinator"]
    assert query.profile.timeline_years == 3


def test_student_goals_constant_matches_profile_default():
    assert "employment" in STUDENT_GOALS
    assert StudentProfile(session_id="s").goal == "employment"
