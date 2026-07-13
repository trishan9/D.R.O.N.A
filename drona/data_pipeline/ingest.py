"""
ChromaDB dual-embedding ingestor for D.R.O.N.A.

Research contribution C1: Dual-embedding retrieval
  - Collection 1: curriculum text, embedded with a general academic model
                  (BAAI/bge-small-en-v1.5)
  - Collection 2: job/career text, embedded with a job-specialised model
                  (TechWolf/JobBERT-v2)

This separation matters because "Python" in a module description ("students learn
Python control flow") and "Python" in a job posting ("3+ years Python required")
live in different semantic neighbourhoods. A single embedding space conflates them.

Architecture:
  - Two ChromaDB collections, one per embedding model
  - Both are backed by local files (no server, zero ops)
  - Documents include metadata matching the DataTier enum for score boosting
  - BM25 index is built separately in the retriever (drona.advising.retriever)

Usage:
    from drona.data_pipeline.ingest import Ingestor
    with Ingestor() as ing:
        ing.add_curriculum_modules(modules)
        ing.add_job_postings(postings)
        ing.add_career_pathways(pathways)
"""

from __future__ import annotations

import json
import re
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from loguru import logger

from drona.contracts import CareerPathway, CurriculumModule, JobPosting
from drona.utils.settings import settings

# Collection name constants
COLL_CURRICULUM = f"{settings.chroma_collection_prefix}_curriculum"
COLL_CAREER = f"{settings.chroma_collection_prefix}_career"

_BATCH_SIZE = 64  # insert in batches to avoid OOM on small GPU


def _tier_boost(tier: str) -> float:
    """Retrieve the configured score multiplier for a tier string."""
    return settings.tier_boost(tier)


# ── Document text builders (what gets embedded) ─────────────────────────────

_CHUNK_CHARS = 1400          # ~350 tokens - fits the embedding model comfortably
_CHUNK_OVERLAP = 150         # carry context across boundaries
_MAX_CHUNKS_PER_MODULE = 40  # safety cap for very large modules


