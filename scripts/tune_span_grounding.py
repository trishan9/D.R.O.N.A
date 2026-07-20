#!/usr/bin/env python3
"""
Choose SPAN_MAX_COVERAGE on DEVELOPMENT data, not on the test set.

WHY THIS SCRIPT EXISTS
----------------------
Capping how much of a question an evidence span may cover removes false
positives (the model quotes the whole question when it has found nothing) but
also costs recall (it quotes the whole question for correct flags too). That
trade-off has a knob, and picking the knob by looking at held-out v2 would fit
the test set - the exact error this project keeps guarding against.

SPLIT
-----
  RETRIEVE from : C2 development bank only (16 items)
  TUNE     on   : held-out v1 (32 items)
  TEST     on   : held-out v2 - never touched here

Retrieving from the bank while tuning on v1 keeps the two disjoint, so no tuning
query can retrieve itself as a labelled example.

CACHING
-------
The coverage cap is a post-filter: it changes which parsed flags are kept, never
what the model generates. So each query is sent to the model ONCE, the parsed
(bias, evidence) pairs are cached, and every cap value is scored offline against
that cache. Identical results, one pass instead of one per setting.

    python scripts/tune_span_grounding.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drona.advising.bias_detector import BiasDetector  # noqa: E402
from drona.advising.rag_bias import (  # noqa: E402
    RAGBiasDetector,
    _parse_flags,
    _tokens,
)
from drona.contracts import StudentProfile  # noqa: E402
from drona.evaluation.heldout_queries import HELDOUT_C2_QUERIES  # noqa: E402
from drona.evaluation.metrics import bias_detection_metrics  # noqa: E402
from drona.evaluation.queries import C2_QUERIES  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "reports" / "span_tuning_cache.json"
CAPS = (0.6, 0.7, 0.8, 0.9, 1.0, 1.01)  # 1.01 == cap effectively disabled


def collect(queries) -> dict[str, list[tuple[str, str]]]:
    """One model call per query; returns parsed (bias, evidence) pairs."""
    if CACHE.exists():
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        if set(cached) == {q.query_text for q in queries}:
            print(f"using cached model replies ({len(cached)} queries)")
            return {k: [tuple(p) for p in v] for k, v in cached.items()}

    # Retrieval pool = development bank only, so no v1 query retrieves itself.
    det = RAGBiasDetector()
    det._pool = list(C2_QUERIES)  # noqa: SLF001
    det._pool_matrix = None  # noqa: SLF001
    det._get_retriever()._ensure_model()  # noqa: SLF001
    enc = det._get_retriever()._model  # noqa: SLF001
    det._pool_matrix = enc.encode(  # noqa: SLF001
        [q.query_text for q in C2_QUERIES],
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    from drona.advising.rag_bias import _PROMPT

    out: dict[str, list[tuple[str, str]]] = {}
    for i, q in enumerate(queries, 1):
        neighbours = det._neighbours(q.query_text)  # noqa: SLF001
        prompt = _PROMPT.format(
            examples=det._format_examples(neighbours),  # noqa: SLF001
            query=q.query_text,
        )
        try:
            raw = det._get_client().complete(  # noqa: SLF001
                prompt, max_tokens=256, temperature=0.0
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}/{len(queries)}] model call failed: {exc}")
            raw = ""
        out[q.query_text] = _parse_flags(raw)
        print(f"  [{i}/{len(queries)}] {len(out[q.query_text])} raw flag(s)")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps({k: [list(p) for p in v] for k, v in out.items()}, indent=2),
        encoding="utf-8",
    )
    return out


def keep(evidence: str, query: str, cap: float) -> bool:
    """span_is_grounded with the cap as a parameter (tuning only)."""
    from drona.advising.rag_bias import SPAN_OVERLAP_MIN, _normalise

    if not evidence.strip():
        return False
    ev, qt = _tokens(evidence), _tokens(query)
    if not ev or not qt:
        return False
    if len(ev) / len(qt) > cap:
        return False
    if _normalise(evidence) in _normalise(query):
        return True
    qs = set(qt)
    return sum(1 for t in ev if t in qs) / len(ev) >= SPAN_OVERLAP_MIN


def main() -> int:
    queries = HELDOUT_C2_QUERIES
    n_neutral = sum(1 for q in queries if not q.expected_biases)
    print(f"tuning SPAN_MAX_COVERAGE - retrieve from C2 bank ({len(C2_QUERIES)}), "
          f"tune on v1 ({len(queries)} items, {n_neutral} neutral). v2 untouched.")

    replies = collect(queries)
    rules, profile = BiasDetector(), StudentProfile(session_id="tune")

    print(f"\n{'cap':>6}  {'RAG alone':^26}   {'hybrid (rules ∪ RAG)':^26}")
    print(f"{'':>6}  {'P':>5} {'R':>5} {'F1':>5} {'fp':>5}   {'P':>5} {'R':>5} {'F1':>5} {'fp':>5}")
    for cap in CAPS:
        row = []
        for hybrid in (False, True):
            res, fp = [], 0
            for q in queries:
                pred = {
                    b for b, ev in replies.get(q.query_text, [])
                    if keep(ev, q.query_text, cap)
                }
                if hybrid:
                    pred |= {
                        f.bias_type
                        for f in rules.detect(q.query_text, profile=profile)
                    }
                actual = set(q.expected_biases)
                res.append({"predicted_biases": pred, "actual_biases": actual})
                if not actual and pred:
                    fp += 1
            m = bias_detection_metrics(res)["macro_avg"]
            row.append((m["precision"], m["recall"], m["f1"], fp))
        (p1, r1, f1, fp1), (p2, r2, f2, fp2) = row
        label = f"{cap:.2f}" if cap <= 1.0 else " off"
        print(f"{label:>6}  {p1:5.3f} {r1:5.3f} {f1:5.3f} {fp1:4d}/{n_neutral}   "
              f"{p2:5.3f} {r2:5.3f} {f2:5.3f} {fp2:4d}/{n_neutral}")

    print("\nPick the cap here, then apply it unchanged to v2 exactly once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
