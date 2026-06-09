"""
D.R.O.N.A. relational + vector persistence layer (PostgreSQL 16 + pgvector).

This package is OPTIONAL at runtime: ChromaDB (in core deps) is the default
local backend, so importing `drona` never requires SQLAlchemy/pgvector. Only
import from `drona.db` when `settings.vector_backend == "pgvector"` or when
running Alembic migrations.

Embedding dimensions are fixed by the encoders (see contracts in the proposal,
contribution C1 dual-embedding):
  - curriculum text  -> BAAI/bge-small-en-v1.5  -> 384 dims
  - career/job text  -> TechWolf/JobBERT-v3     -> 1024 dims
"""

from __future__ import annotations

CURRICULUM_EMBED_DIM = 384  # BAAI/bge-small-en-v1.5
CAREER_EMBED_DIM = 1024  # TechWolf/JobBERT-v3 hidden size

__all__ = ["CURRICULUM_EMBED_DIM", "CAREER_EMBED_DIM"]
