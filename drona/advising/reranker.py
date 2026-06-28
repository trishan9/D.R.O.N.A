"""
Cross-encoder reranker for D.R.O.N.A.

Takes the top-K candidates from the retriever (default 20) and re-scores them
with a small cross-encoder (BAAI/bge-reranker-base, ~278M params), reducing
to top-N (default 5) for the prompt builder.

Why a reranker on top of dense+BM25?
  Bi-encoders (the dense models) encode query and document independently -
  they cannot model token-level interactions. Cross-encoders see (query, doc)
  jointly and are more accurate but too slow to run over the full corpus.
  This is the standard two-stage pipeline: fast retrieval → accurate reranking.

Hardware note:
  BAAI/bge-reranker-base runs on CPU in ~200ms for 20 pairs. On GTX 1650 it
  would be ~50ms. Either is fine given advising latency targets.

Usage:
    reranker = Reranker()
    top5 = reranker.rerank(query, candidates_docs, top_n=5)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from loguru import logger

from drona.contracts import RetrievalCitation
from drona.utils.settings import settings

if TYPE_CHECKING:
    from drona.advising.retriever import _Doc

# bge-reranker returns ~[0,1] relevance probabilities. If even the best pair
# scores below this, the cross-encoder found nothing clearly relevant (e.g.
# heavy typos crush the scores, or the model failed to load) - in that case we
# keep the retriever's ordering/scores instead of overwriting them with ~0.
_RERANK_MIN_SIGNAL = 0.01


class Reranker:
    """Cross-encoder reranker (lazy-loaded to avoid import-time model download)."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.reranker_model
        self._model = None  # lazy load

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import CrossEncoder
        logger.info(f"Loading reranker model: {self._model_name}")
        self._model = CrossEncoder(self._model_name, device="cpu")
        logger.info("Reranker model loaded")

    def rerank_docs(self, query: str, docs: "list[_Doc]", top_n: int | None = None) -> "list[_Doc]":
        """Rerank a list of _Doc objects, returning the top_n most relevant.

        Args:
            query: The advising query string.
            docs: Candidates from the retriever (typically top-20).
            top_n: Number to return. Defaults to settings.rerank_top_k.

        Returns:
            Re-sorted docs, best first. Length = min(top_n, len(docs)).
        """
        n = top_n or settings.rerank_top_k
        if not docs:
            return []
        if len(docs) <= 1:
            return docs[:n]

        self._ensure_model()
        t0 = time.monotonic()
        pairs = [(query, d.text) for d in docs]
        scores = self._model.predict(pairs)  # type: ignore[union-attr]
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Degenerate-output guard: keep retrieval order/scores if the cross-encoder
        # found nothing clearly relevant (typos / model-load issue).
        if max((float(s) for s in scores), default=0.0) < _RERANK_MIN_SIGNAL:
            logger.debug(
                f"Reranker signal weak (<{_RERANK_MIN_SIGNAL}); keeping retrieval order"
            )
            return docs[:n]

        # Apply tier boost on top of cross-encoder scores (C4: Nepal first)
        boosted = [
            (score * settings.tier_boost(d.metadata.get("tier", "international")), d)
            for score, d in zip(scores, docs)
        ]
        ranked = sorted(boosted, key=lambda x: x[0], reverse=True)[:n]

        result = []
        for score, doc in ranked:
            doc.rrf_score = float(score)  # overwrite with reranker score
            result.append(doc)

        logger.debug(
            f"Reranker: {len(docs)} → {len(result)} docs in {elapsed_ms}ms "
            f"(model: {self._model_name})"
        )
        return result

    def rerank_citations(
        self, query: str, citations: list[RetrievalCitation], top_n: int | None = None
    ) -> list[RetrievalCitation]:
        """Rerank pre-built citations (convenience wrapper for the engine).

        Reconstructs pairs from the citation excerpts. Less accurate than
        reranking full docs, but useful when only citations are available.
        """
        n = top_n or settings.rerank_top_k
        if not citations:
            return []
        if len(citations) <= n:
            return citations

        self._ensure_model()
        pairs = [(query, c.excerpt) for c in citations]
        scores = self._model.predict(pairs)  # type: ignore[union-attr]

        boosted = [
            (score * settings.tier_boost(c.tier.value), c)
            for score, c in zip(scores, citations)
        ]
        ranked = sorted(boosted, key=lambda x: x[0], reverse=True)[:n]

        result = []
        for score, cit in ranked:
            cit.relevance_score = float(score)
            result.append(cit)
        return result
