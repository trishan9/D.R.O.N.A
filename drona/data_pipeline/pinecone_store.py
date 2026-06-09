"""
Pinecone (managed cloud vector store) ingestion path for D.R.O.N.A.

Cloud parallel to the local ChromaDB ingestor, for the thesis demonstration of a
production managed vector DB. Keeps the dual-embedding scheme (C1): a
curriculum index (bge, 384-dim) and a career index (JobBERT-v3, 1024-dim).

Tier provenance (C4) travels in each vector's metadata so tier-aware boosting
works the same as in Chroma/pgvector. All heavy imports are LAZY; activate via
VECTOR_BACKEND=pinecone with PINECONE_API_KEY set.
"""

from __future__ import annotations

from functools import lru_cache

from loguru import logger

from drona.contracts import CareerPathway, CurriculumModule, JobPosting
from drona.data_pipeline.ingest import (
    _curriculum_doc,
    _curriculum_meta,
    _job_doc,
    _job_meta,
    _pathway_doc,
    _pathway_meta,
)
from drona.db import CAREER_EMBED_DIM, CURRICULUM_EMBED_DIM
from drona.utils.settings import settings


@lru_cache(maxsize=2)
def _encoder(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device="cpu")


def _client():
    from pinecone import Pinecone

    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY not set")
    return Pinecone(api_key=settings.pinecone_api_key)


def ensure_indexes() -> None:
    """Create the curriculum + career indexes if they don't exist."""
    from pinecone import ServerlessSpec

    pc = _client()
    existing = {i["name"] for i in pc.list_indexes()}
    spec = ServerlessSpec(cloud="aws", region=settings.pinecone_environment)
    for name, dim in (
        (settings.pinecone_index_curriculum, CURRICULUM_EMBED_DIM),
        (settings.pinecone_index_career, CAREER_EMBED_DIM),
    ):
        if name not in existing:
            logger.info(f"Creating Pinecone index {name} (dim={dim}, cosine)")
            pc.create_index(name=name, dimension=dim, metric="cosine", spec=spec)


def _upsert(index_name: str, model_name: str, ids: list[str], docs: list[str], metas: list[dict]) -> int:
    if not ids:
        return 0
    pc = _client()
    index = pc.Index(index_name)
    vecs = _encoder(model_name).encode(docs, normalize_embeddings=True)
    payload = [
        {"id": id_, "values": v.tolist(), "metadata": meta}
        for id_, v, meta in zip(ids, vecs, metas, strict=True)
    ]
    for i in range(0, len(payload), 100):
        index.upsert(vectors=payload[i : i + 100])
    logger.success(f"pinecone: upserted {len(payload)} vectors → {index_name}")
    return len(payload)


def upsert_curriculum(modules: list[CurriculumModule]) -> int:
    return _upsert(
        settings.pinecone_index_curriculum,
        settings.curriculum_embed_model,
        [f"curriculum_{m.module_code}" for m in modules],
        [_curriculum_doc(m) for m in modules],
        [_curriculum_meta(m) for m in modules],
    )


def upsert_jobs(postings: list[JobPosting]) -> int:
    return _upsert(
        settings.pinecone_index_career,
        settings.career_embed_model,
        [f"job_{p.posting_id}" for p in postings],
        [_job_doc(p) for p in postings],
        [_job_meta(p) for p in postings],
    )


def upsert_pathways(pathways: list[CareerPathway]) -> int:
    return _upsert(
        settings.pinecone_index_career,
        settings.career_embed_model,
        [f"pathway_{pw.pathway_id}" for pw in pathways],
        [_pathway_doc(pw) for pw in pathways],
        [_pathway_meta(pw) for pw in pathways],
    )
