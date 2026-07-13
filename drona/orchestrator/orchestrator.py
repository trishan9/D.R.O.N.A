"""
D.R.O.N.A. orchestrator - top-level session coordinator.

Connects all Phase 1 subsystems into a single run loop:

  Perception tick  →  StudentDetection
  SessionMachine   →  state transitions + SessionEvent emissions
  GestureDispatcher → executes robot gestures (GREET, LISTEN, NOD, FAREWELL)
  AdvisingEngine   →  AdvisingQuery → AdvisingResponse

Execution model (Phase 1):
  The orchestrator runs a synchronous tick loop. Each tick:
    1. Calls detector.detect() → StudentDetection
    2. Feeds detection to session_machine.feed_detection() → possible transition
    3. On state entry, performs the associated action (gesture + advising)
    4. Emits SessionEvent to event_log

Query intake (Phase 1):
  Queries arrive via orchestrator.submit_query(text). This is called by the
  Streamlit dashboard or the CLI. The orchestrator holds the query until the
  machine reaches NEEDS_ASSESSMENT, then advances to ADVISING.

Phase 2 upgrade path:
  In Phase 2, ticks become ROS2 subscription callbacks (one per sensor topic).
  submit_query() becomes a ROS2 service call. The orchestrator's internal
  structure stays the same - only the transport layer changes.

Thread safety:
  submit_query() is safe to call from a different thread (e.g. Streamlit).
  It uses a simple queue so the main loop never blocks on I/O.
"""

from __future__ import annotations

import queue
import time
from collections.abc import Callable
from dataclasses import dataclass

from loguru import logger

from drona.advising.engine import AdvisingEngine, make_query
from drona.contracts import (
    AdvisingResponse,
    GestureType,
    SessionEvent,
    SessionState,
    StudentDetection,
)
from drona.interaction.gesture_dispatcher import GestureDispatcher, make_action
from drona.orchestrator.session_machine import SessionMachine
from drona.perception.mediapipe_detector import BaseDetector, StubDetector
from drona.utils.settings import settings

# ── Session record ────────────────────────────────────────────────────────────

