"""
Base+RAG vs LoRA+RAG ablation for the advising fine-tune (Phase 3).

Runs the same query set through two advisors (each exposing
``advise(query) -> AdvisingResponse``) and computes comparable, transparent
metrics. The LoRA adapter is served the same way as the base model (via Ollama
after merge→GGUF, or via a transformers backend); this harness is backend-
agnostic, so the comparison logic is unit-testable with stubs.

Metrics (all defensible at viva, no LLM-judge):
  - pathway_count_mean     : anti-anchoring favours >1 pathway
  - grounded_rate          : fraction of pathways with >=1 citation
  - nepal_citation_ratio   : C4 local-grounding signal
  - hedge_frequency        : calibrated-language signal (anti-overconfidence)
  - refusal_rate           : honesty under low coverage
  - mean_latency_ms
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from typing import Protocol

from loguru import logger

from drona.contracts import AdvisingQuery, AdvisingResponse, DataTier

_HEDGE_RE = re.compile(
    r"\b(may|might|could|consider|depends|often|typically|generally|"
    r"not guaranteed|varies|in many cases)\b",
    re.IGNORECASE,
)


class _Advisor(Protocol):
    def advise(self, query: AdvisingQuery) -> AdvisingResponse: ...


@dataclass
class AblationMetrics:
    n: int = 0
    pathway_count_mean: float = 0.0
    grounded_rate: float = 0.0
    nepal_citation_ratio: float = 0.0
    hedge_frequency: float = 0.0
    refusal_rate: float = 0.0
    mean_latency_ms: float = 0.0


def _hedges(text: str) -> int:
    return len(_HEDGE_RE.findall(text or ""))


def compute_metrics(responses: list[AdvisingResponse], latencies_ms: list[float]) -> AblationMetrics:
    """Aggregate metrics over a list of advising responses."""
    n = len(responses)
    if n == 0:
        return AblationMetrics()

    total_pathways = 0
    grounded = 0
    total_citations = 0
    nepal_citations = 0
    hedge_total = 0
    refusals = 0

    for r in responses:
        if r.refusal:
            refusals += 1
        total_pathways += len(r.pathways)
        hedge_total += _hedges(r.summary)
        for pw in r.pathways:
            if pw.citations:
                grounded += 1
            hedge_total += _hedges(pw.rationale)
            for c in pw.citations:
                total_citations += 1
                if c.tier == DataTier.NEPAL:
                    nepal_citations += 1

    return AblationMetrics(
        n=n,
        pathway_count_mean=total_pathways / n,
        grounded_rate=(grounded / total_pathways) if total_pathways else 0.0,
        nepal_citation_ratio=(nepal_citations / total_citations) if total_citations else 0.0,
        hedge_frequency=hedge_total / n,
        refusal_rate=refusals / n,
        mean_latency_ms=sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0,
    )


def run_backend(advisor: _Advisor, queries: list[AdvisingQuery]) -> AblationMetrics:
    """Run all queries through one advisor and aggregate metrics."""
    responses: list[AdvisingResponse] = []
    latencies: list[float] = []
    for q in queries:
        t0 = time.monotonic()
        responses.append(advisor.advise(q))
        latencies.append((time.monotonic() - t0) * 1000)
    return compute_metrics(responses, latencies)


def run_ablation(
    base: _Advisor, lora: _Advisor, queries: list[AdvisingQuery]
) -> dict[str, dict]:
    """Compare base vs LoRA advisor over the same queries.

    Returns a dict with per-backend metrics and base→lora deltas.
    """
    logger.info(f"Running base vs LoRA ablation over {len(queries)} queries")
    base_m = run_backend(base, queries)
    lora_m = run_backend(lora, queries)
    deltas = {
        k: round(getattr(lora_m, k) - getattr(base_m, k), 4)
        for k in asdict(base_m)
        if isinstance(getattr(base_m, k), (int, float))
    }
    return {"base": asdict(base_m), "lora": asdict(lora_m), "delta_lora_minus_base": deltas}
