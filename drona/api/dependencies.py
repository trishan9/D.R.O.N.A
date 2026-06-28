"""
Advisor singleton + dependency injection for the API.

The advisor (LangGraph-backed by default) loads embedding models, ChromaDB, and
the reranker - expensive - so it is created ONCE, lazily, on first use. Tests
override ``get_advisor`` via FastAPI dependency_overrides to inject a stub.
"""

from __future__ import annotations

from typing import Any, Protocol

from loguru import logger

from drona.contracts import AdvisingQuery, AdvisingResponse


class Advisor(Protocol):
    """Anything with an .advise(query) -> AdvisingResponse method."""

    def advise(self, query: AdvisingQuery) -> AdvisingResponse: ...


_advisor: Any = None


def get_advisor() -> Advisor:
    """Return the process-wide advisor, building it on first call.

    Defaults to the LangGraph orchestrator (AdvisingGraph). If LangGraph isn't
    installed, falls back to the imperative AdvisingEngine so the API still runs.
    """
    global _advisor
    if _advisor is None:
        try:
            from drona.advising.graph import AdvisingGraph

            _advisor = AdvisingGraph()
            logger.info("Advisor: LangGraph orchestrator initialised")
        except Exception as exc:  # pragma: no cover - depends on optional deps
            from drona.advising.engine import AdvisingEngine

            logger.warning(f"LangGraph unavailable ({exc}); using AdvisingEngine")
            _advisor = AdvisingEngine()
    return _advisor


def set_advisor(advisor: Advisor) -> None:
    """Inject an advisor (used by tests / alternate orchestrators)."""
    global _advisor
    _advisor = advisor


def orchestrator_name() -> str:
    return type(get_advisor()).__name__ if _advisor is not None else "lazy"
