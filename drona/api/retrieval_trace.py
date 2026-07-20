"""
Stage-by-stage retrieval trace for the dashboard's retrieval explorer.

WHY
---
C1 claims hybrid retrieval (BM25 + dense, fused with reciprocal rank fusion,
then cross-encoder reranked) beats either retriever alone. The ablation numbers
support that in aggregate, but an aggregate NDCG does not *show* anyone why.

This runs the same query through each stage separately and returns all four
ranked lists, so the difference is visible on a single screen: which documents
only lexical search found, which only the embeddings found, what fusion did to
the order, and what reranking moved. That is the difference between asserting
the design and demonstrating it.

Everything here is read-only and calls the same Retriever the advising path
uses - it is an inspection view of the real pipeline, not a reimplementation.
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger


def _doc_row(doc: Any, rank: int) -> dict[str, Any]:
    """One retrieved document, trimmed to what the explorer renders."""
    meta = doc.metadata or {}
    return {
        "rank": rank,
        "id": doc.id,
        "excerpt": (doc.text or "")[:280],
        "tier": meta.get("tier", "international"),
        "source_type": meta.get("source_type", "career_pathway"),
        "title": meta.get("title") or meta.get("module_code") or meta.get("name") or "",
        "collection": getattr(doc, "collection", ""),
        "dense_rank": getattr(doc, "dense_rank", None),
        "bm25_rank": getattr(doc, "bm25_rank", None),
        "rrf_score": round(float(getattr(doc, "rrf_score", 0.0) or 0.0), 5),
    }


def retrieval_trace(query: str, top_k: int = 8) -> dict[str, Any]:
    """Run the hybrid pipeline stage by stage and return every intermediate list."""
    from drona.advising.reranker import Reranker
    from drona.advising.retriever import Retriever

    query = (query or "").strip()
    if not query:
        return {"available": False, "reason": "empty query"}

    try:
        retriever = Retriever()
    except Exception as exc:  # noqa: BLE001 - explorer must not break the API
        logger.warning(f"/retrieval/trace: retriever unavailable: {exc}")
        return {"available": False, "reason": str(exc)}

    stages: list[dict[str, Any]] = []
    n = max(top_k, 8)

    # 1. Lexical. Exact tokens - module codes, employer names, acronyms.
    try:
        retriever._ensure_bm25()  # noqa: SLF001 - inspection view of the real pipeline
        t0 = time.perf_counter()
        bm25 = retriever._bm25_retrieve(query, n)  # noqa: SLF001
        _elapsed = round((time.perf_counter() - t0) * 1000, 1)
        stages.append({
            "elapsed_ms": _elapsed,
            "key": "bm25",
            "label": "BM25 (lexical)",
            "description": "Exact-term matching. Strong on module codes and names, blind to paraphrase.",
            "docs": [_doc_row(d, i + 1) for i, d in enumerate(bm25[:top_k])],
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"/retrieval/trace: bm25 stage failed: {exc}")
        bm25 = []

    # 2. Dense. Semantic similarity - catches paraphrase, weak on rare literals.
    #    Mirrors retrieve(): dense runs over BOTH collections, and the fusion
    #    below takes all three lists. Fusing only two would not be this pipeline.
    curriculum_docs: list[Any] = []
    career_docs: list[Any] = []
    try:
        from drona.advising.retriever import COLL_CAREER, COLL_CURRICULUM

        t0 = time.perf_counter()
        curriculum_docs = retriever._dense_retrieve(  # noqa: SLF001
            query, retriever._coll_curriculum, COLL_CURRICULUM, n  # noqa: SLF001
        )
        career_docs = retriever._dense_retrieve(  # noqa: SLF001
            query, retriever._coll_career, COLL_CAREER, n  # noqa: SLF001
        )
        dense = curriculum_docs + career_docs
        stages.append({
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "key": "dense",
            "label": "Dense (embeddings)",
            "description": "Semantic similarity over the curriculum and career collections. Catches paraphrase, weaker on rare exact tokens.",
            "docs": [_doc_row(d, i + 1) for i, d in enumerate(dense[:top_k])],
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"/retrieval/trace: dense stage failed: {exc}")
        dense = []

    # 3. Fusion. RRF needs no score calibration between the systems, which is why
    #    it is used instead of a weighted sum of incomparable scores.
    fused: list[Any] = []
    try:
        ranked = [lst for lst in (curriculum_docs, career_docs, bm25) if lst]
        if ranked:
            t0 = time.perf_counter()
            fused = retriever._rrf(ranked)  # noqa: SLF001
            fused = retriever._apply_tier_boost(fused)  # noqa: SLF001
            stages.append({
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                "key": "rrf",
                "label": "RRF fusion + Nepal-first boost",
                "description": "Reciprocal rank fusion combines both rankings without needing comparable scores; the tier boost enforces the local-first ordering (C4).",
                "docs": [_doc_row(d, i + 1) for i, d in enumerate(fused[:top_k])],
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"/retrieval/trace: fusion stage failed: {exc}")

    # 4. Rerank. Cross-encoder scores the pair jointly - most accurate, and
    #    affordable only because it sees the shortlist rather than the corpus.
    try:
        if fused:
            t0 = time.perf_counter()
            reranked = Reranker().rerank_docs(query, list(fused), top_n=top_k)
            stages.append({
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                "key": "rerank",
                "label": "Cross-encoder rerank",
                "description": "Scores each query-document pair jointly. Most accurate stage, affordable because it only sees the shortlist.",
                "docs": [_doc_row(d, i + 1) for i, d in enumerate(reranked)],
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"/retrieval/trace: rerank stage failed: {exc}")

    # Movement between the first and last stage makes the pipeline's effect legible.
    first = stages[0]["docs"] if stages else []
    last = stages[-1]["docs"] if stages else []
    first_ids = [d["id"] for d in first]
    final_only = [d["id"] for d in last if d["id"] not in first_ids]

    return {
        "available": bool(stages),
        "query": query,
        "top_k": top_k,
        "stages": stages,
        "summary": {
            "n_stages": len(stages),
            "bm25_only": sorted({d["id"] for d in (stages[0]["docs"] if stages else [])}
                                - {d["id"] for d in (stages[1]["docs"] if len(stages) > 1 else [])}),
            "surfaced_by_pipeline": final_only,
        },
    }
