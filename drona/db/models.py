"""
SQLAlchemy ORM models for the PostgreSQL + pgvector backend.

These mirror the Pydantic contracts in ``drona.contracts`` so the same data can
live in ChromaDB (dev), pgvector (prod), or Pinecone (cloud) interchangeably.
The three-tier provenance (``DataTier``) is stored as a plain string column and
indexed, because tier-aware retrieval boost (proposal contribution C4) filters
and weights on it constantly.

Vector columns use pgvector ``Vector`` with dimensions fixed by the encoders
(see ``drona.db.__init__``). HNSW indexes are created in the Alembic migration,
not here, because index build parameters are deployment-specific.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from drona.db import CAREER_EMBED_DIM, CURRICULUM_EMBED_DIM


class Base(DeclarativeBase):
    """Declarative base — Alembic autogenerate targets this metadata."""


class CurriculumModuleORM(Base):
    __tablename__ = "curriculum_modules"

    module_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    year: Mapped[int] = mapped_column(Integer)
    semester: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    learning_outcomes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    prerequisites: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    skills_developed: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    is_core: Mapped[bool] = mapped_column(Boolean, default=True)
    source_document: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # bge-small-en-v1.5 embedding of title + description + outcomes
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(CURRICULUM_EMBED_DIM), nullable=True
    )


class JobPostingORM(Base):
    __tablename__ = "job_postings"

    posting_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    tier: Mapped[str] = mapped_column(String(16), index=True)  # DataTier value
    title: Mapped[str] = mapped_column(String(512))
    employer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    skills_required: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    skills_preferred: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    experience_years_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_min_npr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max_npr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    posted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    synthetic_anchor_ids: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    # JobBERT-v3 embedding of title + skills + description
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(CAREER_EMBED_DIM), nullable=True
    )


class CareerPathwayORM(Base):
    __tablename__ = "career_pathways"

    pathway_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    tier: Mapped[str] = mapped_column(String(16), index=True)
    onet_soc_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    esco_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    typical_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    typical_education: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    related_softwarica_modules: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=list
    )
    sample_employers_nepal: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(CAREER_EMBED_DIM), nullable=True
    )


__all__ = ["Base", "CurriculumModuleORM", "JobPostingORM", "CareerPathwayORM"]
