"""
WS4 smoke tests - perception + session state machine + orchestrator.

No camera, no MediaPipe, no real advising engine or gesture dispatcher.
StubDetector drives perception; all heavy subsystems are mocked.

Run with:  pytest tests/test_ws4_orchestrator.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from drona.contracts import (
    AdvisingResponse,
    EngagementState,
    InteractionActionResult,
    PathwayRecommendation,
    SessionState,
    StudentDetection,
)
from drona.orchestrator.orchestrator import Orchestrator, SessionRecord
from drona.orchestrator.session_machine import SessionMachine
from drona.perception.mediapipe_detector import (
    StubDetector,
    _classify_engagement,
    _default_session_script,
    make_detector,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _detection(
    state: EngagementState,
    confidence: float = 0.9,
    distance_m: float | None = 1.2,
) -> StudentDetection:
    return StudentDetection(
        detection_id=str(uuid.uuid4()),
        engagement=state,
        estimated_distance_m=distance_m,
        gaze_on_robot=(state == EngagementState.ENGAGED),
        confidence=confidence,
    )


def _make_stub_engine(refusal: bool = False) -> MagicMock:
    """Mock AdvisingEngine that returns a minimal AdvisingResponse."""
    engine = MagicMock()
    pathway = PathwayRecommendation(
        pathway_title="Software Developer",
        rationale="Matches your skills",
        confidence="medium",
    )
    response = AdvisingResponse(
        query_id=str(uuid.uuid4()),
        summary="Here are your options.",
        pathways=[] if refusal else [pathway],
        refusal=refusal,
        speak_text="Here are your options." if not refusal else "Sorry, no data.",
        requires_human_followup=refusal,
    )
    engine.advise.return_value = response
    return engine


def _make_stub_dispatcher() -> MagicMock:
    """Mock GestureDispatcher that always succeeds."""
    dispatcher = MagicMock()
    dispatcher.execute.return_value = InteractionActionResult(
        action_id=str(uuid.uuid4()),
        success=True,
        actual_duration_seconds=0.5,
    )
    dispatcher.get_trajectory.return_value = []
    return dispatcher


# ── Classification helper ──────────────────────────────────────────────────────

class TestClassifyEngagement:
    def test_low_confidence_is_absent(self) -> None:
        state, _ = _classify_engagement(0.1, 0.05, 5)
        assert state == EngagementState.ABSENT

    def test_medium_confidence_far_is_passing_by(self) -> None:
        state, _ = _classify_engagement(0.5, 0.005, 5)
        assert state == EngagementState.PASSING_BY

    def test_high_confidence_small_face_is_approaching(self) -> None:
        state, _ = _classify_engagement(0.85, 0.005, 5)
        assert state == EngagementState.APPROACHING

    def test_high_confidence_large_face_enough_frames_is_engaged(self) -> None:
        state, _ = _classify_engagement(0.9, 0.15, 5)
        assert state == EngagementState.ENGAGED

    def test_distance_estimated_from_face_size(self) -> None:
        _, dist = _classify_engagement(0.9, 0.05, 5)
        assert dist is not None and dist > 0

    def test_zero_face_area_gives_none_distance(self) -> None:
        _, dist = _classify_engagement(0.9, 0.0, 5)
        assert dist is None


# ── StubDetector ──────────────────────────────────────────────────────────────

class TestStubDetector:
    def test_returns_detection_from_script(self) -> None:
        script = [
            (EngagementState.ABSENT, 0.0, None),
            (EngagementState.ENGAGED, 0.9, 1.2),
        ]
        det = StubDetector(script=script)
        d1 = det.detect()
        d2 = det.detect()
        assert d1.engagement == EngagementState.ABSENT
        assert d2.engagement == EngagementState.ENGAGED

    def test_repeats_last_when_exhausted(self) -> None:
        script = [(EngagementState.ENGAGED, 0.9, 1.2)]
        det = StubDetector(script=script)
        det.detect()  # consume
        d2 = det.detect()  # should repeat last
        assert d2.engagement == EngagementState.ENGAGED

    def test_reset_restarts_script(self) -> None:
        script = [
            (EngagementState.ABSENT, 0.0, None),
            (EngagementState.ENGAGED, 0.9, 1.2),
        ]
        det = StubDetector(script=script)
        det.detect()
        det.reset()
        d = det.detect()
        assert d.engagement == EngagementState.ABSENT

    def test_exhausted_flag(self) -> None:
        script = [(EngagementState.ABSENT, 0.0, None)]
        det = StubDetector(script=script)
        assert not det.exhausted
        det.detect()
        assert det.exhausted

    def test_detection_has_detection_id(self) -> None:
        det = StubDetector()
        d = det.detect()
        assert d.detection_id != ""

    def test_make_detector_returns_stub_without_mediapipe(self) -> None:
        det = make_detector(prefer_mediapipe=False)
        assert isinstance(det, StubDetector)

    def test_default_script_contains_engaged_state(self) -> None:
        script = _default_session_script()
        states = [s for s, _, _ in script]
        assert EngagementState.ENGAGED in states

    def test_gaze_on_robot_true_when_engaged(self) -> None:
        script = [(EngagementState.ENGAGED, 0.9, 1.2)]
        det = StubDetector(script=script)
        d = det.detect()
        assert d.gaze_on_robot is True


# ── SessionMachine ────────────────────────────────────────────────────────────

class TestSessionMachine:
    def test_initial_state_is_idle(self) -> None:
        machine = SessionMachine()
        assert machine.state == SessionState.IDLE

    def test_engaged_detection_triggers_greeting(self) -> None:
        machine = SessionMachine()
        result = machine.feed_detection(_detection(EngagementState.ENGAGED))
        assert result.transitioned
        assert machine.state == SessionState.GREETING

    def test_absent_in_idle_stays_idle(self) -> None:
        machine = SessionMachine()
        result = machine.feed_detection(_detection(EngagementState.ABSENT, confidence=0.0))
        assert not result.transitioned
        assert machine.state == SessionState.IDLE

    def test_mark_greeted_advances_to_needs_assessment(self) -> None:
        machine = SessionMachine()
        machine.feed_detection(_detection(EngagementState.ENGAGED))
        result = machine.mark_greeted()
        assert result.transitioned
        assert machine.state == SessionState.NEEDS_ASSESSMENT

    def test_submit_query_advances_to_advising(self) -> None:
        machine = SessionMachine()
        machine.feed_detection(_detection(EngagementState.ENGAGED))
        machine.mark_greeted()
        result = machine.submit_query("What jobs can I get?")
        assert result.transitioned
        assert machine.state == SessionState.ADVISING

    def test_query_in_wrong_state_is_rejected(self) -> None:
        machine = SessionMachine()
        result = machine.submit_query("Hello")
        assert not result.transitioned
        assert machine.state == SessionState.IDLE

    def test_mark_response_delivered_advances_to_closure(self) -> None:
        machine = SessionMachine()
        machine.feed_detection(_detection(EngagementState.ENGAGED))
        machine.mark_greeted()
        machine.submit_query("Career advice?")
        result = machine.mark_response_delivered()
        assert result.transitioned
        assert machine.state == SessionState.CLOSURE

    def test_mark_session_closed_returns_to_idle(self) -> None:
        machine = SessionMachine()
        machine.feed_detection(_detection(EngagementState.ENGAGED))
        machine.mark_greeted()
        machine.submit_query("Career advice?")
        machine.mark_response_delivered()
        result = machine.mark_session_closed()
        assert result.transitioned
        assert machine.state == SessionState.IDLE

    def test_timeout_from_greeting(self) -> None:
        machine = SessionMachine(timeout_s=0.0)  # instant timeout
        machine.feed_detection(_detection(EngagementState.ENGAGED))
        assert machine.state == SessionState.GREETING
        # Now send absent with timeout=0 so it fires immediately
        absent = _detection(EngagementState.ABSENT, confidence=0.0)
        result = machine.feed_detection(absent)
        assert result.transitioned
        assert machine.state == SessionState.IDLE

    def test_reset_returns_to_idle(self) -> None:
        machine = SessionMachine()
        machine.feed_detection(_detection(EngagementState.ENGAGED))
        assert machine.state == SessionState.GREETING
        machine.reset()
        assert machine.state == SessionState.IDLE

    def test_new_session_id_after_reset(self) -> None:
        machine = SessionMachine()
        sid1 = machine.session_id
        machine.feed_detection(_detection(EngagementState.ENGAGED))
        machine.reset()
        sid2 = machine.session_id
        assert sid1 != sid2

    def test_events_recorded_on_transitions(self) -> None:
        machine = SessionMachine()
        machine.feed_detection(_detection(EngagementState.ENGAGED))
        machine.mark_greeted()
        events = machine.events
        triggers = [e.trigger for e in events]
        assert "student_engaged" in triggers
        assert "greeted" in triggers

    def test_session_summary_contains_state(self) -> None:
        machine = SessionMachine()
        summary = machine.session_summary()
        assert "state" in summary
        assert "session_id" in summary

    def test_full_lifecycle(self) -> None:
        machine = SessionMachine()
        machine.feed_detection(_detection(EngagementState.ENGAGED))
        assert machine.state == SessionState.GREETING
        machine.mark_greeted()
        assert machine.state == SessionState.NEEDS_ASSESSMENT
        machine.submit_query("Career options?")
        assert machine.state == SessionState.ADVISING
        machine.mark_response_delivered()
        assert machine.state == SessionState.CLOSURE
        machine.mark_session_closed()
        assert machine.state == SessionState.IDLE


# ── Orchestrator (mocked subsystems) ──────────────────────────────────────────

class TestOrchestrator:
    def _make_orchestrator(
        self,
        script: list | None = None,
        refusal: bool = False,
    ) -> Orchestrator:
        det = StubDetector(script=script or _default_session_script())
        engine = _make_stub_engine(refusal=refusal)
        dispatcher = _make_stub_dispatcher()
        return Orchestrator(
            detector=det,
            engine=engine,
            dispatcher=dispatcher,
        )

    def test_tick_in_idle_with_absent_stays_idle(self) -> None:
        orch = self._make_orchestrator(
            script=[(EngagementState.ABSENT, 0.0, None)] * 5
        )
        for _ in range(5):
            orch.tick()
        assert orch.state == SessionState.IDLE

    def test_engaged_detection_triggers_greeting_state(self) -> None:
        script = [(EngagementState.ENGAGED, 0.9, 1.2)]
        orch = self._make_orchestrator(script=script)
        orch.tick()
        # After first tick with ENGAGED, machine should be in GREETING or NEEDS_ASSESSMENT
        # (orchestrator calls mark_greeted() inside _do_greet so it advances past GREETING)
        assert orch.state in (SessionState.GREETING, SessionState.NEEDS_ASSESSMENT)

    def test_full_session_via_submit_query(self) -> None:
        """Drive a complete session: engage → greet → query → advise → close."""
        # Script: 1 engaged frame, then absent to trigger timeout after session
        script = (
            [(EngagementState.ENGAGED, 0.9, 1.2)] * 1
            + [(EngagementState.ABSENT, 0.0, None)] * 20
        )
        orch = self._make_orchestrator(script=script)

        # Tick 1: ENGAGED → triggers GREETING + _do_greet() → NEEDS_ASSESSMENT
        orch.tick()
        assert orch.state == SessionState.NEEDS_ASSESSMENT

        # Submit a query
        orch.submit_query("What careers suit me?")
        orch.tick()  # consumes query → ADVISING → response → CLOSURE → IDLE
        assert orch.state == SessionState.IDLE

    def test_completed_sessions_recorded(self) -> None:
        script = (
            [(EngagementState.ENGAGED, 0.9, 1.2)] * 1
            + [(EngagementState.ABSENT, 0.0, None)] * 5
        )
        orch = self._make_orchestrator(script=script)
        orch.tick()  # engage → needs_assessment
        orch.submit_query("Career options?")
        orch.tick()  # advise → idle
        assert len(orch.completed_sessions) == 1
        record = orch.completed_sessions[0]
        assert isinstance(record, SessionRecord)
        assert record.query_count == 1

    def test_on_response_callback_called(self) -> None:
        responses_received: list[AdvisingResponse] = []
        script = [
            (EngagementState.ENGAGED, 0.9, 1.2),
            (EngagementState.ABSENT, 0.0, None),
        ]
        det = StubDetector(script=script)
        engine = _make_stub_engine()
        dispatcher = _make_stub_dispatcher()
        orch = Orchestrator(
            detector=det,
            engine=engine,
            dispatcher=dispatcher,
            on_response=lambda r: responses_received.append(r),
        )
        orch.tick()  # engage → needs_assessment
        orch.submit_query("Career advice?")
        orch.tick()  # advise
        assert len(responses_received) == 1

    def test_on_event_callback_called_on_transition(self) -> None:
        events_received = []
        script = [(EngagementState.ENGAGED, 0.9, 1.2)]
        orch = Orchestrator(
            detector=StubDetector(script=script),
            engine=_make_stub_engine(),
            dispatcher=_make_stub_dispatcher(),
            on_event=lambda e: events_received.append(e),
        )
        orch.tick()
        assert len(events_received) >= 1

    def test_empty_query_is_ignored(self) -> None:
        orch = self._make_orchestrator()
        orch.submit_query("")
        orch.submit_query("   ")
        # Queue should be empty
        assert orch._query_queue.empty()

    def test_session_summary_accessible(self) -> None:
        orch = self._make_orchestrator()
        summary = orch.session_summary()
        assert "state" in summary

    def test_refusal_response_still_completes_session(self) -> None:
        """Engine refusal should not leave the session stuck."""
        script = [
            (EngagementState.ENGAGED, 0.9, 1.2),
            (EngagementState.ABSENT, 0.0, None),
        ]
        orch = self._make_orchestrator(script=script, refusal=True)
        orch.tick()  # engage → needs_assessment
        orch.submit_query("Question with no data coverage")
        orch.tick()  # advise (refusal) → idle
        assert orch.state == SessionState.IDLE
