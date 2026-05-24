"""
Synthetic evaluation query bank for D.R.O.N.A.

Provides labelled queries for evaluating each research contribution:

  C1 — Retrieval quality
    Queries with known relevant content types (curriculum vs career vs both).
    Used to compute NDCG@K, MRR, Recall@K comparing hybrid vs dense-only.

  C2 — Bias detection quality
    Queries with known expected bias labels.
    Used to compute precision, recall, F1 per bias type.
    Sourced from the psychology / advising literature on cognitive bias examples.

  C3 — Gesture evaluation
    Gesture labels with expected duration ranges and smoothness thresholds.
    Used to compare KeyframePolicy vs ACT baseline.

  C4 — Stack evaluation
    Queries that should surface Nepal-local data preferentially.
    Used to measure Nepal citation ratio.

Why synthetic queries?
  Collecting labelled student advising queries would require ethics board
  approval (PII/welfare considerations). Synthetic queries are standard
  practice in IR evaluation (cf. TREC, BEIR benchmarks) when real data is
  unavailable. The bias detection labels are manually verified against the
  pattern definitions in bias_detector.py — these are ground truth by
  construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ── Data types ────────────────────────────────────────────────────────────────

RelevanceCategory = Literal["curriculum", "career", "both", "none"]
BiasType = Literal[
    "availability_heuristic", "anchoring", "confirmation",
    "dunning_kruger", "loss_aversion", "consistency",
]


@dataclass
class EvalQuery:
    """One labelled evaluation query."""
    query_id: str
    query_text: str
    # C1: expected relevance category
    expected_relevance: RelevanceCategory
    # C2: expected bias types (may be empty)
    expected_biases: list[BiasType] = field(default_factory=list)
    # C4: should primarily retrieve Nepal-tier data
    prefers_local: bool = True
    # Metadata
    category: str = "general"
    notes: str = ""


# ── C1 retrieval queries ──────────────────────────────────────────────────────
# These queries are designed to match specific content areas of the knowledge
# base. "curriculum" queries should rank curriculum documents highly; "career"
# queries should rank job postings and pathways highly; "both" queries need both.

C1_QUERIES: list[EvalQuery] = [
    EvalQuery(
        query_id="c1_001",
        query_text="What modules teach Python programming at Softwarica?",
        expected_relevance="curriculum",
        prefers_local=True,
        category="curriculum_lookup",
        notes="Should retrieve programming/software modules.",
    ),
    EvalQuery(
        query_id="c1_002",
        query_text="machine learning algorithms taught in BSc Computing",
        expected_relevance="curriculum",
        prefers_local=True,
        category="curriculum_lookup",
        notes="ML-adjacent curriculum content.",
    ),
    EvalQuery(
        query_id="c1_003",
        query_text="software developer jobs in Kathmandu salary Nepal",
        expected_relevance="career",
        prefers_local=True,
        category="job_market",
        notes="Should surface Nepal job postings.",
    ),
    EvalQuery(
        query_id="c1_004",
        query_text="data scientist job requirements skills experience",
        expected_relevance="career",
        prefers_local=False,
        category="job_market",
        notes="Generic job market query.",
    ),
    EvalQuery(
        query_id="c1_005",
        query_text="how do database modules prepare me for backend developer roles",
        expected_relevance="both",
        prefers_local=True,
        category="curriculum_to_career",
        notes="Bridge query — needs both curriculum and career docs.",
    ),
    EvalQuery(
        query_id="c1_006",
        query_text="career pathways for computing graduates in Nepal fintech",
        expected_relevance="both",
        prefers_local=True,
        category="curriculum_to_career",
        notes="Nepal fintech sector — eSewa, Khalti etc.",
    ),
    EvalQuery(
        query_id="c1_007",
        query_text="network security cybersecurity jobs Kathmandu",
        expected_relevance="career",
        prefers_local=True,
        category="job_market",
    ),
    EvalQuery(
        query_id="c1_008",
        query_text="what is the difference between software engineering and computer science",
        expected_relevance="curriculum",
        prefers_local=False,
        category="curriculum_lookup",
        notes="Conceptual query — less lexical overlap with postings.",
    ),
    EvalQuery(
        query_id="c1_009",
        query_text="internship opportunities Nepal computing students",
        expected_relevance="career",
        prefers_local=True,
        category="job_market",
    ),
    EvalQuery(
        query_id="c1_010",
        query_text="final year project ideas AI machine learning",
        expected_relevance="curriculum",
        prefers_local=False,
        category="curriculum_lookup",
    ),
]

# ── C2 bias detection queries ──────────────────────────────────────────────────
# Each query is designed to trigger a specific bias pattern. Multiple biases
# per query are possible but each has a PRIMARY expected bias.

C2_QUERIES: list[EvalQuery] = [
    # Availability heuristic
    EvalQuery(
        query_id="c2_av_001",
        query_text="My friend got a job at Leapfrog earning Rs 80,000. How do I get there?",
        expected_biases=["availability_heuristic", "anchoring"],
        expected_relevance="career",
        category="availability",
        notes="Friend anecdote + salary anchor.",
    ),
    EvalQuery(
        query_id="c2_av_002",
        query_text="I heard AI pays really well these days. Should I focus only on AI?",
        expected_biases=["availability_heuristic", "anchoring"],
        expected_relevance="career",
        category="availability",
    ),
    EvalQuery(
        query_id="c2_av_003",
        query_text="Everyone says cloud computing is the future. What do you think?",
        expected_biases=["availability_heuristic", "confirmation"],
        expected_relevance="career",
        category="availability",
    ),
    # Anchoring
    EvalQuery(
        query_id="c2_an_001",
        query_text="I only want to work at Google or Microsoft, nowhere else. How do I qualify?",
        expected_biases=["anchoring"],
        expected_relevance="career",
        category="anchoring",
    ),
    EvalQuery(
        query_id="c2_an_002",
        query_text="I've decided I will only accept jobs paying exactly Rs 100,000 minimum.",
        expected_biases=["anchoring"],
        expected_relevance="career",
        category="anchoring",
    ),
    # Confirmation bias
    EvalQuery(
        query_id="c2_cf_001",
        query_text="Python is definitely the best language for career growth, right? Isn't it?",
        expected_biases=["confirmation"],
        expected_relevance="career",
        category="confirmation",
    ),
    EvalQuery(
        query_id="c2_cf_002",
        query_text="Don't you agree that data science is the only future-proof career in Nepal?",
        expected_biases=["confirmation"],
        expected_relevance="career",
        category="confirmation",
    ),
    # Loss aversion
    EvalQuery(
        query_id="c2_la_001",
        query_text="I'm scared of being unemployed after graduation. What's the safest career path?",
        expected_biases=["loss_aversion"],
        expected_relevance="career",
        category="loss_aversion",
    ),
    EvalQuery(
        query_id="c2_la_002",
        query_text="What should I avoid to not make a mistake in my career choice?",
        expected_biases=["loss_aversion"],
        expected_relevance="career",
        category="loss_aversion",
    ),
    # Consistency bias
    EvalQuery(
        query_id="c2_co_001",
        query_text="I've already told my parents I'll be a data scientist. I can't change now.",
        expected_biases=["consistency"],
        expected_relevance="career",
        category="consistency",
    ),
    EvalQuery(
        query_id="c2_co_002",
        query_text="I've been saying for years I want to be a game developer. It's too late to switch.",
        expected_biases=["consistency"],
        expected_relevance="career",
        category="consistency",
    ),
    # Dunning-Kruger (text-based signals)
    EvalQuery(
        query_id="c2_dk_001",
        query_text="I know Python very well and can easily build any web application. What senior roles suit me?",
        expected_biases=["dunning_kruger"],
        expected_relevance="career",
        category="dunning_kruger",
    ),
    EvalQuery(
        query_id="c2_dk_002",
        query_text="I'm terrible at everything. No one would hire me. Is there any hope?",
        expected_biases=["dunning_kruger"],
        expected_relevance="career",
        category="dunning_kruger",
    ),
    # Clean queries (no bias — important for precision)
    EvalQuery(
        query_id="c2_clean_001",
        query_text="What career paths are available for BSc Computing graduates in Nepal?",
        expected_biases=[],
        expected_relevance="both",
        category="clean",
    ),
    EvalQuery(
        query_id="c2_clean_002",
        query_text="How does the database module at Softwarica prepare me for industry?",
        expected_biases=[],
        expected_relevance="both",
        category="clean",
    ),
    EvalQuery(
        query_id="c2_clean_003",
        query_text="What skills do I need for a data analyst role in Kathmandu?",
        expected_biases=[],
        expected_relevance="career",
        category="clean",
    ),
]

# ── C3 gesture evaluation parameters ─────────────────────────────────────────

@dataclass
class GestureEvalSpec:
    """Expected behaviour spec for one gesture."""
    gesture_label: str
    expected_min_frames: int     # trajectory must be at least this long
    expected_max_frames: int     # and at most this long (sanity bounds)
    expected_max_jerk: float     # mean absolute jerk threshold (smoothness)
    expected_path_length_min: float  # arm must actually move (not stay still)


C3_GESTURE_SPECS: list[GestureEvalSpec] = [
    # Jerk thresholds are sanity bounds for the keyframe baseline, not quality targets.
    # Keyframe linear interpolation produces step-changes at keyframe boundaries that
    # yield high jerk — these measured values ARE the thesis C3 baseline. ACT is
    # expected to achieve lower jerk than these thresholds.
    GestureEvalSpec("greet",    10,  200, 50.0, 0.5),
    GestureEvalSpec("nod",      10,  150, 30.0, 0.2),
    GestureEvalSpec("point",    8,   100, 20.0, 0.3),
    GestureEvalSpec("idle",     5,   50,   1.0, 0.0),
    GestureEvalSpec("listen",   10,  150, 10.0, 0.2),
    GestureEvalSpec("farewell", 10,  200, 50.0, 0.5),
]

# ── C4 stack queries (expect Nepal-tier results) ───────────────────────────────

C4_QUERIES: list[EvalQuery] = [
    EvalQuery(
        query_id="c4_001",
        query_text="software jobs Kathmandu Nepal 2024",
        expected_relevance="career",
        prefers_local=True,
        category="nepal_market",
    ),
    EvalQuery(
        query_id="c4_002",
        query_text="IT companies hiring in Nepal Leapfrog F1Soft Yomari",
        expected_relevance="career",
        prefers_local=True,
        category="nepal_market",
    ),
    EvalQuery(
        query_id="c4_003",
        query_text="fintech startup jobs Kathmandu eSewa Khalti",
        expected_relevance="career",
        prefers_local=True,
        category="nepal_market",
    ),
]


# ── Combined bank ──────────────────────────────────────────────────────────────

ALL_QUERIES: list[EvalQuery] = C1_QUERIES + C2_QUERIES + C4_QUERIES


def queries_by_category(category: str) -> list[EvalQuery]:
    return [q for q in ALL_QUERIES if q.category == category]


def queries_with_bias(bias_type: BiasType) -> list[EvalQuery]:
    return [q for q in ALL_QUERIES if bias_type in q.expected_biases]


def clean_queries() -> list[EvalQuery]:
    return [q for q in ALL_QUERIES if not q.expected_biases]
