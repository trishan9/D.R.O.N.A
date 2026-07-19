#!/usr/bin/env python3
"""
D.R.O.N.A. SYSTEM-LEVEL validation (thesis defence numbers).

The C1-C4 harness measures *components* (retrieval ranking, detector P/R/F1,
gesture jerk). This script measures what the thesis actually claims about the
**advice itself**:

  1. HALLUCINATION RESISTANCE  - is every recommendation traceable to a document
     that retrieval actually returned? (citation_eval)
  2. BIAS MITIGATION           - does the RESPONSE counter the bias, not just flag
     it? pathway diversity, counter-recommendations, hedging. (bias_mitigation)
  3. ABLATION (the experiment) - the same queries answered WITH vs WITHOUT the
     bias-mitigation instructions, so the contribution is demonstrated by a
     controlled comparison rather than asserted.

Writes reports/validation_report.json, which the API's /evaluation endpoint
serves to the dashboard.

    python scripts/run_validation.py                    # local engine
    python scripts/run_validation.py --remote-url URL   # a served brain (T4)
    python scripts/run_validation.py --limit 6          # fewer queries (slow LLM)

Needs a working brain: this generates real responses. On a small box use
--remote-url pointing at the GPU tier.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drona.advising.engine import make_query  # noqa: E402
from drona.evaluation.bias_mitigation import evaluate_bias_mitigation  # noqa: E402
from drona.evaluation.citation_eval import evaluate_citations  # noqa: E402
from drona.evaluation.queries import C2_QUERIES  # noqa: E402

REPORT = Path(__file__).resolve().parents[1] / "reports" / "validation_report.json"


def _build_advisor(remote_url: str | None):
    if remote_url:
        from drona.advising.remote import RemoteAdvisor

        return RemoteAdvisor(remote_url), None
    from drona.advising.engine import AdvisingEngine

    eng = AdvisingEngine()
    return eng, eng


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--remote-url", default=None, help="Serve from a remote /advise API")
    ap.add_argument("--limit", type=int, default=0, help="Only run the first N queries")
    ap.add_argument("--no-ablation", action="store_true", help="Skip the bias on/off run")
    args = ap.parse_args()

    queries = C2_QUERIES[: args.limit] if args.limit else C2_QUERIES
    advisor, engine = _build_advisor(args.remote_url)
    print(f"Validating over {len(queries)} queries "
          f"({'remote' if args.remote_url else 'local engine'}) ...")

    # ── Pass 1: bias mitigation ON (the shipped system) ──────────────────────
    responses, cases, interests = [], [], []
    t0 = time.time()
    for i, q in enumerate(queries, 1):
        resp = advisor.advise(make_query(q.query_text))
        responses.append(resp)
        # Retrieved set = the citations the engine actually surfaced for the turn.
        retrieved = list(getattr(resp, "citations", []) or [])
        if not retrieved:
            seen: list = []
            for p in getattr(resp, "pathways", []) or []:
                seen.extend(getattr(p, "citations", []) or [])
            retrieved = seen
        cases.append((resp, retrieved))
        interests.append([])
        print(f"  [{i}/{len(queries)}] {'refusal' if resp.refusal else f'{len(resp.pathways)} pathways'}")

    mitigation_on = evaluate_bias_mitigation(responses, interests)
    citations = evaluate_citations(cases)
    elapsed = time.time() - t0

    out: dict = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_queries": len(queries),
        "source": args.remote_url or "local-engine",
        "elapsed_s": round(elapsed, 1),
        "hallucination": asdict(citations),
        "bias_mitigation_on": asdict(mitigation_on),
    }

    # ── Pass 2: ABLATION - same queries, mitigation instructions OFF ─────────
    # This is the controlled experiment: if the bias-aware prompting works, the
    # ON run should show MORE pathway diversity / counter-recommendations.
    if not args.no_ablation and engine is not None:
        import drona.advising.prompt_builder as pb

        print("Ablation: re-running with bias mitigation DISABLED ...")
        original = pb._BIAS_INSTRUCTIONS
        try:
            pb._BIAS_INSTRUCTIONS = {}  # strip the mitigation guidance
            off_responses = [advisor.advise(make_query(q.query_text)) for q in queries]
        finally:
            pb._BIAS_INSTRUCTIONS = original
        mitigation_off = evaluate_bias_mitigation(off_responses, interests)
        out["bias_mitigation_off"] = asdict(mitigation_off)
        out["ablation_delta"] = {
            k: round(getattr(mitigation_on, k) - getattr(mitigation_off, k), 4)
            for k in ("mean_pathway_diversity", "multi_pathway_rate",
                      "mean_hedge_frequency", "counter_recommendation_rate",
                      "bias_flag_coverage")
        }
    elif not args.no_ablation:
        out["ablation_skipped"] = "ablation needs the local engine (prompt is built server-side)"

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("\n" + "=" * 66)
    print("HALLUCINATION RESISTANCE")
    c = out["hallucination"]
    print(f"  grounded pathways        : {c['grounded_pathway_rate']:.1%}")
    print(f"  hallucinated citations   : {c['hallucinated_citation_rate']:.1%}")
    print(f"  fully grounded responses : {c['fully_grounded_response_rate']:.1%}")
    print("BIAS MITIGATION (shipped system)")
    m = out["bias_mitigation_on"]
    print(f"  mean pathway diversity   : {m['mean_pathway_diversity']:.2f}")
    print(f"  multi-pathway rate       : {m['multi_pathway_rate']:.1%}")
    print(f"  counter-recommendations  : {m['counter_recommendation_rate']:.1%}")
    print(f"  hedge frequency          : {m['mean_hedge_frequency']:.2f}")
    print(f"  bias flags surfaced      : {m['bias_flag_coverage']:.1%}")
    if "ablation_delta" in out:
        print("ABLATION (mitigation ON minus OFF - positive = the prompting works)")
        for k, v in out["ablation_delta"].items():
            print(f"  {k:26} {v:+.4f}")
    print("=" * 66)
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
