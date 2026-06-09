"""
RAG quality evaluation for D.R.O.N.A. — Ragas with a transparent fallback.

Ragas (Es et al. 2023) scores RAG systems on faithfulness, answer relevancy, and
context precision/recall. It is, however, heavy and (for the LLM-graded metrics)
calls an LLM judge — which conflicts with the C4 "local-only request path"
guarantee if pointed at a cloud model. So this harness:

  - Uses **Ragas** when it is installed AND an offline judge LLM is explicitly
    provided (Ragas/judge are an *evaluation-time*, offline concern — never the
    live advising path), and
  - Otherwise falls back to a **lightweight, transparent, lexical proxy** that
    needs no extra dependencies and is fully reproducible. The proxy is clearly
    labelled as such in the output so it is never mistaken for true Ragas scores.

Each evaluation sample is a dict:
    {
      "question":  str,
      "answer":    str,           # the response summary / speak_text
      "contexts":  list[str],     # retrieved excerpts the answer should rest on
      "ground_truth": str | None, # optional reference answer
    }
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


# ── Lightweight lexical proxy metrics (no deps) ───────────────────────────────

def _faithfulness_proxy(answer: str, contexts: list[str]) -> float:
    """Fraction of answer content-tokens that appear in the retrieved context.

    A crude but transparent grounding proxy: an answer that invents tokens not
    present in any context is less faithful. Stopword-light by design.
    """
    ans = _tokens(answer)
    if not ans:
        return 0.0
    ctx = set().union(*[_tokens(c) for c in contexts]) if contexts else set()
    grounded = ans & ctx
    return len(grounded) / len(ans)


def _answer_relevancy_proxy(question: str, answer: str) -> float:
    """Token overlap (Jaccard) between question and answer — topical relevance."""
    q, a = _tokens(question), _tokens(answer)
    if not q or not a:
        return 0.0
    return len(q & a) / len(q | a)


def _context_precision_proxy(question: str, contexts: list[str]) -> float:
    """Fraction of retrieved contexts that share any token with the question."""
    if not contexts:
        return 0.0
    q = _tokens(question)
    useful = sum(1 for c in contexts if q & _tokens(c))
    return useful / len(contexts)


def _context_recall_proxy(ground_truth: str | None, contexts: list[str]) -> float:
    """Fraction of ground-truth tokens recoverable from the retrieved contexts."""
    if not ground_truth:
        return 0.0
    gt = _tokens(ground_truth)
    if not gt:
        return 0.0
    ctx = set().union(*[_tokens(c) for c in contexts]) if contexts else set()
    return len(gt & ctx) / len(gt)


@dataclass
class RagasReport:
    backend: str                       # "ragas" or "lexical_proxy"
    n_samples: int
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    per_sample: list[dict[str, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _evaluate_with_proxy(samples: list[dict[str, Any]]) -> RagasReport:
    per_sample: list[dict[str, float]] = []
    for s in samples:
        contexts = list(s.get("contexts", []) or [])
        row = {
            "faithfulness": _faithfulness_proxy(s.get("answer", ""), contexts),
            "answer_relevancy": _answer_relevancy_proxy(s.get("question", ""), s.get("answer", "")),
            "context_precision": _context_precision_proxy(s.get("question", ""), contexts),
            "context_recall": _context_recall_proxy(s.get("ground_truth"), contexts),
        }
        per_sample.append(row)

    n = len(per_sample) or 1
    agg = {k: sum(r[k] for r in per_sample) / n for k in
           ("faithfulness", "answer_relevancy", "context_precision", "context_recall")}
    return RagasReport(
        backend="lexical_proxy",
        n_samples=len(samples),
        per_sample=per_sample,
        notes=[
            "Ragas not used (not installed or no offline judge LLM provided). "
            "Scores are a transparent lexical proxy, NOT official Ragas metrics.",
        ],
        **agg,
    )


def evaluate_rag(
    samples: list[dict[str, Any]],
    judge_llm: Any | None = None,
    judge_embeddings: Any | None = None,
    force_proxy: bool = False,
) -> RagasReport:
    """Evaluate RAG quality, preferring Ragas when available.

    Args:
        samples: list of {question, answer, contexts, ground_truth?} dicts.
        judge_llm: an offline LangChain-compatible LLM for Ragas's graded metrics.
            REQUIRED for the real Ragas backend (kept offline — never the live
            advising model). If None, the lexical proxy is used.
        judge_embeddings: embeddings model for Ragas relevancy metrics.
        force_proxy: skip Ragas even if installed (useful for fast CI).

    Returns:
        RagasReport. ``backend`` tells you which path produced the numbers.
    """
    if not samples:
        return RagasReport("lexical_proxy", 0, 0.0, 0.0, 0.0, 0.0, notes=["No samples."])

    if force_proxy or judge_llm is None:
        return _evaluate_with_proxy(samples)

    try:
        from datasets import Dataset  # noqa: F401
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except Exception:
        report = _evaluate_with_proxy(samples)
        report.notes.append("Ragas import failed; used lexical proxy instead.")
        return report

    try:
        from datasets import Dataset

        ds = Dataset.from_list(
            [
                {
                    "question": s.get("question", ""),
                    "answer": s.get("answer", ""),
                    "contexts": list(s.get("contexts", []) or []),
                    "ground_truth": s.get("ground_truth", "") or "",
                }
                for s in samples
            ]
        )
        metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
        result = ragas_evaluate(
            ds, metrics=metrics, llm=judge_llm, embeddings=judge_embeddings
        )
        scores = result if isinstance(result, dict) else result.scores  # type: ignore[attr-defined]

        def _get(name: str) -> float:
            try:
                return float(scores[name])
            except Exception:
                return 0.0

        return RagasReport(
            backend="ragas",
            n_samples=len(samples),
            faithfulness=_get("faithfulness"),
            answer_relevancy=_get("answer_relevancy"),
            context_precision=_get("context_precision"),
            context_recall=_get("context_recall"),
            notes=["Scored with the Ragas backend (offline judge LLM)."],
        )
    except Exception as exc:  # pragma: no cover - depends on external judge
        report = _evaluate_with_proxy(samples)
        report.notes.append(f"Ragas run failed ({exc}); used lexical proxy instead.")
        return report
