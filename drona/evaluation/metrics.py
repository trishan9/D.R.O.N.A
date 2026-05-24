"""
Evaluation metrics for D.R.O.N.A. research contributions C1–C4.

All functions are pure (no side effects, no I/O) and take only Python
primitive types / numpy arrays so they are trivially testable.

Reference implementations:
  NDCG: Manning et al., "Introduction to Information Retrieval" §8.4
  MRR:  Voorhees, TREC-8 QA track, 1999
  F1:   Standard IR precision/recall
  Jerk: Hogan (2009), "Revisiting the minimum-jerk hypothesis" — used in C3
        gesture smoothness evaluation
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


# ── C1 — Retrieval metrics ─────────────────────────────────────────────────────

def dcg_at_k(relevance: list[float], k: int) -> float:
    """Discounted Cumulative Gain at k.

    Args:
        relevance: Ordered list of relevance scores for retrieved items.
                   1.0 = relevant, 0.0 = not relevant (binary or graded).
        k: Cutoff position.

    Returns:
        DCG@k score.
    """
    n = min(k, len(relevance))
    return sum(
        rel / math.log2(rank + 2)   # rank+2 because log base 2 of rank+1, rank is 0-indexed
        for rank, rel in enumerate(relevance[:n])
    )


def ndcg_at_k(relevance: list[float], k: int) -> float:
    """Normalised Discounted Cumulative Gain at k.

    Args:
        relevance: Ordered list of relevance scores for retrieved items.
        k: Cutoff position.

    Returns:
        NDCG@k in [0, 1]. Returns 0 if no relevant items exist.
    """
    actual_dcg = dcg_at_k(relevance, k)
    ideal_relevance = sorted(relevance, reverse=True)
    ideal_dcg = dcg_at_k(ideal_relevance, k)
    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg


def mrr(relevance: list[float]) -> float:
    """Mean Reciprocal Rank (for a single query).

    For a list of queries, average the result across queries.

    Args:
        relevance: Ordered list of binary relevance labels.

    Returns:
        1/rank of first relevant item, or 0 if none found.
    """
    for rank, rel in enumerate(relevance, start=1):
        if rel > 0:
            return 1.0 / rank
    return 0.0


def recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    """Recall at k — fraction of relevant items retrieved in top-k.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevant_ids: Set of all known relevant document IDs.
        k: Cutoff position.

    Returns:
        Recall@k in [0, 1]. Returns 0 if relevant_ids is empty.
    """
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)


def precision_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    """Precision at k.

    Args:
        retrieved_ids: Ordered retrieved IDs.
        relevant_ids: Set of relevant IDs.
        k: Cutoff.

    Returns:
        Precision@k in [0, 1].
    """
    if k == 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / k


def retrieval_metrics(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int = 5,
) -> dict[str, float]:
    """Compute a full retrieval metric bundle for one query.

    Returns:
        Dict with ndcg@k, mrr, recall@k, precision@k.
    """
    relevance = [1.0 if doc_id in relevant_ids else 0.0 for doc_id in retrieved_ids]
    return {
        f"ndcg@{k}": ndcg_at_k(relevance, k),
        "mrr":        mrr(relevance),
        f"recall@{k}": recall_at_k(retrieved_ids, relevant_ids, k),
        f"precision@{k}": precision_at_k(retrieved_ids, relevant_ids, k),
    }


def mean_metrics(metric_dicts: list[dict[str, float]]) -> dict[str, float]:
    """Average a list of per-query metric dicts (macro averaging)."""
    if not metric_dicts:
        return {}
    keys = metric_dicts[0].keys()
    return {
        key: sum(d[key] for d in metric_dicts) / len(metric_dicts)
        for key in keys
    }


# ── C2 — Bias detection metrics ───────────────────────────────────────────────

def precision_recall_f1(
    predicted: set[str],
    actual: set[str],
) -> dict[str, float]:
    """Compute precision, recall, and F1 for a set prediction.

    Args:
        predicted: Set of predicted labels/IDs.
        actual: Set of true labels/IDs.

    Returns:
        Dict with 'precision', 'recall', 'f1'.
    """
    if not predicted and not actual:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not predicted:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    if not actual:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0}

    tp = len(predicted & actual)
    precision = tp / len(predicted)
    recall = tp / len(actual)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def bias_detection_metrics(
    results: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Compute per-bias-type and macro-average P/R/F1.

    Args:
        results: List of dicts, each with:
            'predicted_biases': set[str]  (detected bias types)
            'actual_biases': set[str]     (ground-truth bias types)

    Returns:
        Dict mapping bias_type → {precision, recall, f1}, plus 'macro_avg'.
    """
    from drona.contracts import BiasFlag  # for the 6 valid bias types

    bias_types = [
        "availability_heuristic", "anchoring", "confirmation",
        "dunning_kruger", "loss_aversion", "consistency",
    ]

    per_type: dict[str, dict[str, float]] = {}
    for bt in bias_types:
        tp = fp = fn = 0
        for r in results:
            predicted = bt in r["predicted_biases"]
            actual = bt in r["actual_biases"]
            if predicted and actual:
                tp += 1
            elif predicted and not actual:
                fp += 1
            elif not predicted and actual:
                fn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        per_type[bt] = {"precision": precision, "recall": recall, "f1": f1,
                        "tp": tp, "fp": fp, "fn": fn}

    # Macro average (over bias types with at least one positive example)
    active = [v for k, v in per_type.items() if v["tp"] + v["fn"] > 0]
    if active:
        macro_p = sum(v["precision"] for v in active) / len(active)
        macro_r = sum(v["recall"] for v in active) / len(active)
        macro_f = sum(v["f1"] for v in active) / len(active)
    else:
        macro_p = macro_r = macro_f = 0.0

    per_type["macro_avg"] = {"precision": macro_p, "recall": macro_r, "f1": macro_f}
    return per_type


