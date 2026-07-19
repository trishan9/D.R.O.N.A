"""
Synthetic evaluation query bank for D.R.O.N.A.

Provides labelled queries for evaluating each research contribution:

  C1 - Retrieval quality
    Queries with known relevant content types (curriculum vs career vs both).
    Used to compute NDCG@K, MRR, Recall@K comparing hybrid vs dense-only.

  C2 - Bias detection quality
    Queries with known expected bias labels.
    Used to compute precision, recall, F1 per bias type.
    Sourced from the psychology / advising literature on cognitive bias examples.

  C3 - Gesture evaluation
    Gesture labels with expected duration ranges and smoothness thresholds.
    Used to compare KeyframePolicy vs ACT baseline.

  C4 - Stack evaluation
    Queries that should surface Nepal-local data preferentially.
    Used to measure Nepal citation ratio.

Why synthetic queries?
  Collecting labelled student advising queries would require ethics board
  approval (PII/welfare considerations). Synthetic queries are standard
  practice in IR evaluation (cf. TREC, BEIR benchmarks) when real data is
  unavailable. The bias detection labels are manually verified against the
  pattern definitions in bias_detector.py - these are ground truth by
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
    # C1 GROUND TRUTH: module codes that genuinely answer this query. Retrieval is
    # scored against these (module level, so content chunks collapse to their
    # module). Empty = query is not part of the labelled C1 bank.
    relevant_modules: frozenset[str] = frozenset()
    # Metadata
    category: str = "general"
    notes: str = ""


# ── C1 retrieval queries ──────────────────────────────────────────────────────
# These queries are designed to match specific content areas of the knowledge
# base. "curriculum" queries should rank curriculum documents highly; "career"
# queries should rank job postings and pathways highly; "both" queries need both.

def _c1(qid: str, text: str, modules: set[str]) -> EvalQuery:
    """Build a labelled C1 retrieval query (curriculum ground truth)."""
    return EvalQuery(query_id=qid, query_text=text, expected_relevance="curriculum",
                     relevant_modules=frozenset(modules), category="c1_labelled")


C1_QUERIES: list[EvalQuery] = [
    # Ground-truth labelled retrieval bank. `relevant_modules` lists the module
    # codes that genuinely answer the query, judged from the real Softwarica
    # module titles in the index. Retrieval is scored against these at MODULE
    # level, so a system is only credited for surfacing the right modules.
    _c1("c1_ml", "which modules teach machine learning",
        {"ST6006CEM", "ST5000CEM", "ST6057CEM", "ST6058CEM"}),
    _c1("c1_nn", "neural networks and deep learning module",
        {"ST6057CEM", "ST6006CEM"}),
    _c1("c1_agents", "intelligent agents module", {"ST6058CEM"}),
    _c1("c1_ai_intro", "introduction to artificial intelligence", {"ST5000CEM"}),
    _c1("c1_python", "where do I learn Python programming",
        {"ST4000CEM", "ST4061CEM", "ST5062CEM", "ST5008CEM", "SP4001COM"}),
    _c1("c1_oop", "object oriented programming module", {"ST4003CEM"}),
    _c1("c1_algo", "algorithms and data structures",
        {"ST5003CEM", "ST4000CEM", "ST4061CEM", "ST5062CEM"}),
    _c1("c1_math", "mathematics for computer science",
        {"ST4002CEM", "ST4068CEM"}),
    _c1("c1_toc", "theory of computation", {"ST5002CEM"}),
    _c1("c1_db", "database systems module", {"ST4005CEM", "ST4056CEM"}),
    _c1("c1_web", "web development modules",
        {"ST5007CEM", "ST4056CEM", "ST6003CEM"}),
    _c1("c1_webapi", "web API development", {"ST6003CEM"}),
    _c1("c1_websec", "web security", {"ST5067CEM"}),
    _c1("c1_mobile", "mobile app development for Android",
        {"ST6002CEM", "SP5000COM", "SP5000C0M"}),
    _c1("c1_ux", "user experience design module", {"ST6012CEM"}),
    _c1("c1_se", "software engineering and agile development",
        {"ST5001CEM", "ST5009CEM"}),
    _c1("c1_sd", "software design module", {"ST4001CEM", "ST4067CEM"}),
    _c1("c1_os", "operating systems module",
        {"ST5004CEM", "ST5068CEM"}),
    _c1("c1_net", "computer networking module",
        {"ST5064CEM", "ST4065CEM", "ST4004CEM"}),
    _c1("c1_ds", "data science and big data modules",
        {"ST5005CEM", "ST5014CEM", "ST5011CEM"}),
    _c1("c1_pentest", "penetration testing and ethical hacking",
        {"ST5063CEM", "ST6049CEM", "ST6048CEM"}),
    _c1("c1_exploit", "exploit development", {"ST6048CEM"}),
    _c1("c1_crypto", "practical cryptography", {"ST6051CEM"}),
    _c1("c1_forensics", "digital forensics",
        {"ST4060CEM", "ST5065CEM", "SC-001"}),
    _c1("c1_reverse", "reverse engineering module", {"ST6052CEM"}),
    _c1("c1_secfound", "foundations of cyber security",
        {"ST4064CEM", "ST4063CEM"}),
    _c1("c1_secmgmt", "security management, audit and monitoring",
        {"ST6054CEM", "ST6050CEM"}),
    _c1("c1_seccareer", "cyber security careers", {"ST5069CEM"}),
    _c1("c1_project", "final year individual project",
        {"ST6001CEM", "ST6000CEM"}),
    _c1("c1_enterprise", "enterprise project module", {"ST5010CEM"}),
    _c1("c1_legal", "legal and ethical issues in computing", {"ST4059CEM"}),
    _c1("c1_entrepreneur", "how do I start my own business",
        {"STA201IAE", "STA103IAE", "STA309IAE", "GUIDE-STARTUP"}),
    _c1("c1_grad", "how do I apply for a masters degree abroad",
        {"GUIDE-GRAD"}),
    _c1("c1_airoles", "will AI replace developers and what AI-era roles exist",
        {"GUIDE-AIROLES"}),
    _c1("c1_csai", "computer science with artificial intelligence programme",
        {"INFO-CSAI"}),
    _c1("c1_ehc", "ethical hacking and cybersecurity programme",
        {"INFO-EHC"}),
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
    # Clean queries (no bias - important for precision)
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
    # yield high jerk - these measured values ARE the thesis C3 baseline. ACT is
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