def _chunk_content(content: str) -> list[str]:
    """Split a module's full body into overlapping chunks for embedding.

    Prefers paragraph/lesson boundaries; falls back to fixed windows. Returns
    [] for empty/short content (the summary doc already covers those).
    """
    content = (content or "").strip()
    if len(content) < 200:
        return []
    paras = [p.strip() for p in re.split(r"\n{2,}|\n(?=###|\*\*|\[Attached)", content)
             if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paras:
        if len(buf) + len(para) + 1 <= _CHUNK_CHARS:
            buf = f"{buf}\n{para}".strip()
        else:
            if buf:
                chunks.append(buf)
            # a single huge paragraph is windowed
            if len(para) > _CHUNK_CHARS:
                for i in range(0, len(para), _CHUNK_CHARS - _CHUNK_OVERLAP):
                    chunks.append(para[i:i + _CHUNK_CHARS])
                buf = ""
            else:
                buf = para
        if len(chunks) >= _MAX_CHUNKS_PER_MODULE:
            break
    if buf and len(chunks) < _MAX_CHUNKS_PER_MODULE:
        chunks.append(buf)
    return chunks[:_MAX_CHUNKS_PER_MODULE]


def _curriculum_doc(m: CurriculumModule) -> str:
    """Build the text that represents a module in the embedding space."""
    parts = [
        f"Module: {m.title}",
        f"Code: {m.module_code}",
        f"Year {m.year}" + (f", Semester {m.semester}" if m.semester else ""),
    ]
    if m.description:
        parts.append(f"Description: {m.description}")
    if m.learning_outcomes:
        parts.append("Learning outcomes: " + "; ".join(m.learning_outcomes))
    if m.skills_developed:
        parts.append("Skills: " + ", ".join(m.skills_developed))
    if m.prerequisites:
        parts.append("Prerequisites: " + ", ".join(m.prerequisites))
    return "\n".join(parts)


def _job_doc(p: JobPosting) -> str:
    """Build the text that represents a job posting in the embedding space."""
    parts = [f"Job: {p.title}"]
    if p.employer:
        parts.append(f"Employer: {p.employer}")
    if p.location:
        parts.append(f"Location: {p.location}")
    if p.skills_required:
        parts.append("Required skills: " + ", ".join(p.skills_required))
    if p.skills_preferred:
        parts.append("Preferred skills: " + ", ".join(p.skills_preferred))
    if p.description:
        parts.append(f"Description: {p.description[:500]}")
    if p.experience_years_min is not None:
        parts.append(f"Experience: {p.experience_years_min}+ years")
    if p.salary_min_npr:
        sal = f"NPR {p.salary_min_npr:,}"
        if p.salary_max_npr:
            sal += f"–{p.salary_max_npr:,}"
        parts.append(f"Salary: {sal}")
    return "\n".join(parts)


def _pathway_doc(pw: CareerPathway) -> str:
    """Build the text for a career pathway."""
    parts = [f"Career pathway: {pw.title}"]
    if pw.description:
        parts.append(f"Description: {pw.description[:400]}")
    if pw.typical_skills:
        parts.append("Skills: " + ", ".join(pw.typical_skills))
    if pw.typical_education:
        parts.append("Education: " + "; ".join(pw.typical_education))
    if pw.related_softwarica_modules:
        parts.append("Related modules: " + ", ".join(pw.related_softwarica_modules))
    if pw.sample_employers_nepal:
        parts.append("Nepal employers: " + ", ".join(pw.sample_employers_nepal))
    return "\n".join(parts)


# ── Metadata builders ─────────────────────────────────────────────────────

def _curriculum_meta(m: CurriculumModule) -> dict[str, Any]:
    return {
        "module_code": m.module_code,
        "title": m.title,
        "programme": getattr(m, "programme", "software_engineering"),
        "year": m.year,
        "semester": m.semester or 0,
        "credits": m.credits or 0,
        "is_core": m.is_core,
        "source_type": "curriculum",
        "tier": "nepal",  # all curriculum data is local
        "tier_boost": _tier_boost("nepal"),
        "is_synthetic": False,
        "source_document": m.source_document or "",
        "skills_json": json.dumps(m.skills_developed),
        "prerequisites_json": json.dumps(m.prerequisites),
    }


def _job_meta(p: JobPosting) -> dict[str, Any]:
    return {
        "posting_id": p.posting_id,
        "source": p.source,
        "title": p.title,
        "employer": p.employer or "",
        "location": p.location or "",
        "source_type": "job_posting",
        "tier": p.tier.value,
        "tier_boost": _tier_boost(p.tier.value),
        "is_synthetic": p.is_synthetic,
        "salary_min_npr": p.salary_min_npr or 0,
        "salary_max_npr": p.salary_max_npr or 0,
        "experience_years_min": p.experience_years_min or 0,
        "skills_json": json.dumps(p.skills_required),
    }


def _pathway_meta(pw: CareerPathway) -> dict[str, Any]:
    return {
        "pathway_id": pw.pathway_id,
        "title": pw.title,
        "onet_soc_code": pw.onet_soc_code or "",
        "esco_code": pw.esco_code or "",
        "source_type": "career_pathway",
        "tier": pw.tier.value,
        "tier_boost": _tier_boost(pw.tier.value),
        "is_synthetic": False,
        "skills_json": json.dumps(pw.typical_skills),
        "modules_json": json.dumps(pw.related_softwarica_modules),
    }


# ── Ingestor ─────────────────────────────────────────────────────────────────

class Ingestor:
    """Context manager that wraps two ChromaDB collections for D.R.O.N.A."""

    def __init__(self, chroma_dir: str | None = None) -> None:
        path = chroma_dir or str(settings.chroma_dir)
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=path)

        # Curriculum collection: general-purpose English embedder
        curriculum_ef = SentenceTransformerEmbeddingFunction(
            model_name=settings.curriculum_embed_model,
            device="cpu",  # safe default; change to 'cuda' if GPU available
        )
        self._coll_curriculum = self._client.get_or_create_collection(
            name=COLL_CURRICULUM,
            embedding_function=curriculum_ef,
            metadata={"hnsw:space": "cosine"},
        )

        # Career collection: job-specialised embedder (C1 contribution)
        career_ef = SentenceTransformerEmbeddingFunction(
            model_name=settings.career_embed_model,
            device="cpu",
        )
        self._coll_career = self._client.get_or_create_collection(
            name=COLL_CAREER,
            embedding_function=career_ef,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"Ingestor ready - chroma_dir={path} | "
            f"curriculum_model={settings.curriculum_embed_model} | "
            f"career_model={settings.career_embed_model}"
        )

    # ── Generic batch add ──────────────────────────────────────────────────

    def _add_batched(
        self,
        collection: chromadb.Collection,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Add documents in batches; skip IDs already present in the collection."""
        if not ids:
            logger.debug("  No items to add - empty id list")
            return
        # chromadb >=1.x rejects get(ids=[]); guarded above. include=[] returns
        # only the ids of those already present, which we use to skip duplicates.
        existing = set(collection.get(ids=ids, include=[])["ids"])
        new_ids, new_docs, new_metas = [], [], []
        for id_, doc, meta in zip(ids, documents, metadatas, strict=False):
            if id_ not in existing:
                new_ids.append(id_)
                new_docs.append(doc)
                new_metas.append(meta)

        if not new_ids:
            logger.debug(f"  All {len(ids)} items already present - nothing to add")
            return

        for i in range(0, len(new_ids), _BATCH_SIZE):
            batch_ids = new_ids[i : i + _BATCH_SIZE]
            batch_docs = new_docs[i : i + _BATCH_SIZE]
            batch_metas = new_metas[i : i + _BATCH_SIZE]
            collection.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
            logger.debug(f"  Added batch {i // _BATCH_SIZE + 1}: {len(batch_ids)} items")

        logger.info(
            f"  → Inserted {len(new_ids)} new documents "
            f"(skipped {len(ids) - len(new_ids)} existing)"
        )

    # ── Public add methods ──────────────────────────────────────────────────

    def add_curriculum_modules(self, modules: list[CurriculumModule]) -> None:
        """Embed and store curriculum modules in the curriculum collection.

        Each module produces one summary document (title/skills/description) plus
        N content chunks from its full lesson + PDF body, so deep material - not
        just the blurb - is retrievable.
        """
        # A module shared across programmes (e.g. Computer Architecture in both
        # Computing and CS-AI) is synced once per account and collides on
        # module_code. Keep the richest copy so ids stay unique.
        by_code: dict[str, CurriculumModule] = {}
        for m in modules:
            prev = by_code.get(m.module_code)
            if prev is None or len(m.content) > len(prev.content):
                by_code[m.module_code] = m
        deduped = list(by_code.values())
        if len(deduped) < len(modules):
            logger.info(f"  deduped {len(modules) - len(deduped)} cross-account "
                        f"module copies (shared codes)")
        modules = deduped

        logger.info(f"Ingesting {len(modules)} curriculum modules → {COLL_CURRICULUM}")
        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict[str, Any]] = []
        for m in modules:
            ids.append(f"curriculum_{m.module_code}")
            docs.append(_curriculum_doc(m))
            metas.append(_curriculum_meta(m))
            for i, chunk in enumerate(_chunk_content(m.content)):
                ids.append(f"curriculum_{m.module_code}_c{i}")
                docs.append(f"{m.title} ({m.module_code}). {chunk}")
                meta = _curriculum_meta(m)
                meta["is_chunk"] = True
                metas.append(meta)
        logger.info(f"  {len(modules)} modules -> {len(ids)} documents (with content chunks)")
        self._add_batched(self._coll_curriculum, ids, docs, metas)

    def add_job_postings(self, postings: list[JobPosting]) -> None:
        """Embed and store job postings in the career collection."""
        logger.info(f"Ingesting {len(postings)} job postings → {COLL_CAREER}")
        ids = [f"job_{p.posting_id}" for p in postings]
        docs = [_job_doc(p) for p in postings]
        metas = [_job_meta(p) for p in postings]
        self._add_batched(self._coll_career, ids, docs, metas)

    def add_career_pathways(self, pathways: list[CareerPathway]) -> None:
        """Embed career pathways into BOTH collections.

        Pathways are added to both because:
        - Career collection: for matching against job-style queries
        - Curriculum collection: for matching against academic queries
        """
        logger.info(f"Ingesting {len(pathways)} career pathways → both collections")
        ids = [f"pathway_{pw.pathway_id}" for pw in pathways]
        docs = [_pathway_doc(pw) for pw in pathways]
        metas = [_pathway_meta(pw) for pw in pathways]

        self._add_batched(self._coll_curriculum, ids, docs, metas)
        self._add_batched(self._coll_career, ids, docs, metas)

    # ── Stats ───────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        return {
            "curriculum_docs": self._coll_curriculum.count(),
            "career_docs": self._coll_career.count(),
        }

    # ── Context manager ──────────────────────────────────────────────────────

    def __enter__(self) -> Ingestor:
        return self

    def __exit__(self, *args: Any) -> None:
        pass  # chromadb PersistentClient auto-flushes


def print_stats() -> None:
    """Quick CLI-friendly stats dump."""
    with Ingestor() as ing:
        s = ing.stats()
    logger.info(
        f"ChromaDB stats: curriculum={s['curriculum_docs']} docs, "
        f"career={s['career_docs']} docs"
    )
