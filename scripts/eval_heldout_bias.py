#!/usr/bin/env python3
"""
Score the bias detector on the HELD-OUT set (drona/evaluation/heldout_queries.py).

This is the generalisation number for the dissertation. The development bank in
queries.py was used while tuning the detector's patterns, so its macro-F1 measures
fit, not generalisation. This set was written without consulting those patterns.

RULE: do not "fix" the detector in response to this output. Doing so converts the
held-out set into a second development set and the number stops meaning anything.
Report it as it is - a lower honest number is stronger evidence than a perfect
self-tuned one.

    python scripts/eval_heldout_bias.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drona.advising.bias_detector import BiasDetector  # noqa: E402
from drona.contracts import StudentProfile  # noqa: E402
from drona.evaluation.heldout_queries import HELDOUT_C2_QUERIES  # noqa: E402
from drona.evaluation.metrics import bias_detection_metrics  # noqa: E402

REPORT = Path(__file__).resolve().parents[1] / "reports" / "heldout_bias_report.json"


def main() -> int:
    det = BiasDetector()
    profile = StudentProfile(session_id="heldout-eval")

    results: list[dict] = []
    misses: list[tuple[str, set[str], set[str]]] = []
    false_pos: list[tuple[str, set[str]]] = []

    for q in HELDOUT_C2_QUERIES:
        predicted = {f.bias_type for f in det.detect(q.query_text, profile=profile)}
        actual = set(q.expected_biases)
        results.append({"predicted_biases": predicted, "actual_biases": actual})
        if actual - predicted:
            misses.append((q.query_text, actual, predicted))
        if not actual and predicted:
            false_pos.append((q.query_text, predicted))

    metrics = bias_detection_metrics(results)
    macro = metrics.pop("macro_avg")

    n_biased = sum(1 for q in HELDOUT_C2_QUERIES if q.expected_biases)
    n_neutral = len(HELDOUT_C2_QUERIES) - n_biased

    print("=" * 72)
    print("HELD-OUT bias detection (detector NOT tuned on these)")
    print("=" * 72)
    print(f"  items: {len(HELDOUT_C2_QUERIES)}  ({n_biased} biased, {n_neutral} neutral)")
    print()
    for name, m in sorted(metrics.items()):
        print(f"    {name:26} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}")
    print()
    print(f"  MACRO  P={macro['precision']:.3f}  R={macro['recall']:.3f}  F1={macro['f1']:.3f}")
    print(f"  false positives on neutral controls: {len(false_pos)}/{n_neutral}")

    if misses:
        print(f"\n  MISSED ({len(misses)}) - kept visible on purpose, not patched away:")
        for text, actual, pred in misses:
            print(f"    · expected {sorted(actual)} got {sorted(pred) or '[]'}")
            print(f"      \"{text[:78]}\"")
    if false_pos:
        print(f"\n  FALSE POSITIVES ({len(false_pos)}):")
        for text, pred in false_pos:
            print(f"    · flagged {sorted(pred)} on a neutral question")
            print(f"      \"{text[:78]}\"")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(
            {
                "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "set": "held-out (author-constructed, detector not tuned on it)",
                "n_items": len(HELDOUT_C2_QUERIES),
                "n_biased": n_biased,
                "n_neutral": n_neutral,
                "per_bias": metrics,
                "macro_avg": macro,
                "n_missed": len(misses),
                "n_false_positive": len(false_pos),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
