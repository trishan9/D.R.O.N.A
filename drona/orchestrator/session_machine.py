"""
Session state machine for D.R.O.N.A.

Implements the finite state machine that governs a student advising session:

  IDLE ──student_engaged──► GREETING
    │                            │
    │                     greeted (gesture done)
    │                            │
    │                            ▼
    │                    NEEDS_ASSESSMENT
    │                            │
    │                    query_received
    │                            │
    │                            ▼
    │                         ADVISING
    │                            │
    │                   response_delivered
    │                            │
    │                            ▼
    │                         CLOSURE
    │                            │
    │                    session_closed
    │                            │
    └──────────────────────────◄─┘

Any state → IDLE via timeout trigger when the student is ABSENT or DISENGAGING
for longer than settings.session_timeout_s.

Any state → IDLE via explicit reset() call.

Design principles:
  - Pure transition function: (state, trigger, ctx) → (new_state, events)
    No side effects inside the state machine itself. Side effects (gesture
    dispatch, advising calls) are performed by the Orchestrator based on
    the events emitted by the machine.
  - SessionEvent is emitted on every state change (contracts layer).
  - Timeout logic uses wall-clock time stored in SessionContext so the machine
    can be driven from tests without real sleeps.
  - Each session gets a fresh UUID. The machine never stores student data —
    session_id is the only identifier and is discarded at session end.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import NamedTuple

from loguru import logger

from drona.contracts import (
    EngagementState,
    SessionEvent,
    SessionState,
    StudentDetection,
)
from drona.utils.settings import settings

# ── Triggers ──────────────────────────────────────────────────────────────────

class Trigger:
    STUDENT_ENGAGED    = "student_engaged"
    GREETED            = "greeted"
    QUERY_RECEIVED     = "query_received"
    RESPONSE_DELIVERED = "response_delivered"
    SESSION_CLOSED     = "session_closed"
    TIMEOUT            = "timeout"
    RESET              = "reset"


# ── Transition table ───────────────────────────────────────────────────────────
#
# (current_state, trigger) → next_state
# Unlisted combinations are no-ops (machine stays in current state).

_TRANSITIONS: dict[tuple[SessionState, str], SessionState] = {
    (SessionState.IDLE,            Trigger.STUDENT_ENGAGED):    SessionState.GREETING,
    (SessionState.GREETING,        Trigger.GREETED):             SessionState.NEEDS_ASSESSMENT,
    (SessionState.NEEDS_ASSESSMENT,Trigger.QUERY_RECEIVED):     SessionState.ADVISING,
    (SessionState.ADVISING,        Trigger.RESPONSE_DELIVERED):  SessionState.CLOSURE,
    (SessionState.CLOSURE,         Trigger.SESSION_CLOSED):      SessionState.IDLE,
    # Any non-IDLE state can timeout back to IDLE
    (SessionState.GREETING,        Trigger.TIMEOUT):             SessionState.IDLE,
    (SessionState.NEEDS_ASSESSMENT,Trigger.TIMEOUT):             SessionState.IDLE,
    (SessionState.ADVISING,        Trigger.TIMEOUT):             SessionState.IDLE,
    (SessionState.CLOSURE,         Trigger.TIMEOUT):             SessionState.IDLE,
    # Explicit reset from any state
    (SessionState.GREETING,        Trigger.RESET):               SessionState.IDLE,
    (SessionState.NEEDS_ASSESSMENT,Trigger.RESET):               SessionState.IDLE,
    (SessionState.ADVISING,        Trigger.RESET):               SessionState.IDLE,
    (SessionState.CLOSURE,         Trigger.RESET):               SessionState.IDLE,
}


# ── Session context (carries mutable per-session state) ───────────────────────

@dataclass
class SessionContext:
    """Mutable context carried through a session lifecycle."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionState = SessionState.IDLE
    last_detection_time: float = field(default_factory=time.monotonic)
    last_engaged_time: float | None = None
    pending_query: str | None = None
    query_count: int = 0
    events: list[SessionEvent] = field(default_factory=list)

    def record_event(self, from_state: SessionState, to_state: SessionState, trigger: str) -> SessionEvent:
        ev = SessionEvent(
            session_id=self.session_id,
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
        )
        self.events.append(ev)
        return ev


# ── Transition result ──────────────────────────────────────────────────────────

class TransitionResult(NamedTuple):
    transitioned: bool
    event: SessionEvent | None
    new_state: SessionState


# ── State machine ──────────────────────────────────────────────────────────────