@dataclass
class SessionRecord:
    """Immutable record of a completed session (for evaluation and logging)."""
    session_id: str
    events: list[SessionEvent]
    responses: list[AdvisingResponse]
    duration_s: float
    query_count: int


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    """Top-level coordinator for a D.R.O.N.A. advising session.

    Usage (Phase 1 interactive loop):
        orch = Orchestrator()
        orch.run(max_ticks=200)  # blocks; submit_query() from another thread

    Usage (single-tick test):
        orch = Orchestrator(detector=StubDetector(...))
        orch.tick()
    """

    def __init__(
        self,
        detector: BaseDetector | None = None,
        engine: AdvisingEngine | None = None,
        dispatcher: GestureDispatcher | None = None,
        session_machine: SessionMachine | None = None,
        on_response: Callable[[AdvisingResponse], None] | None = None,
        on_event: Callable[[SessionEvent], None] | None = None,
    ) -> None:
        self._detector = detector or StubDetector()
        self._engine = engine or AdvisingEngine()
        self._dispatcher = dispatcher or GestureDispatcher()
        self._machine = session_machine or SessionMachine()
        self._on_response = on_response
        self._on_event = on_event

        self._query_queue: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._completed_sessions: list[SessionRecord] = []
        self._session_start: float = time.monotonic()
        self._session_responses: list[AdvisingResponse] = []
        self._running = False

    # ── Public interface ───────────────────────────────────────────────────────

    def submit_query(self, text: str) -> None:
        """Accept a student query from any thread (Streamlit, CLI, test).

        The query is enqueued and consumed by the main loop on the next tick
        where the machine is in NEEDS_ASSESSMENT state.
        """
        if not text.strip():
            return
        logger.info(f"Query submitted: {text[:80]}…")
        self._query_queue.put(text.strip())

    def run(
        self,
        max_ticks: int | None = None,
        tick_interval_s: float | None = None,
    ) -> None:
        """Run the orchestrator loop synchronously.

        Args:
            max_ticks: Stop after this many ticks (None = run until stopped).
            tick_interval_s: Sleep between ticks (defaults to settings).
        """
        interval = tick_interval_s or settings.perception_interval_s
        self._running = True
        tick = 0

        logger.info("Orchestrator started")
        try:
            while self._running:
                if max_ticks is not None and tick >= max_ticks:
                    break
                self.tick()
                time.sleep(interval)
                tick += 1
        finally:
            self._running = False
            self._dispatcher.close()
            logger.info(f"Orchestrator stopped after {tick} ticks")

    def stop(self) -> None:
        """Signal the run loop to stop after the current tick."""
        self._running = False

    def tick(self) -> SessionEvent | None:
        """Execute one orchestrator tick. Returns the SessionEvent if a state
        transition occurred, else None."""
        detection = self._detector.detect()
        result = self._machine.feed_detection(detection)

        if result.transitioned and result.event:
            self._dispatch_on_entry(result.new_state, detection)
            if self._on_event:
                self._on_event(result.event)
            return result.event

        # Check if a query arrived and machine is in NEEDS_ASSESSMENT
        if self._machine.state == SessionState.NEEDS_ASSESSMENT:
            try:
                query_text = self._query_queue.get_nowait()
            except queue.Empty:
                query_text = None

            if query_text:
                self._run_advising(query_text)

        return None

    # ── State entry actions ────────────────────────────────────────────────────

    def _dispatch_on_entry(
        self, state: SessionState, detection: StudentDetection
    ) -> None:
        """Perform side effects when entering a new state."""
        if state == SessionState.GREETING:
            self._session_start = time.monotonic()
            self._session_responses = []
            logger.info(
                f"New session [{self._machine.session_id[:8]}] - "
                f"student at {detection.estimated_distance_m:.1f}m"
                if detection.estimated_distance_m else
                f"New session [{self._machine.session_id[:8]}]"
            )
            self._do_greet()

        elif state == SessionState.IDLE:
            # timeout path: session wasn't closed cleanly via _do_farewell
            self._finalise_session()

    def _do_greet(self) -> None:
        """Execute GREET gesture then advance to NEEDS_ASSESSMENT."""
        action = make_action(GestureType.GREET, speech_text="Hello! I'm DRONA.")
        result = self._dispatcher.execute(action)
        logger.debug(f"GREET gesture: success={result.success}, {result.actual_duration_seconds:.2f}s")
        self._machine.mark_greeted()
        logger.info("Waiting for student query…")

    def _run_advising(self, query_text: str) -> None:
        """Fire QUERY_RECEIVED, run advising pipeline, deliver response."""
        # Advance to ADVISING
        self._machine.submit_query(query_text)
        if self._machine.state != SessionState.ADVISING:
            logger.warning("State did not advance to ADVISING - skipping")
            return

        # LISTEN gesture during processing
        listen_action = make_action(GestureType.LISTEN, speech_text="Let me think about that…")
        self._dispatcher.execute(listen_action)

        # Run advising
        adv_query = make_query(text=query_text, session_id=self._machine.session_id)
        response = self._engine.advise(adv_query)
        self._session_responses.append(response)

        if self._on_response:
            self._on_response(response)

        logger.info(
            f"Response: {len(response.pathways)} pathways, "
            f"refusal={response.refusal}, "
            f"biases={[f.bias_type for f in response.bias_flags]}"
        )

        # NOD to acknowledge delivery
        nod_action = make_action(GestureType.NOD, speech_text=response.speak_text)
        self._dispatcher.execute(nod_action)

        # Advance to CLOSURE
        self._machine.mark_response_delivered()
        self._do_farewell()

    def _do_farewell(self) -> None:
        """Execute FAREWELL gesture then close the session."""
        action = make_action(GestureType.FAREWELL, speech_text="Good luck! See you next time.")
        result = self._dispatcher.execute(action)
        logger.debug(f"FAREWELL gesture: {result.actual_duration_seconds:.2f}s")
        self._machine.mark_session_closed()
        self._finalise_session()

    def _finalise_session(self) -> None:
        """Record the completed session for evaluation."""
        duration = time.monotonic() - self._session_start
        record = SessionRecord(
            session_id=self._machine.session_id,
            events=self._machine.events,
            responses=list(self._session_responses),
            duration_s=duration,
            query_count=len(self._session_responses),
        )
        self._completed_sessions.append(record)
        logger.info(
            f"Session [{record.session_id[:8]}] complete - "
            f"{record.query_count} queries in {duration:.1f}s"
        )

    # ── Introspection ──────────────────────────────────────────────────────────

    @property
    def state(self) -> SessionState:
        return self._machine.state

    @property
    def completed_sessions(self) -> list[SessionRecord]:
        return list(self._completed_sessions)

    def session_summary(self) -> dict[str, object]:
        return self._machine.session_summary()
