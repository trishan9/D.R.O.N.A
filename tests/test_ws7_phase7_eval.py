"""
Phase 7 evaluation-harness tests:
  - bias-MITIGATION metrics (diversity, hedging, counter-rec, refusal, tiers)
  - scipy.stats comparison harness (Welch / Mann-Whitney / Cohen's d / bootstrap)
  - Ragas lexical-proxy fallback
  - citation-verification aggregation
"""

from __future__ import annotations

import numpy as np
import pytest

from drona.contracts import (
    AdvisingResponse,
    BiasFlag,
    DataTier,
    PathwayRecommendation,
    RetrievalCitation,
)
from drona.evaluation.bias_mitigation import (
    evaluate_bias_mitigation,
    hedge_frequency,
    pathway_diversity,
    tier_citation_distribution,
)
from drona.evaluation.citation_eval import evaluate_citations
from drona.evaluation.ragas_harness import evaluate_rag
from drona.evaluation.stats import compare_conditions, paired_comparison


# ── Fixtures / builders ───────────────────────────────────────────────────────

def _cit(source_id: str, tier: DataTier, score: float = 0.8) -> RetrievalCitation:
    return RetrievalCitation(
        source_type="job_posting",
        source_id=source_id,
        tier=tier,
        excerpt=f"excerpt for {source_id}",
        relevance_score=score,
    )


def _pathway(title: str, citations, confidence="medium", rationale="you might consider this option") -> PathwayRecommendation:
    return PathwayRecommendation(
        pathway_title=title,
        rationale=rationale,
        citations=list(citations),
        confidence=confidence,
    )


def _response(pathways, *, refusal=False, summary="You could explore several options.",
              bias_flags=None) -> AdvisingResponse:
    return AdvisingResponse(
        query_id="q1",
        summary=summary,
        pathways=list(pathways),
        bias_flags=list(bias_flags or []),
        refusal=refusal,
        speak_text=summary,
    )


def _rich_response() -> AdvisingResponse:
    p1 = _pathway("Backend Developer", [_cit("np1", DataTier.NEPAL), _cit("np2", DataTier.NEPAL)], "high")
    p2 = _pathway("Data Analyst", [_cit("intl1", DataTier.INTERNATIONAL)], "low",
                  rationale="alternatively this might suit you, however it depends")
    flag = BiasFlag(bias_type="anchoring", detected_signal="only X", mitigation_applied="offered alternatives")
    return _response([p1, p2], bias_flags=[flag])


# ── Bias mitigation ───────────────────────────────────────────────────────────

def test_pathway_diversity_counts_distinct_titles():
    r = _rich_response()
    assert pathway_diversity(r) == 2.0


def test_pathway_diversity_refusal_is_zero():
    r = _response([], refusal=True, summary="I can't answer confidently.")
    assert pathway_diversity(r) == 0.0


def test_hedge_frequency_in_unit_range_and_detects_hedges():
    r = _rich_response()
    h = hedge_frequency(r)
    assert 0.0 < h <= 1.0


def test_tier_distribution_sums_to_one():
    r = _rich_response()
    dist = tier_citation_distribution(r)
    assert pytest.approx(sum(dist.values()), abs=1e-9) == 1.0
    assert dist["nepal"] > dist["international"]  # 2 nepal vs 1 intl


def test_evaluate_bias_mitigation_aggregate():
    responses = [_rich_response(), _rich_response()]
    report = evaluate_bias_mitigation(responses)
    assert report.n_responses == 2
    assert report.mean_pathway_diversity == 2.0
    assert report.multi_pathway_rate == 1.0
    assert report.refusal_rate == 0.0
    assert report.bias_flag_coverage == 1.0
    assert report.nepal_first_rate == 1.0  # nepal is top-cited tier in both


def test_evaluate_bias_mitigation_empty():
    report = evaluate_bias_mitigation([])
    assert report.n_responses == 0
    assert report.mean_pathway_diversity == 0.0


def test_counter_recommendation_detected_via_low_confidence():
    report = evaluate_bias_mitigation([_rich_response()])
    # rich response has a low-confidence alternative → counts as counter-rec
    assert report.counter_recommendation_rate == 1.0


# ── Stats harness ─────────────────────────────────────────────────────────────

def test_compare_conditions_detects_clear_difference():
    rng = np.random.default_rng(0)
    a = rng.normal(10.0, 1.0, size=30)   # "traditional" higher jerk
    b = rng.normal(6.0, 1.0, size=30)    # "DRONA/ACT" lower jerk
    res = compare_conditions(a, b, "traditional", "drona")
    assert res.significant
    assert res.mean_difference > 0
    assert res.effect_magnitude in {"medium", "large"}
    assert res.ci95_low <= res.mean_difference <= res.ci95_high
    assert "traditional" in res.summary()


def test_compare_conditions_no_difference_not_significant():
    rng = np.random.default_rng(1)
    a = rng.normal(5.0, 1.0, size=40)
    b = rng.normal(5.0, 1.0, size=40)
    res = compare_conditions(a, b)
    assert not res.significant
    assert res.effect_magnitude == "negligible"


def test_compare_conditions_requires_min_samples():
    with pytest.raises(ValueError):
        compare_conditions([1.0], [2.0, 3.0])


def test_paired_comparison_runs():
    before = [5, 6, 7, 8, 9]
    after = [6, 7, 8, 9, 10]
    res = paired_comparison(before, after)
    assert res["n_pairs"] == 5
    assert res["mean_change"] == pytest.approx(1.0)


# ── Ragas proxy ───────────────────────────────────────────────────────────────

def test_ragas_lexical_proxy_scores():
    samples = [
        {
            "question": "What software jobs exist in Kathmandu?",
            "answer": "Several software jobs in Kathmandu exist at local companies.",
            "contexts": ["Software developer jobs in Kathmandu at Leapfrog and F1Soft."],
            "ground_truth": "Kathmandu has software developer jobs.",
        }
    ]
    report = evaluate_rag(samples, force_proxy=True)
    assert report.backend == "lexical_proxy"
    assert report.n_samples == 1
    assert 0.0 <= report.faithfulness <= 1.0
    assert report.answer_relevancy > 0.0
    assert report.context_precision > 0.0


def test_ragas_empty_samples():
    report = evaluate_rag([])
    assert report.n_samples == 0


# ── Citation eval ─────────────────────────────────────────────────────────────

def test_citation_eval_all_grounded():
    retrieved = [_cit("np1", DataTier.NEPAL), _cit("np2", DataTier.NEPAL)]
    r = _response([_pathway("Backend", [retrieved[0]])])
    report = evaluate_citations([(r, retrieved)])
    assert report.grounded_pathway_rate == 1.0
    assert report.hallucinated_citation_rate == 0.0
    assert report.fully_grounded_response_rate == 1.0


def test_citation_eval_detects_hallucination():
    retrieved = [_cit("real1", DataTier.NEPAL)]
    # pathway cites a source NOT in the retrieved set
    r = _response([_pathway("Ghost", [_cit("fake1", DataTier.INTERNATIONAL)])])
    report = evaluate_citations([(r, retrieved)])
    assert report.hallucinated_citation_rate == 1.0
    assert report.grounded_pathway_rate == 0.0
    assert report.fully_grounded_response_rate == 0.0


def test_citation_eval_empty():
    report = evaluate_citations([])
    assert report.n_responses == 0
