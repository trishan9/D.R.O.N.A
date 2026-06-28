"""initial schema: pgvector extension + three core tables + HNSW indexes

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-09

Creates the dual-embedding (contribution C1) store: curriculum modules
(384-dim bge), job postings and career pathways (1024-dim JobBERT-v3). HNSW
indexes use cosine distance (vector_cosine_ops) because both encoders are
trained for cosine similarity. The `tier` columns are indexed for the
tier-aware retrieval boost (contribution C4).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op
from drona.db import CAREER_EMBED_DIM, CURRICULUM_EMBED_DIM

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "curriculum_modules",
        sa.Column("module_code", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("semester", sa.Integer, nullable=True),
        sa.Column("credits", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("learning_outcomes", sa.ARRAY(sa.Text), server_default="{}"),
        sa.Column("prerequisites", sa.ARRAY(sa.String(32)), server_default="{}"),
        sa.Column("skills_developed", sa.ARRAY(sa.Text), server_default="{}"),
        sa.Column("is_core", sa.Boolean, server_default=sa.true()),
        sa.Column("source_document", sa.String(512), nullable=True),
        sa.Column("embedding", Vector(CURRICULUM_EMBED_DIM), nullable=True),
    )

    op.create_table(
        "job_postings",
        sa.Column("posting_id", sa.String(64), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("employer", sa.String(256), nullable=True),
        sa.Column("location", sa.String(256), nullable=True),
        sa.Column("skills_required", sa.ARRAY(sa.Text), server_default="{}"),
        sa.Column("skills_preferred", sa.ARRAY(sa.Text), server_default="{}"),
        sa.Column("experience_years_min", sa.Integer, nullable=True),
        sa.Column("salary_min_npr", sa.Integer, nullable=True),
        sa.Column("salary_max_npr", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("posted_date", sa.DateTime, nullable=True),
        sa.Column("collected_date", sa.DateTime, server_default=sa.func.now()),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("is_synthetic", sa.Boolean, server_default=sa.false()),
        sa.Column("synthetic_anchor_ids", sa.ARRAY(sa.String(64)), server_default="{}"),
        sa.Column("embedding", Vector(CAREER_EMBED_DIM), nullable=True),
    )
    op.create_index("ix_job_postings_tier", "job_postings", ["tier"])
    op.create_index("ix_job_postings_is_synthetic", "job_postings", ["is_synthetic"])

    op.create_table(
        "career_pathways",
        sa.Column("pathway_id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("onet_soc_code", sa.String(16), nullable=True),
        sa.Column("esco_code", sa.String(32), nullable=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("typical_skills", sa.ARRAY(sa.Text), server_default="{}"),
        sa.Column("typical_education", sa.ARRAY(sa.Text), server_default="{}"),
        sa.Column("related_softwarica_modules", sa.ARRAY(sa.String(32)), server_default="{}"),
        sa.Column("sample_employers_nepal", sa.ARRAY(sa.Text), server_default="{}"),
        sa.Column("embedding", Vector(CAREER_EMBED_DIM), nullable=True),
    )
    op.create_index("ix_career_pathways_tier", "career_pathways", ["tier"])

    # HNSW cosine indexes - built after tables so initial bulk insert is fast.
    op.execute(
        "CREATE INDEX ix_curriculum_embedding ON curriculum_modules "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_job_postings_embedding ON job_postings "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_career_pathways_embedding ON career_pathways "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("career_pathways")
    op.drop_table("job_postings")
    op.drop_table("curriculum_modules")
    # Extension left in place - other DBs may share it.
