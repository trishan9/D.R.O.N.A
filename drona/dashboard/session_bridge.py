"""
Session bridge for D.R.O.N.A. dashboard.

Manages communication between the Streamlit UI thread and the advising engine.
Streamlit re-runs the entire script on every interaction, so we use
`st.session_state` as the persistence layer - all mutable state lives there.

The bridge is intentionally NOT a singleton - each Streamlit session gets its
own AdvisingEngine instance (lazy-initialised on first query). This avoids
shared model state across concurrent browser sessions.

Why not run the full Orchestrator here?
  The Orchestrator's main loop is camera-driven. The dashboard is a web UI -
  no camera feed. The dashboard uses the AdvisingEngine directly (stages 1-4
  of the pipeline: retrieve → rerank → detect bias → generate). The
  GestureDispatcher is not called from the dashboard - gestures are driven
  by the physical robot via the Orchestrator, which runs separately.

Thread safety:
  Streamlit's execution model is single-threaded per session. No locking
  needed within a single browser tab.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drona.advising.engine import AdvisingEngine, make_query
from drona.contracts import AdvisingResponse, BiasFlag


# ── Session entry ─────────────────────────────────────────────────────────────

@dataclass
class QueryEntry:
    """One turn in the advising conversation."""
    query_text: str
    response: AdvisingResponse
    query_number: int


# ── Bridge ────────────────────────────────────────────────────────────────────

class SessionBridge:
    """Stateless bridge - all state lives in the provided state dict
    (intended to be ``st.session_state`` in production, a plain dict in tests).
    """

    _ENGINE_KEY = "_drona_engine"
    _HISTORY_KEY = "query_history"
    _QUERY_COUNT_KEY = "query_count"
    _PROFILE_KEY = "student_profile"

    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state
        if self._HISTORY_KEY not in state:
            state[self._HISTORY_KEY] = []
        if self._QUERY_COUNT_KEY not in state:
            state[self._QUERY_COUNT_KEY] = 0

    # ── Engine ────────────────────────────────────────────────────────────────

    def _engine(self) -> AdvisingEngine:
        if self._ENGINE_KEY not in self._state:
            self._state[self._ENGINE_KEY] = AdvisingEngine()
        return self._state[self._ENGINE_KEY]  # type: ignore[return-value]

    # ── Profile helpers ────────────────────────────────────────────────────────

    def set_profile(
        self,
        year: int | None = None,
        completed_modules: list[str] | None = None,
        skills: list[str] | None = None,
        geography: str = "any",
    ) -> None:
        """Store student profile settings in session state."""
        self._state[self._PROFILE_KEY] = {
            "year": year,
            "completed": completed_modules or [],
            "skills": skills or [],
            "geography": geography,
        }

    def _get_profile(self) -> dict[str, Any]:
        return self._state.get(self._PROFILE_KEY, {})

    # ── Query submission ───────────────────────────────────────────────────────

    def submit(
        self,
        query_text: str,
        max_pathways: int = 3,
    ) -> AdvisingResponse:
        """Submit a query to the advising engine and store the result.

        Args:
            query_text: The student's question.
            max_pathways: Number of pathways to request (anti-anchoring default: 3).

        Returns:
            The AdvisingResponse, also appended to history.
        """
        profile = self._get_profile()
        adv_query = make_query(
            text=query_text,
            year=profile.get("year"),
            completed=profile.get("completed", []),
            skills=profile.get("skills", []),
            geography=profile.get("geography", "any"),
            max_pathways=max_pathways,
        )

        response = self._engine().advise(adv_query)

        self._state[self._QUERY_COUNT_KEY] += 1
        entry = QueryEntry(
            query_text=query_text,
            response=response,
            query_number=self._state[self._QUERY_COUNT_KEY],
        )
        self._state[self._HISTORY_KEY].append(entry)
        return response

    # ── History ────────────────────────────────────────────────────────────────

    @property
    def history(self) -> list[QueryEntry]:
        return self._state[self._HISTORY_KEY]

    @property
    def query_count(self) -> int:
        return self._state[self._QUERY_COUNT_KEY]

    def clear_history(self) -> None:
        self._state[self._HISTORY_KEY] = []
        self._state[self._QUERY_COUNT_KEY] = 0

    # ── Statistics ─────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Aggregate statistics across all queries in this session."""
        if not self.history:
            return {
                "query_count": 0,
                "total_pathways": 0,
                "total_bias_flags": 0,
                "bias_type_counts": {},
                "refusal_count": 0,
                "avg_generation_ms": None,
                "nepal_citations": 0,
                "intl_citations": 0,
            }

        bias_counts: dict[str, int] = {}
        total_pathways = 0
        total_flags = 0
        refusals = 0
        gen_times: list[int] = []
        nepal_cits = 0
        intl_cits = 0

        for entry in self.history:
            r = entry.response
            total_pathways += len(r.pathways)
            total_flags += len(r.bias_flags)
            if r.refusal:
                refusals += 1
            if r.generation_time_ms is not None:
                gen_times.append(r.generation_time_ms)
            for flag in r.bias_flags:
                bias_counts[flag.bias_type] = bias_counts.get(flag.bias_type, 0) + 1
            for pw in r.pathways:
                for cit in pw.citations:
                    if cit.tier.value == "nepal":
                        nepal_cits += 1
                    elif cit.tier.value == "international":
                        intl_cits += 1

        return {
            "query_count": self.query_count,
            "total_pathways": total_pathways,
            "total_bias_flags": total_flags,
            "bias_type_counts": bias_counts,
            "refusal_count": refusals,
            "avg_generation_ms": int(sum(gen_times) / len(gen_times)) if gen_times else None,
            "nepal_citations": nepal_cits,
            "intl_citations": intl_cits,
        }
