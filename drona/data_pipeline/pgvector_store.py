"""
PostgreSQL + pgvector ingestion path for D.R.O.N.A.

This is the production-grade parallel to the local ChromaDB ingestor
(drona.data_pipeline.ingest). It embeds the same dual-embedding scheme
(contribution C1) - bge for curriculum, JobBERT-v3 for career - and upserts
into the pgvector tables defined in drona.db.models (migration 0001).

All heavy imports (SQLAlchemy, pgvector, sentence-transformers) are LAZY so the
core system never hard-depends on them. Activate via VECTOR_BACKEND=pgvector
after `docker compose up -d db` and `alembic upgrade head`.
"""

from __future__ import annotations

from functools import lru_cache

from loguru import logger

from drona.contracts import CareerPathway, CurriculumModule, JobPosting
from drona.data_pipeline.ingest import _curriculum_doc, _job_doc, _pathway_doc
from drona.utils.settings import settings


@lru_cache(maxsize=2)
def _encoder(model_name: str):
    """Cache one SentenceTransformer per model name (cold start is expensive)."""
    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading encoder {model_name} (cpu)")
    return SentenceTransformer(model_name, device="cpu")


def _embed(model_name: str, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vecs = _encoder(model_name).encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def upsert_curriculum(modules: list[CurriculumModule]) -> int:
    """Embed + upsert curriculum modules into pgvector."""
    from sqlalchemy.dialects.postgresql import insert

    from drona.db.models import CurriculumModuleORM
    from drona.db.session import get_session

    if not modules:
        return 0
    embeddings = _embed(settings.curriculum_embed_model, [_curriculum_doc(m) for m in modules])
    rows = []
    for m, emb in zip(modules, embeddings, strict=True):
        rows.append(
            {
                "module_code": m.module_code,
                "title": m.title,
                "year": m.year,
                "semester": m.semester,
                "credits": m.credits,
                "description": m.description,
                "learning_outcomes": m.learning_outcomes,
                "prerequisites": m.prerequisites,
                "skills_developed": m.skills_developed,
                "is_core": m.is_core,
                "source_document": m.source_document,
                "embedding": emb,
            }
        )
    with get_session() as s:
        stmt = insert(CurriculumModuleORM).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["module_code"],
            set_={c: stmt.excluded[c] for c in rows[0] if c != "module_code"},
        )
        s.execute(stmt)
    logger.success(f"pgvector: upserted {len(rows)} curriculum modules")
    return len(rows)


def upsert_jobs(postings: list[JobPosting]) -> int:
    """Embed + upsert job postings into pgvector."""
    from sqlalchemy.dialects.postgresql import insert

    from drona.db.models import JobPostingORM
    from drona.db.session import get_session

    if not postings:
        return 0
    embeddings = _embed(settings.career_embed_model, [_job_doc(p) for p in postings])
    rows = []
    for p, emb in zip(postings, embeddings, strict=True):
        rows.append(
            {
                "posting_id": p.posting_id,
                "source": p.source,
                "tier": p.tier.value,
                "title": p.title,
                "employer": p.employer,
                "location": p.location,
                "skills_required": p.skills_required,
                "skills_preferred": p.skills_preferred,
                "experience_years_min": p.experience_years_min,
                "salary_min_npr": p.salary_min_npr,
                "salary_max_npr": p.salary_max_npr,
                "description": p.description,
                "posted_date": p.posted_date,
                "source_url": p.source_url,
                "is_synthetic": p.is_synthetic,
                "synthetic_anchor_ids": p.synthetic_anchor_ids,
                "embedding": emb,
            }
        )
    with get_session() as s:
        stmt = insert(JobPostingORM).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["posting_id"],
            set_={c: stmt.excluded[c] for c in rows[0] if c != "posting_id"},
        )
        s.execute(stmt)
    logger.success(f"pgvector: upserted {len(rows)} job postings")
    return len(rows)


def upsert_pathways(pathways: list[CareerPathway]) -> int:
    """Embed + upsert career pathways into pgvector."""
    from sqlalchemy.dialects.postgresql import insert

    from drona.db.models import CareerPathwayORM
    from drona.db.session import get_session

    if not pathways:
        return 0
    embeddings = _embed(settings.career_embed_model, [_pathway_doc(pw) for pw in pathways])
    rows = []
    for pw, emb in zip(pathways, embeddings, strict=True):
        rows.append(
            {
                "pathway_id": pw.pathway_id,
                "title": pw.title,
                "tier": pw.tier.value,
                "onet_soc_code": pw.onet_soc_code,
                "esco_code": pw.esco_code,
                "description": pw.description,
                "typical_skills": pw.typical_skills,
                "typical_education": pw.typical_education,
                "related_softwarica_modules": pw.related_softwarica_modules,
                "sample_employers_nepal": pw.sample_employers_nepal,
                "embedding": emb,
            }
        )
    with get_session() as s:
        stmt = insert(CareerPathwayORM).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["pathway_id"],
            set_={c: stmt.excluded[c] for c in rows[0] if c != "pathway_id"},
        )
        s.execute(stmt)
    logger.success(f"pgvector: upserted {len(rows)} career pathways")
    return len(rows)
