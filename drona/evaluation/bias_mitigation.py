"""
Custom bias-MITIGATION metrics for D.R.O.N.A. (proposal §Cognitive Biases).

These are distinct from the bias *detection* P/R/F1 in ``metrics.py``: detection
measures "did we spot the bias in the question?", whereas these measure "did the
RESPONSE actually counter it?". They operationalise the proposal's claim that
D.R.O.N.A. mitigates - not just flags - cognitive bias.

All functions are pure and operate on ``AdvisingResponse`` objects (or anything
duck-typed with the same fields), so they work identically on live responses, on
a recorded eval set, or on responses replayed from a rosbag.

Metric → bias it targets:
  pathway_diversity        → availability heuristic / anchoring (one-option fixation)
  hedge_frequency          → Dunning–Kruger / overconfidence (calibrated uncertainty)
  counter_recommendation_rate → confirmation bias (offers the non-obvious option)
  refusal_rate             → hallucination / overreach (honest "I don't know")
  tier_citation_distribution → availability of *local* evidence (Nepal-first, C4)
  bias_flag_coverage       → transparency (named + mitigated, not silent)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

# Hedging language signals calibrated uncertainty rather than false confidence.
# Grounded in Tversky & Kahneman 1974 (overconfidence) - the response should not
# assert single-answer certainty.
_HEDGE_TERMS = (
    "may", "might", "could", "consider", "depends", "one option", "alternatively",
    "however", "on the other hand", "it's worth", "you might", "not the only",
    "trade-off", "tradeoff", "uncertain", "varies", "explore", "tends to",
)


def _iter_pathways(response: Any) -> list[Any]:
    return list(getattr(response, "pathways", []) or [])


# ── Per-response metrics ──────────────────────────────────────────────────────

def pathway_diversity(response: Any) -> float:
    """Number of distinct pathways surfaced (anti single-option anchoring).

    Returns the count as a float so it averages cleanly across responses. A
    refusal contributes 0. The proposal's anti-anchoring design mandates >1.
    """
    if getattr(response, "refusal", False):
        return 0.0
    titles = {p.pathway_title.strip().lower() for p in _iter_pathways(response)}
    return float(len(titles))


def hedge_frequency(response: Any) -> float:
    """Fraction of hedge terms present in the spoken + summary text.

    Normalised to [0, 1] by the size of the hedge lexicon, so it is comparable
    across responses of different lengths. Higher = more calibrated language.
    """
    text = " ".join(
        [
            getattr(response, "summary", "") or "",
            getattr(response, "speak_text", "") or "",
            *[getattr(p, "rationale", "") or "" for p in _iter_pathways(response)],
        ]
    ).lower()
    if not text.strip():
        return 0.0
    hits = sum(1 for term in _HEDGE_TERMS if term in text)
    return hits / len(_HEDGE_TERMS)


def has_counter_recommendation(response: Any, declared_interests: Iterable[str] = ()) -> bool:
    """True if the response offers a pathway that diverges from the obvious pick.

    Operationalised two ways (either qualifies):
      1. Multiple pathways with at least two distinct confidence levels OR a
         non-"high" pathway present (i.e. it didn't just serve one confident
         answer), or
      2. A pathway whose text shares no token with the declared interests
         (a genuine alternative to what the student already leans toward).
    """
    pathways = _iter_pathways(response)
    if len(pathways) < 2:
        return False

    confidences = {getattr(p, "confidence", "medium") for p in pathways}
    if len(confidences) >= 2 or any(c != "high" for c in confidences):
        offered_alternative = True
    else:
        offered_alternative = False

    interests = [i.lower() for i in declared_interests if i]
    if interests:
        for p in pathways:
            hay = (
                getattr(p, "pathway_title", "")
                + " "
                + getattr(p, "rationale", "")
            ).lower()
            if not any(i in hay for i in interests):
                return True
    return offered_alternative


def tier_citation_distribution(response: Any) -> dict[str, float]:
    """Fraction of citations per data tier (nepal/regional/international/synthetic)."""
    counts: Counter[str] = Counter()
    for p in _iter_pathways(response):
        for c in getattr(p, "citations", []) or []:
            tier = getattr(c.tier, "value", None) or str(c.tier)
            counts[tier] += 1
    total = sum(counts.values())
    if total == 0:
        return {}
    return {tier: n / total for tier, n in counts.items()}


# ── Aggregate report over a set of responses ──────────────────────────────────

@dataclass
class BiasMitigationReport:
    """Aggregate bias-mitigation metrics across a response set."""

    n_responses: int
    mean_pathway_diversity: float
    multi_pathway_rate: float          # fraction of non-refusal responses with >1 pathway
    mean_hedge_frequency: float
    counter_recommendation_rate: float
    refusal_rate: float
    bias_flag_coverage: float          # fraction of responses carrying ≥1 bias flag
    tier_citation_distribution: dict[str, float] = field(default_factory=dict)
    nepal_first_rate: float = 0.0      # fraction where nepal is the top-cited tier

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_bias_mitigation(
    responses: list[Any],
    declared_interests_per_response: list[list[str]] | None = None,
) -> BiasMitigationReport:
    """Compute the aggregate bias-mitigation report for a list of responses.

    Args:
        responses: AdvisingResponse-like objects.
        declared_interests_per_response: optional per-response declared interests
            (same length as ``responses``) used by the counter-recommendation
            metric. If omitted, the confidence-spread heuristic is used.
    """
    n = len(responses)
    if n == 0:
        return BiasMitigationReport(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, {}, 0.0)

    interests = declared_interests_per_response or [[] for _ in responses]

    diversities = [pathway_diversity(r) for r in responses]
    non_refusals = [r for r in responses if not getattr(r, "refusal", False)]
    multi = sum(1 for r in non_refusals if pathway_diversity(r) > 1)
    hedges = [hedge_frequency(r) for r in responses]
    counters = sum(
        1 for r, ints in zip(responses, interests) if has_counter_recommendation(r, ints)
    )
    refusals = sum(1 for r in responses if getattr(r, "refusal", False))
    flagged = sum(1 for r in responses if getattr(r, "bias_flags", None))

    # Aggregate tier distribution across all citations.
    agg: Counter[str] = Counter()
    nepal_first = 0
    for r in responses:
        dist = tier_citation_distribution(r)
        for tier, frac in dist.items():
            agg[tier] += frac
        if dist and max(dist, key=dist.get) == "nepal":
            nepal_first += 1
    agg_total = sum(agg.values())
    tier_dist = {t: v / agg_total for t, v in agg.items()} if agg_total else {}

    return BiasMitigationReport(
        n_responses=n,
        mean_pathway_diversity=sum(diversities) / n,
        multi_pathway_rate=(multi / len(non_refusals)) if non_refusals else 0.0,
        mean_hedge_frequency=sum(hedges) / n,
        counter_recommendation_rate=counters / n,
        refusal_rate=refusals / n,
        bias_flag_coverage=flagged / n,
        tier_citation_distribution=tier_dist,
        nepal_first_rate=nepal_first / n,
    )
