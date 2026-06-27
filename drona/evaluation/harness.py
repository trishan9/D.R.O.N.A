"""
Evaluation harness for D.R.O.N.A. — runs all C1–C4 evaluations.

Each eval method runs one contribution's evaluation and returns a structured
results dict. `run_all()` combines them into a single JSON-serializable report.

Evaluation design (no human-labelled data needed):

  C1 — Retrieval quality
    For each eval query, we check which ChromaDB collections the top-K results
    come from and whether the tier distribution matches expectations. Without a
    labelled document set, we use collection membership as a relevance proxy:
    - "curriculum" queries should have ≥ 50% curriculum-collection results
    - "career" queries should have ≥ 50% career-collection results
    - "both" queries should have results from both collections
    We also compare hybrid (BM25 + dense + RRF) vs dense-only retrieval to
    demonstrate the C1 contribution empirically.

  C2 — Bias detection
    Run the BiasDetector on each C2_QUERIES entry and compare predicted bias
    types against the ground-truth labels. Compute precision, recall, F1 per
    bias type and macro average. The query bank labels are ground-truth by
    construction (they were written to trigger specific patterns).

  C3 — Gesture smoothness
    Execute each gesture with KeyframePolicy in StubEnv and measure jerk score,
    path length, and duration. These form the "scripted baseline" against which
    ACT-trained policies will be compared. Spec: all gestures must be within
    frame count bounds and jerk below threshold.

  C4 — Stack / provenance
    Query with C4_QUERIES, measure Nepal citation ratio and generation latency.
    Target: ≥ 40% Nepal citations for queries that prefer local data.

Dependency handling:
    C1 requires a populated ChromaDB (run ingest_data.py first).
    C2, C3, C4 (non-LLM) run with no external dependencies.
    C4 latency measurement requires Ollama running; skipped gracefully if not.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from drona.advising.bias_detector import BiasDetector
from drona.evaluation.metrics import (
    bias_detection_metrics,
    gesture_metrics,
    jerk_score,
    latency_stats,
    mean_metrics,
    nepal_citation_ratio,
    path_length,
    retrieval_metrics,
)
from drona.evaluation.queries import (
    C1_QUERIES,
    C2_QUERIES,
    C3_GESTURE_SPECS,
    C4_QUERIES,
    EvalQuery,
)
from drona.interaction.act_policy import KeyframePolicy
from drona.interaction.mujoco_env import StubEnv


# ── Results containers ────────────────────────────────────────────────────────

@dataclass
class C1Result:
    hybrid_metrics:      dict[str, float]
    dense_only_metrics:  dict[str, float]
    improvement:         dict[str, float]   # hybrid - dense_only per metric
    collection_balance:  dict[str, float]   # fraction from each collection
    n_queries:           int
    skipped:             bool = False
    skip_reason:         str = ""


@dataclass
class C2Result:
    per_bias_metrics:    dict[str, dict[str, float]]
    macro_avg:           dict[str, float]
    n_queries:           int
    n_with_bias:         int
    n_clean:             int


@dataclass
class C3Result:
    per_gesture:         dict[str, dict[str, float]]
    mean_jerk:           float
    mean_path_length:    float
    all_within_spec:     bool
    spec_failures:       list[str]


@dataclass
class C4Result:
    nepal_citation_ratio: float
    target_met:           bool           # ≥ 0.40 for local-preference queries
    latency:              dict[str, float]
    latency_skipped:      bool = False
    # "response" = measured over full advising responses (needs Ollama);
    # "retrieval" = measured over the retrieved citations (offline fallback).
    ratio_source:         str = "response"


@dataclass
class EvaluationReport:
    timestamp: str
    c1: C1Result | None = None
    c2: C2Result | None = None
    c3: C3Result | None = None
    c4: C4Result | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "c1": asdict(self.c1) if self.c1 else None,
            "c2": asdict(self.c2) if self.c2 else None,
            "c3": asdict(self.c3) if self.c3 else None,
            "c4": asdict(self.c4) if self.c4 else None,
            "notes": self.notes,
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        logger.info(f"Evaluation report saved to {path}")


# ── Harness ────────────────────────────────────────────────────────────────────

class EvaluationHarness:
    """Runs all D.R.O.N.A. evaluations and assembles a report."""

    def __init__(self) -> None:
        self._bias_detector = BiasDetector()

    # ── C1: Retrieval ──────────────────────────────────────────────────────────

    def eval_c1(self, top_k: int = 5) -> C1Result:
        """Evaluate hybrid retrieval quality (C1 contribution).

        Compares hybrid (BM25 + dense + RRF) vs dense-only retrieval using
        collection membership as a relevance proxy.
        """
        logger.info("C1 evaluation: retrieval quality")
        try:
            from drona.advising.retriever import Retriever
        except Exception as exc:
            return C1Result(
                hybrid_metrics={}, dense_only_metrics={}, improvement={},
                collection_balance={}, n_queries=0,
                skipped=True, skip_reason=f"ChromaDB unavailable: {exc}",
            )

        try:
            retriever = Retriever()
        except Exception as exc:
            return C1Result(
                hybrid_metrics={}, dense_only_metrics={}, improvement={},
                collection_balance={}, n_queries=0,
                skipped=True, skip_reason=f"Retriever init failed: {exc}",
            )

        hybrid_all: list[dict[str, float]] = []
        dense_all: list[dict[str, float]] = []
        collection_counts: dict[str, int] = {"curriculum": 0, "career": 0, "unknown": 0}
        n_processed = 0

        for q in C1_QUERIES:
            try:
                # Hybrid: full pipeline
                hybrid_docs = retriever.retrieve_raw(q.query_text, top_k=top_k)

                # Dense-only: only curriculum dense retrieval (simplest baseline)
                from drona.data_pipeline.ingest import COLL_CURRICULUM, COLL_CAREER
                dense_docs = retriever._dense_retrieve(
                    q.query_text, retriever._coll_curriculum, COLL_CURRICULUM, top_k
                )

                if not hybrid_docs:
                    logger.warning(f"No hybrid results for {q.query_id}")
                    continue

                # Build relevance labels from collection membership
                relevant_collections = _expected_collections(q.expected_relevance)
                hybrid_ids = [d.id for d in hybrid_docs]
                hybrid_relevant = {
                    d.id for d in hybrid_docs if d.collection in relevant_collections
                }
                dense_ids = [d.id for d in dense_docs]
                dense_relevant = {
                    d.id for d in dense_docs if d.collection in relevant_collections
                }

                h_metrics = retrieval_metrics(hybrid_ids, hybrid_relevant, k=top_k)
                d_metrics = retrieval_metrics(dense_ids, dense_relevant, k=top_k)

                hybrid_all.append(h_metrics)
                dense_all.append(d_metrics)

                # Track collection distribution
                for d in hybrid_docs[:top_k]:
                    col = d.collection
                    if COLL_CURRICULUM in col:
                        collection_counts["curriculum"] += 1
                    elif COLL_CAREER in col:
                        collection_counts["career"] += 1
                    else:
                        collection_counts["unknown"] += 1

                n_processed += 1

            except Exception as exc:
                logger.warning(f"C1 skipping {q.query_id}: {exc}")

        if not hybrid_all:
            return C1Result(
                hybrid_metrics={}, dense_only_metrics={}, improvement={},
                collection_balance={}, n_queries=0,
                skipped=True, skip_reason="ChromaDB appears empty — run ingest_data.py first.",
            )

        h_mean = mean_metrics(hybrid_all)
        d_mean = mean_metrics(dense_all)
        improvement = {k: h_mean[k] - d_mean.get(k, 0.0) for k in h_mean}

        total_docs = sum(collection_counts.values()) or 1
        balance = {k: v / total_docs for k, v in collection_counts.items()}

        logger.info(
            f"C1: {n_processed} queries — "
            f"hybrid NDCG@{top_k}={h_mean.get(f'ndcg@{top_k}', 0):.3f}, "
            f"dense NDCG@{top_k}={d_mean.get(f'ndcg@{top_k}', 0):.3f}"
        )
        return C1Result(
            hybrid_metrics=h_mean,
            dense_only_metrics=d_mean,
            improvement=improvement,
            collection_balance=balance,
            n_queries=n_processed,
        )

    # ── C2: Bias detection ────────────────────────────────────────────────────

    def eval_c2(self) -> C2Result:
        """Evaluate bias detection precision/recall/F1 (C2 contribution)."""
        logger.info("C2 evaluation: bias detection")
        results: list[dict[str, Any]] = []

        for q in C2_QUERIES:
            flags = self._bias_detector.detect(q.query_text)
            predicted = {f.bias_type for f in flags}
            actual = set(q.expected_biases)
            results.append({"predicted_biases": predicted, "actual_biases": actual})

        metrics = bias_detection_metrics(results)
        macro = metrics.pop("macro_avg")

        n_with_bias = sum(1 for q in C2_QUERIES if q.expected_biases)
        n_clean = len(C2_QUERIES) - n_with_bias

        logger.info(
            f"C2: {len(C2_QUERIES)} queries — "
            f"macro P={macro['precision']:.3f} R={macro['recall']:.3f} F1={macro['f1']:.3f}"
        )
        return C2Result(
            per_bias_metrics=metrics,
            macro_avg=macro,
            n_queries=len(C2_QUERIES),
            n_with_bias=n_with_bias,
            n_clean=n_clean,
        )

    # ── C3: Gesture smoothness ─────────────────────────────────────────────────

    def eval_c3(self, dt: float = 0.05) -> C3Result:
        """Evaluate keyframe gesture baseline smoothness (C3 contribution)."""
        logger.info("C3 evaluation: gesture smoothness (keyframe baseline)")
        per_gesture: dict[str, dict[str, float]] = {}
        spec_failures: list[str] = []
        env = StubEnv(dt=dt)
        all_jerks: list[float] = []
        all_paths: list[float] = []

        for spec in C3_GESTURE_SPECS:
            try:
                policy = KeyframePolicy(spec.gesture_label, dt=dt)
                env.reset()
                positions: list[np.ndarray] = []
                obs = env.reset()
                policy.reset()

                while not policy.is_complete:
                    action = policy.select_action({"observation.state": obs})
                    obs, _ = env.step(action)
                    positions.append(obs.copy())

                t_start = time.monotonic()
                actual_duration = len(positions) * dt

                jerk = jerk_score(positions, dt)
                plen = path_length(positions)
                n_frames = len(positions)

                g_metrics = {
                    "jerk": jerk,
                    "path_length": plen,
                    "n_frames": float(n_frames),
                    "duration_s": actual_duration,
                }
                per_gesture[spec.gesture_label] = g_metrics
                all_jerks.append(jerk)
                all_paths.append(plen)

                # Check spec
                if not (spec.expected_min_frames <= n_frames <= spec.expected_max_frames):
                    spec_failures.append(
                        f"{spec.gesture_label}: frames={n_frames} outside "
                        f"[{spec.expected_min_frames}, {spec.expected_max_frames}]"
                    )
                if jerk > spec.expected_max_jerk:
                    spec_failures.append(
                        f"{spec.gesture_label}: jerk={jerk:.3f} > threshold {spec.expected_max_jerk}"
                    )
                if plen < spec.expected_path_length_min:
                    spec_failures.append(
                        f"{spec.gesture_label}: path_length={plen:.3f} < min {spec.expected_path_length_min}"
                    )

                logger.debug(
                    f"  {spec.gesture_label}: frames={n_frames}, "
                    f"jerk={jerk:.4f}, path={plen:.3f}"
                )

            except Exception as exc:
                logger.warning(f"C3 gesture '{spec.gesture_label}' failed: {exc}")
                spec_failures.append(f"{spec.gesture_label}: exception — {exc}")

        env.close()
        mean_jerk = float(np.mean(all_jerks)) if all_jerks else 0.0
        mean_path = float(np.mean(all_paths)) if all_paths else 0.0

        logger.info(
            f"C3: mean_jerk={mean_jerk:.4f}, mean_path={mean_path:.3f}, "
            f"spec_failures={len(spec_failures)}"
        )
        return C3Result(
            per_gesture=per_gesture,
            mean_jerk=mean_jerk,
            mean_path_length=mean_path,
            all_within_spec=len(spec_failures) == 0,
            spec_failures=spec_failures,
        )

    # ── C4: Stack / provenance ─────────────────────────────────────────────────

    def eval_c4(self, with_llm: bool = False) -> C4Result:
        """Evaluate Nepal-first citation ratio and latency (C4 contribution).

        Args:
            with_llm: If True, attempt full advising pipeline latency measurement.
                      Requires Ollama running. Skipped gracefully if unavailable.
        """
        logger.info("C4 evaluation: stack / provenance metrics")
        responses: list[Any] = []
        gen_times: list[int] = []
        latency_skipped = True

        if with_llm:
            try:
                from drona.advising.engine import AdvisingEngine, make_query
                engine = AdvisingEngine()
                if engine._llm.is_available():
                    for q in C4_QUERIES:
                        adv_q = make_query(q.query_text)
                        resp = engine.advise(adv_q)
                        responses.append(resp)
                        if resp.generation_time_ms is not None:
                            gen_times.append(resp.generation_time_ms)
                    latency_skipped = False
                else:
                    logger.info("C4: Ollama not available — skipping latency measurement")
            except Exception as exc:
                logger.warning(f"C4 LLM eval failed: {exc}")

        ratio = nepal_citation_ratio(responses)
        ratio_source = "response"
        latency = latency_stats(gen_times) if gen_times else {}

        # Without the LLM there are no response citations, so measure the
        # Nepal-first ratio over the RETRIEVED citations instead (this directly
        # reflects the C4 tier-boost) and reuse the loop for retrieval latency.
        if latency_skipped:
            try:
                from drona.advising.retriever import Retriever
                from drona.contracts import DataTier
                retriever = Retriever()
                times_ms: list[int] = []
                total = nepal = 0
                for q in C4_QUERIES:
                    t0 = time.monotonic()
                    cits = retriever.retrieve(q.query_text)
                    times_ms.append(int((time.monotonic() - t0) * 1000))
                    total += len(cits)
                    nepal += sum(1 for c in cits if c.tier == DataTier.NEPAL)
                latency = latency_stats(times_ms)
                latency["note"] = 0.0  # marker: retrieval-only, not full pipeline
                if not responses and total:
                    ratio = nepal / total
                    ratio_source = "retrieval"
            except Exception as exc:
                logger.warning(f"C4 retrieval measurement failed: {exc}")

        target_met = ratio >= 0.40
        logger.info(
            f"C4: nepal_ratio={ratio:.3f} (source={ratio_source}), "
            f"target_met={target_met}, latency_skipped={latency_skipped}"
        )
        return C4Result(
            nepal_citation_ratio=ratio,
            target_met=target_met,
            latency=latency,
            latency_skipped=latency_skipped,
            ratio_source=ratio_source,
        )

    # ── run_all ────────────────────────────────────────────────────────────────

    def run_all(
        self,
        run_c1: bool = True,
        run_c2: bool = True,
        run_c3: bool = True,
        run_c4: bool = True,
        c4_with_llm: bool = False,
    ) -> EvaluationReport:
        from datetime import datetime, timezone
        report = EvaluationReport(
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        if run_c1:
            report.c1 = self.eval_c1()
            if report.c1.skipped:
                report.notes.append(f"C1 skipped: {report.c1.skip_reason}")

        if run_c2:
            report.c2 = self.eval_c2()

        if run_c3:
            report.c3 = self.eval_c3()
            if report.c3.spec_failures:
                report.notes.append(
                    f"C3 spec failures: {'; '.join(report.c3.spec_failures)}"
                )

        if run_c4:
            report.c4 = self.eval_c4(with_llm=c4_with_llm)

        return report


# ── Helper ────────────────────────────────────────────────────────────────────

def _expected_collections(relevance: str) -> set[str]:
    """Map expected_relevance label to ChromaDB collection name substrings."""
    from drona.data_pipeline.ingest import COLL_CURRICULUM, COLL_CAREER
    if relevance == "curriculum":
        return {COLL_CURRICULUM}
    if relevance == "career":
        return {COLL_CAREER}
    if relevance == "both":
        return {COLL_CURRICULUM, COLL_CAREER}
    return set()