# ── C3 — Gesture smoothness metrics ───────────────────────────────────────────

def jerk_score(positions: list[np.ndarray], dt: float = 0.05) -> float:
    """Mean absolute jerk (third derivative of position).

    Lower jerk = smoother motion. Used to compare ACT vs keyframe baseline.

    Args:
        positions: Ordered list of joint position arrays (shape: DOF each).
        dt: Time step in seconds.

    Returns:
        Mean absolute jerk in rad/s³, averaged over joints. 0 if too few points.
    """
    if len(positions) < 4:
        return 0.0
    arr = np.stack(positions)   # (T, DOF)
    vel  = np.diff(arr,  n=1, axis=0) / dt
    acc  = np.diff(vel,  n=1, axis=0) / dt
    jerk = np.diff(acc,  n=1, axis=0) / dt
    return float(np.mean(np.abs(jerk)))


def path_length(positions: list[np.ndarray]) -> float:
    """Total Euclidean path length in joint space."""
    if len(positions) < 2:
        return 0.0
    arr = np.stack(positions)
    return float(np.sum(np.linalg.norm(np.diff(arr, axis=0), axis=1)))


def duration_error(actual_s: float, expected_s: float) -> float:
    """Absolute duration error in seconds."""
    return abs(actual_s - expected_s)


def gesture_metrics(
    positions: list[np.ndarray],
    actual_duration_s: float,
    expected_duration_s: float | None = None,
    dt: float = 0.05,
) -> dict[str, float]:
    """Bundle of gesture quality metrics for one execution."""
    result: dict[str, float] = {
        "jerk": jerk_score(positions, dt),
        "path_length": path_length(positions),
        "n_frames": float(len(positions)),
        "duration_s": actual_duration_s,
    }
    if expected_duration_s is not None:
        result["duration_error_s"] = duration_error(actual_duration_s, expected_duration_s)
    return result


# ── C4 — Stack / provenance metrics ───────────────────────────────────────────

def nepal_citation_ratio(
    responses: list[Any],  # list[AdvisingResponse]
) -> float:
    """Fraction of all citations that are Nepal-tier.

    Args:
        responses: List of AdvisingResponse objects.

    Returns:
        Ratio in [0, 1]. Returns 0 if no citations at all.
    """
    total = 0
    nepal = 0
    for r in responses:
        for pw in getattr(r, "pathways", []):
            for cit in getattr(pw, "citations", []):
                total += 1
                if getattr(cit.tier, "value", "") == "nepal":
                    nepal += 1
    return nepal / total if total > 0 else 0.0


def latency_stats(generation_times_ms: list[int]) -> dict[str, float]:
    """Compute latency percentiles from a list of generation times.

    Args:
        generation_times_ms: List of integer millisecond timings.

    Returns:
        Dict with mean, median, p90, p95, p99.
    """
    if not generation_times_ms:
        return {}
    arr = np.array(generation_times_ms, dtype=float)
    return {
        "mean_ms":   float(np.mean(arr)),
        "median_ms": float(np.median(arr)),
        "p90_ms":    float(np.percentile(arr, 90)),
        "p95_ms":    float(np.percentile(arr, 95)),
        "p99_ms":    float(np.percentile(arr, 99)),
        "min_ms":    float(np.min(arr)),
        "max_ms":    float(np.max(arr)),
    }
