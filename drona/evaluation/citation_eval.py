"""
Citation-verification evaluation for D.R.O.N.A.

Phase 2 ships per-response citation grounding (``drona.advising.verify``). This
harness aggregates that check over a *set* of responses to produce the thesis's
hallucination-resistance numbers:

  - grounded_pathway_rate : fraction of all pathways that carry ≥1 valid citation
  - hallucinated_citation_rate : fraction of cited sources NOT in the retrieved set
  - fully_grounded_response_rate : fraction of responses where every pathway is grounded
  - mean_citations_per_pathway

The check is rule-based and falsifiable (no LLM judge), matching the system's
transparency philosophy. It can run on live responses or on responses + their
retrieved-citation sets recorded during an eval run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from drona.advising.verify import verify_pathways


@dataclass
class CitationEvalReport:
    n_responses: int
    n_pathways: int
    grounded_pathway_rate: float
    hallucinated_citation_rate: float
    fully_grounded_response_rate: float
    mean_citations_per_pathway: float
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_citations(
    cases: list[tuple[Any, list[Any]]],
) -> CitationEvalReport:
    """Aggregate citation-grounding metrics.

    Args:
        cases: list of ``(response, retrieved_citations)`` pairs, where
            ``response`` is an AdvisingResponse-like object and
            ``retrieved_citations`` is the list of RetrievalCitation actually
            returned by retrieval+rerank for that query. If you only have the
            response, pass the union of its own pathway citations as the
            retrieved set (this then measures internal consistency only).

    Returns:
        CitationEvalReport.
    """
    n_responses = len(cases)
    if n_responses == 0:
        return CitationEvalReport(0, 0, 0.0, 0.0, 0.0, 0.0, ["No cases."])

    total_pathways = 0
    grounded_pathways = 0
    total_citations = 0
    hallucinated_citations = 0
    fully_grounded_responses = 0
    issues: list[str] = []

    for response, retrieved in cases:
        pathways = list(getattr(response, "pathways", []) or [])
        retrieved_ids = {getattr(c, "source_id", None) for c in (retrieved or [])}

        report = verify_pathways(pathways, list(retrieved or []))
        issues.extend(report.issues)

        total_pathways += len(pathways)
        for pw in pathways:
            cits = list(getattr(pw, "citations", []) or [])
            total_citations += len(cits)
            valid = [c for c in cits if getattr(c, "source_id", None) in retrieved_ids]
            hallucinated_citations += len(cits) - len(valid)
            if valid:
                grounded_pathways += 1

        if pathways and report.all_grounded:
            fully_grounded_responses += 1

    return CitationEvalReport(
        n_responses=n_responses,
        n_pathways=total_pathways,
        grounded_pathway_rate=(grounded_pathways / total_pathways) if total_pathways else 0.0,
        hallucinated_citation_rate=(hallucinated_citations / total_citations) if total_citations else 0.0,
        fully_grounded_response_rate=fully_grounded_responses / n_responses,
        mean_citations_per_pathway=(total_citations / total_pathways) if total_pathways else 0.0,
        issues=issues[:50],  # cap to keep the report readable
    )
