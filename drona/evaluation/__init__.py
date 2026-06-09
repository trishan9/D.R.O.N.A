"""
D.R.O.N.A. evaluation package.

Modules:
  metrics          — pure C1–C4 metric functions (NDCG, P/R/F1, jerk, latency…)
  queries          — labelled synthetic evaluation query bank
  harness          — EvaluationHarness: runs C1–C4 and assembles a report
  bias_mitigation  — custom bias-MITIGATION metrics (diversity, hedging, …)
  stats            — scipy.stats comparison harness (robot vs traditional, …)
  ragas_harness    — RAG quality (Ragas when available, lexical proxy otherwise)
  citation_eval    — aggregate citation-grounding / hallucination metrics

See docs/architecture.md and docs/evaluation_guide.md.
"""

from drona.evaluation.bias_mitigation import (
    BiasMitigationReport,
    evaluate_bias_mitigation,
)
from drona.evaluation.citation_eval import CitationEvalReport, evaluate_citations
from drona.evaluation.ragas_harness import RagasReport, evaluate_rag
from drona.evaluation.stats import (
    ComparisonResult,
    compare_conditions,
    paired_comparison,
)

__all__ = [
    "BiasMitigationReport",
    "evaluate_bias_mitigation",
    "CitationEvalReport",
    "evaluate_citations",
    "RagasReport",
    "evaluate_rag",
    "ComparisonResult",
    "compare_conditions",
    "paired_comparison",
]
