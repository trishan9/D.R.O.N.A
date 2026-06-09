"""
SQLAlchemy engine + session factory for the pgvector backend.

Imported lazily (only when ``settings.vector_backend == "pgvector"``) so the
core system never hard-depends on SQLAlchemy being installed.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from drona.utils.settings import settings

# pool_pre_ping avoids stale-connection errors after the DB container restarts.
_engine = create_engine(settings.postgres_dsn, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def get_engine():
    """Return the process-wide SQLAlchemy engine."""
    return _engine


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session with commit/rollback handling."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["get_engine", "get_session", "SessionLocal"]