class SessionMachine:
    """Finite state machine for a D.R.O.N.A. advising session.

    Thread-safety: Not thread-safe. All calls must be from the same thread
    (the orchestrator's main loop). This is by design for Phase 1 simplicity.
    """

    def __init__(self, timeout_s: float | None = None) -> None:
        self._timeout_s = timeout_s if timeout_s is not None else settings.session_timeout_s
        self._ctx = SessionContext()

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def state(self) -> SessionState:
        return self._ctx.state

    @property
    def session_id(self) -> str:
        return self._ctx.session_id

    @property
    def pending_query(self) -> str | None:
        return self._ctx.pending_query

    @property
    def events(self) -> list[SessionEvent]:
        return list(self._ctx.events)

    # ── Trigger interface ──────────────────────────────────────────────────────

    def fire(self, trigger: str) -> TransitionResult:
        """Fire a trigger and apply any valid transition.

        Args:
            trigger: One of the Trigger constants.

        Returns:
            TransitionResult(transitioned, event, new_state).
        """
        key = (self._ctx.state, trigger)
        next_state = _TRANSITIONS.get(key)

        if next_state is None:
            return TransitionResult(False, None, self._ctx.state)

        from_state = self._ctx.state
        self._ctx.state = next_state

        # On returning to IDLE, start a fresh session
        if next_state == SessionState.IDLE:
            self._ctx.session_id = str(uuid.uuid4())
            self._ctx.pending_query = None
            self._ctx.query_count = 0

        event = self._ctx.record_event(from_state, next_state, trigger)
        logger.info(
            f"[{self._ctx.session_id[:8]}] "
            f"{from_state.value} ──{trigger}──► {next_state.value}"
        )
        return TransitionResult(True, event, next_state)

    def reset(self) -> TransitionResult:
        """Hard reset to IDLE regardless of current state."""
        if self._ctx.state == SessionState.IDLE:
            return TransitionResult(False, None, SessionState.IDLE)
        return self.fire(Trigger.RESET)

    # ── Detection feed ─────────────────────────────────────────────────────────

    def feed_detection(self, detection: StudentDetection) -> TransitionResult:
        """Update machine based on a new StudentDetection.

        This is called every perception tick. The machine applies:
          - IDLE → GREETING when ENGAGED detected
          - Timeout to IDLE when student ABSENT/DISENGAGING too long

        Does NOT trigger GREETED, QUERY_RECEIVED, etc. — those are fired by
        the Orchestrator at appropriate moments in the execution flow.

        Args:
            detection: Latest StudentDetection from the perception layer.

        Returns:
            TransitionResult (may have transitioned=False if no change).
        """
        now = time.monotonic()
        self._ctx.last_detection_time = now

        engaged = detection.engagement == EngagementState.ENGAGED
        absent_or_leaving = detection.engagement in (
            EngagementState.ABSENT, EngagementState.DISENGAGING
        )

        # IDLE → GREETING on engagement
        if self._ctx.state == SessionState.IDLE and engaged:
            self._ctx.last_engaged_time = now
            return self.fire(Trigger.STUDENT_ENGAGED)

        # Track engaged time for timeout reset
        if engaged:
            self._ctx.last_engaged_time = now

        # Timeout: student gone for too long
        if absent_or_leaving and self._ctx.state != SessionState.IDLE:
            since_last_engaged = now - (self._ctx.last_engaged_time or now)
            if since_last_engaged >= self._timeout_s:
                logger.info(
                    f"Session timeout after {since_last_engaged:.1f}s "
                    f"without engagement"
                )
                return self.fire(Trigger.TIMEOUT)

        return TransitionResult(False, None, self._ctx.state)

    # ── Query intake ───────────────────────────────────────────────────────────

    def submit_query(self, query_text: str) -> TransitionResult:
        """Accept a student query and trigger QUERY_RECEIVED if in NEEDS_ASSESSMENT.

        Args:
            query_text: The student's advising question.

        Returns:
            TransitionResult — transitioned only if state was NEEDS_ASSESSMENT.
        """
        if self._ctx.state != SessionState.NEEDS_ASSESSMENT:
            logger.warning(
                f"Query submitted in state {self._ctx.state.value} — ignored"
            )
            return TransitionResult(False, None, self._ctx.state)

        self._ctx.pending_query = query_text
        self._ctx.query_count += 1
        return self.fire(Trigger.QUERY_RECEIVED)

    # ── Lifecycle hooks ────────────────────────────────────────────────────────

    def mark_greeted(self) -> TransitionResult:
        """Call after GREET gesture completes."""
        return self.fire(Trigger.GREETED)

    def mark_response_delivered(self) -> TransitionResult:
        """Call after advising response has been spoken/displayed."""
        return self.fire(Trigger.RESPONSE_DELIVERED)

    def mark_session_closed(self) -> TransitionResult:
        """Call after FAREWELL gesture completes."""
        result = self.fire(Trigger.SESSION_CLOSED)
        if result.transitioned:
            self._ctx.pending_query = None
        return result

    # ── Introspection ─────────────────────────────────────────────────────────

    def session_summary(self) -> dict[str, object]:
        """Return a summary of the current session for logging/evaluation."""
        return {
            "session_id": self._ctx.session_id,
            "state": self._ctx.state.value,
            "query_count": self._ctx.query_count,
            "event_count": len(self._ctx.events),
            "events": [
                {
                    "from": e.from_state.value,
                    "to": e.to_state.value,
                    "trigger": e.trigger,
                }
                for e in self._ctx.events
            ],
        }
