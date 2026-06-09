"""
Citation-grounding verification for D.R.O.N.A.

The LLM is instructed to cite retrieved documents by index. This module checks
that it actually did, and that the citations it used really exist in the
retrieved set. Ungrounded pathways (zero valid citations) are a hallucination
risk; we don't silently trust them.

This is a deliberately TRANSPARENT and FALSIFIABLE check (no second LLM "judge"),
mirroring the design philosophy of the rule-based bias detector. Grounding the
RAG claim is the verification stage of the LangGraph (Lewis et al. 2020 — RAG;
the proposal's citation-grounding requirement).

Outputs a VerificationReport the graph uses to decide:
  - downgrade an ungrounded pathway's confidence to "low", and
  - whether to RETRY generation (if too many pathways are ungrounded), and
  - whether the whole response should refuse (if nothing is grounded).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from drona.contracts import PathwayRecommendation, RetrievalCitation


@dataclass
class VerificationReport:
    """Result of verifying a set of pathways against retrieved citations."""

    grounded_pathways: list[PathwayRecommendation] = field(default_factory=list)
    ungrounded_titles: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def all_grounded(self) -> bool:
        return not self.ungrounded_titles

    @property
    def any_grounded(self) -> bool:
        return bool(self.grounded_pathways) and any(
            p.confidence != "low" or p.citations for p in self.grounded_pathways
        )

    @property
    def grounded_fraction(self) -> float:
        total = len(self.grounded_pathways)
        if total == 0:
            return 0.0
        grounded = sum(1 for p in self.grounded_pathways if p.citations)
        return grounded / total


def _citation_ids(citations: list[RetrievalCitation]) -> set[str]:
    return {c.source_id for c in citations}


def verify_pathways(
    pathways: list[PathwayRecommendation],
    retrieved: list[RetrievalCitation],
) -> VerificationReport:
    """Verify each pathway is grounded in the retrieved citation set.

    A pathway is "grounded" if it references at least one citation whose
    source_id is in the retrieved set. Pathways citing unknown sources have
    those citations stripped; pathways left with no valid citation are flagged
    and their confidence downgraded to "low" (kept, but clearly marked).

    Args:
        pathways: LLM-produced pathways (citations already resolved to objects).
        retrieved: The citations actually returned by retrieval+rerank.

    Returns:
        VerificationReport with cleaned pathways and any issues found.
    """
    valid_ids = _citation_ids(retrieved)
    report = VerificationReport()

    for pw in pathways:
        kept = [c for c in pw.citations if c.source_id in valid_ids]
        dropped = len(pw.citations) - len(kept)
        if dropped:
            report.issues.append(
                f"Pathway '{pw.pathway_title}': dropped {dropped} citation(s) "
                f"not present in the retrieved set (possible hallucination)."
            )

        if kept:
            report.grounded_pathways.append(pw.model_copy(update={"citations": kept}))
        else:
            # No valid citation — keep the pathway but mark it low-confidence and
            # record the issue so the UI/graph can surface or suppress it.
            report.ungrounded_titles.append(pw.pathway_title)
            report.issues.append(
                f"Pathway '{pw.pathway_title}': no valid citation — "
                f"confidence downgraded to low."
            )
            report.grounded_pathways.append(
                pw.model_copy(update={"citations": [], "confidence": "low"})
            )

    return report
