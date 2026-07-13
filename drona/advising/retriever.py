"""
Hybrid retriever for D.R.O.N.A. - Research Contribution C1.

Architecture:
  1. Dense retrieval from two ChromaDB collections (curriculum + career),
     each embedded with a domain-appropriate model.
  2. BM25 sparse retrieval over the same document set, built at startup from
     the ChromaDB metadata (no second embedding needed).
  3. Reciprocal Rank Fusion (RRF) to merge the three ranked lists.
  4. Tier boosting: Nepal-tier documents are up-weighted per settings.

Why two collections instead of one?
  "Python" in a module description ("students learn Python control flow")
  and "Python" in a job posting ("3 years Python required") sit in different
  semantic neighbourhoods. Mixing them into one embedding space dilutes both.
  The dual-collection design is the core of C1.

Why RRF instead of linear score combination?
  Dense scores and BM25 scores are not on the same scale and are hard to
  calibrate without a labelled evaluation set (which we don't have at
  ingestion time). RRF is parameter-light and empirically robust across
  domains (Cormack et al., 2009).

Usage:
    retriever = Retriever()
    results = retriever.retrieve("I want to work in AI in Kathmandu", top_k=5)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from loguru import logger
from rank_bm25 import BM25Okapi

from drona.contracts import DataTier, RetrievalCitation
from drona.data_pipeline.ingest import COLL_CAREER, COLL_CURRICULUM
from drona.utils.settings import settings

_RRF_K = 60  # standard RRF constant; higher → more rank-based, less score-based


@dataclass
class _Doc:
    """Internal intermediate representation of a retrieved document."""
    id: str
    text: str
    metadata: dict[str, Any]
    dense_rank: int | None = None
    bm25_rank: int | None = None
    rrf_score: float = 0.0
    collection: str = ""


def _build_citation(doc: _Doc) -> RetrievalCitation:
    meta = doc.metadata
    source_type = meta.get("source_type", "career_pathway")
    tier_str = meta.get("tier", "international")

    # Map source_type to a valid literal
    valid_types = {"curriculum", "job_posting", "career_pathway", "report", "synthetic"}
    if source_type not in valid_types:
        source_type = "career_pathway"

    try:
        tier = DataTier(tier_str)
    except ValueError:
        tier = DataTier.INTERNATIONAL

    return RetrievalCitation(
        source_type=source_type,  # type: ignore[arg-type]
        source_id=doc.id,
        tier=tier,
        excerpt=doc.text[:300],
        relevance_score=doc.rrf_score,
    )


class Retriever:
    """Hybrid retriever over the dual-embedding ChromaDB store."""

    def __init__(self, chroma_dir: str | None = None) -> None:
        path = chroma_dir or str(settings.chroma_dir)
        self._client = chromadb.PersistentClient(path=path)

        curriculum_ef = SentenceTransformerEmbeddingFunction(
            model_name=settings.curriculum_embed_model, device="cpu"
        )
        career_ef = SentenceTransformerEmbeddingFunction(
            model_name=settings.career_embed_model, device="cpu"
        )

        self._coll_curriculum = self._client.get_or_create_collection(
            name=COLL_CURRICULUM, embedding_function=curriculum_ef,
            metadata={"hnsw:space": "cosine"},
        )
        self._coll_career = self._client.get_or_create_collection(
            name=COLL_CAREER, embedding_function=career_ef,
            metadata={"hnsw:space": "cosine"},
        )

        # BM25 index is built lazily from the curriculum collection
        self._bm25_index: BM25Okapi | None = None
        self._bm25_docs: list[_Doc] = []

        logger.info(
            f"Retriever ready - "
            f"curriculum={self._coll_curriculum.count()} docs, "
            f"career={self._coll_career.count()} docs"
        )

    # ── BM25 index ───────────────────────────────────────────────────────────

    def _ensure_bm25(self) -> None:
        """Build BM25 index from all curriculum documents (lazy, one-time)."""
        if self._bm25_index is not None:
            return

        logger.info("Building BM25 index from curriculum collection…")
        result = self._coll_curriculum.get(include=["documents", "metadatas"])
        ids = result["ids"]
        texts = result["documents"] or []
        metas = result["metadatas"] or []

        self._bm25_docs = [
            _Doc(id=i, text=t, metadata=m or {}, collection=COLL_CURRICULUM)
            for i, t, m in zip(ids, texts, metas, strict=False)
        ]
        tokenised = [d.text.lower().split() for d in self._bm25_docs]
        self._bm25_index = BM25Okapi(tokenised)
        logger.info(f"BM25 index built over {len(self._bm25_docs)} curriculum documents")

    # ── Dense retrieval ───────────────────────────────────────────────────────

    def _dense_retrieve(
        self, query: str, collection: chromadb.Collection, label: str, n: int
    ) -> list[_Doc]:
        if collection.count() == 0:
            return []
        result = collection.query(
            query_texts=[query],
            n_results=min(n, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        docs: list[_Doc] = []
        for id_, text, meta, _dist in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
            strict=False,
        ):
            docs.append(_Doc(id=id_, text=text, metadata=meta or {}, collection=label))
        return docs

    # ── BM25 retrieval ────────────────────────────────────────────────────────

    def _bm25_retrieve(self, query: str, n: int) -> list[_Doc]:
        self._ensure_bm25()
        if not self._bm25_docs:
            return []
        tokens = query.lower().split()
        scores = self._bm25_index.get_scores(tokens)  # type: ignore[union-attr]
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:n]
        return [self._bm25_docs[i] for i, _ in ranked]

    # ── RRF fusion ────────────────────────────────────────────────────────────

    @staticmethod
    def _rrf(ranked_lists: list[list[_Doc]]) -> list[_Doc]:
        """Reciprocal Rank Fusion across multiple ranked lists."""
        scores: dict[str, float] = {}
        best_doc: dict[str, _Doc] = {}

        for ranked in ranked_lists:
            for rank, doc in enumerate(ranked, start=1):
                rrf = 1.0 / (_RRF_K + rank)
                scores[doc.id] = scores.get(doc.id, 0.0) + rrf
                if doc.id not in best_doc:
                    best_doc[doc.id] = doc

        merged = sorted(best_doc.values(), key=lambda d: scores[d.id], reverse=True)
        for doc in merged:
            doc.rrf_score = scores[doc.id]
        return merged

    # ── Tier boosting ─────────────────────────────────────────────────────────

    @staticmethod
    def _apply_tier_boost(docs: list[_Doc]) -> list[_Doc]:
        """Multiply RRF score by the configured tier boost then re-sort."""
        for doc in docs:
            tier = doc.metadata.get("tier", "international")
            boost = settings.tier_boost(tier)
            doc.rrf_score *= boost
        return sorted(docs, key=lambda d: d.rrf_score, reverse=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        require_local_first: bool = True,
    ) -> list[RetrievalCitation]:
        """Run hybrid retrieval and return ranked citations.

        Args:
            query: The student's advising query string.
            top_k: Number of results to return. Defaults to settings.retrieval_top_k.
            require_local_first: If True, apply Nepal-tier boost (anti-anchoring:
                Nepali market data appears before US-only data).

        Returns:
            Ranked list of RetrievalCitation objects ready for the prompt builder.
        """
        k = top_k or settings.retrieval_top_k
        logger.debug(f"Retrieving top-{k} for query: {query[:80]}…")

        # Dense from both collections
        curriculum_docs = self._dense_retrieve(query, self._coll_curriculum, COLL_CURRICULUM, k)
        career_docs = self._dense_retrieve(query, self._coll_career, COLL_CAREER, k)

        # BM25 from curriculum (lexical match matters for module codes like "4001COMP")
        bm25_docs = self._bm25_retrieve(query, k)

        # Fuse
        merged = self._rrf([curriculum_docs, career_docs, bm25_docs])

        # Tier boost (C4: Nepal data surfaces higher)
        if require_local_first:
            merged = self._apply_tier_boost(merged)

        top = merged[:k]
        citations = [_build_citation(d) for d in top]
        logger.debug(
            f"Retrieved {len(citations)} citations "
            f"(Nepal: {sum(1 for c in citations if c.tier == DataTier.NEPAL)}, "
            f"Intl: {sum(1 for c in citations if c.tier == DataTier.INTERNATIONAL)})"
        )
        return citations

    def retrieve_raw(self, query: str, top_k: int | None = None) -> list[_Doc]:
        """Like retrieve() but returns internal _Doc objects (for reranker input)."""
        k = top_k or settings.retrieval_top_k
        curriculum_docs = self._dense_retrieve(query, self._coll_curriculum, COLL_CURRICULUM, k)
        career_docs = self._dense_retrieve(query, self._coll_career, COLL_CAREER, k)
        bm25_docs = self._bm25_retrieve(query, k)
        merged = self._rrf([curriculum_docs, career_docs, bm25_docs])
        return self._apply_tier_boost(merged)[:k]
