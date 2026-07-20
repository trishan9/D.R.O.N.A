#!/usr/bin/env python3
"""
Compare bias detectors on the HELD-OUT v2 set: rules vs semantic vs hybrid.

This is the experiment behind the claim that a learned layer beats hand-written
patterns. All three are scored on the SAME untouched set (v2); the semantic
exemplars come from development data only (bank + v1), so this is a clean
train/test split rather than a self-report.

    python scripts/benchmark_bias_detectors.py
    python scripts/benchmark_bias_detectors.py --sweep   # threshold sweep (dev)

The threshold is chosen on DEVELOPMENT data (--sweep reports v1) and then applied
unchanged to v2. Picking it by looking at v2 would leak the test set.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drona.advising.bias_detector import BiasDetector  # noqa: E402
from drona.advising.semantic_bias import (  # noqa: E402
    DEFAULT_THRESHOLD,
    HybridBiasDetector,
    SemanticBiasDetector,
)
from drona.contracts import StudentProfile  # noqa: E402
from drona.evaluation.heldout_queries import HELDOUT_C2_QUERIES  # noqa: E402
from drona.evaluation.heldout_queries_v2 import HELDOUT_C2_QUERIES_V2  # noqa: E402
from drona.evaluation.metrics import bias_detection_metrics  # noqa: E402

REPORT = Path(__file__).resolve().parents[1] / "reports" / "bias_detector_comparison.json"


def score(detector, queries, profile) -> tuple[dict, dict, int]:
    results, fp = [], 0
    for q in queries:
        predicted = {f.bias_type for f in detector.detect(q.query_text, profile=profile)}
        actual = set(q.expected_biases)
        results.append({"predicted_biases": predicted, "actual_biases": actual})
        if not actual and predicted:
            fp += 1
    m = bias_detection_metrics(results)
    macro = m.pop("macro_avg")
    return macro, m, fp


class _UngroundedHybrid:
    """Ablation twin of RAGHybridBiasDetector with the span check switched off.

    Isolates what evidence grounding costs in recall and buys in precision, at
    the configuration that actually ships.
    """

    def __init__(self) -> None:
        from drona.advising.bias_detector import BiasDetector
        from drona.advising.rag_bias import RAGBiasDetector

        self._rules = BiasDetector()
        self._rag = RAGBiasDetector(require_grounding=False)

    def detect(self, query_text, profile=None):
        flags = list(self._rules.detect(query_text, profile=profile))
        seen = {f.bias_type for f in flags}
        for f in self._rag.detect(query_text, profile=profile):
            if f.bias_type not in seen:
                flags.append(f)
                seen.add(f.bias_type)
        return flags


def main() -> int:
    profile = StudentProfile(session_id="bench")
    v2 = HELDOUT_C2_QUERIES_V2
    n_neutral = sum(1 for q in v2 if not q.expected_biases)

    # Threshold selection uses a proper 3-way split:
    #   FIT   exemplars = C2 development bank only
    #   TUNE  threshold  = held-out v1 (not in the exemplar bank)
    #   TEST  final      = held-out v2 (untouched by either)
    # Scoring v1 with v1 in the bank would be leakage - every query would match
    # itself at cosine 1.0 and recall would be a meaningless 1.000.
    if "--sweep" in sys.argv:
        from drona.advising.semantic_bias import _Exemplar
        from drona.evaluation.queries import C2_QUERIES

        bank_only = [
            _Exemplar(text=q.query_text, bias_type=b)
            for q in C2_QUERIES
            for b in q.expected_biases
        ]
        print(f"threshold sweep - FIT on the C2 bank only ({len(bank_only)} exemplars), "
              f"TUNE on v1 ({len(HELDOUT_C2_QUERIES)} items). v2 is never touched.")
        for t in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70):
            det = SemanticBiasDetector(threshold=t, exemplars=bank_only)
            macro, _, fp = score(det, HELDOUT_C2_QUERIES, profile)
            print(f"  thr={t:.2f}  P={macro['precision']:.3f} "
                  f"R={macro['recall']:.3f} F1={macro['f1']:.3f}  fp={fp}")
        return 0

    detectors = {
        "rules (regex)": BiasDetector(),
        f"semantic (kNN, thr={DEFAULT_THRESHOLD})": SemanticBiasDetector(),
        "hybrid (rules ∪ semantic)": HybridBiasDetector(),
    }
    # LLM detection is opt-in: it needs a served model and is orders of
    # magnitude slower than the other two (one generation per query).
    if "--llm" in sys.argv:
        from drona.advising.llm_bias import LLMBiasDetector, LLMHybridBiasDetector
        from drona.advising.rag_bias import RAGBiasDetector, RAGHybridBiasDetector

        detectors["llm (zero-shot)"] = LLMBiasDetector()
        detectors["hybrid (rules ∪ llm)"] = LLMHybridBiasDetector()
        # Ablation: same retrieved few-shot prompt, with the evidence-span check
        # disabled, isolating what grounding alone contributes to precision.
        detectors["rag-llm (few-shot, NO grounding)"] = RAGBiasDetector(
            require_grounding=False
        )
        detectors["rag-llm (few-shot + grounding)"] = RAGBiasDetector()
        detectors["hybrid (rules ∪ rag-llm, NO grounding)"] = _UngroundedHybrid()
        detectors["hybrid (rules ∪ rag-llm) [PRODUCTION]"] = RAGHybridBiasDetector()

    print("=" * 74)
    print(f"Bias detector comparison - HELD-OUT v2 ({len(v2)} items, {n_neutral} neutral)")
    print("semantic exemplars: development data only (C2 bank + v1)")
    print("=" * 74)

    out: dict = {"set": "heldout_v2", "n_items": len(v2),
                 "n_neutral": n_neutral, "detectors": {}}
    for name, det in detectors.items():
        t0 = time.time()
        macro, per_type, fp = score(det, v2, profile)
        elapsed = time.time() - t0
        out["detectors"][name] = {
            "macro": macro, "per_type": per_type,
            "false_positives": fp, "seconds": round(elapsed, 1),
        }
        print(f"\n{name}")
        print(f"  MACRO  P={macro['precision']:.3f}  R={macro['recall']:.3f}  "
              f"F1={macro['f1']:.3f}   false-pos={fp}/{n_neutral}   ({elapsed:.1f}s)")
        for bias, m in sorted(per_type.items()):
            print(f"     {bias:26} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
