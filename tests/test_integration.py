"""
Integration tests - full Phase 1 pipeline end-to-end.

No ROS2, no ChromaDB, no Ollama required. Uses mocks for external services
so the entire data flow from student query to gesture dispatch can be verified
in CI without any infrastructure.

Coverage:
  - Bias detection → prompt building → mocked LLM → AdvisingResponse
  - SessionMachine full lifecycle (IDLE → GREETING → ADVISING → CLOSURE → IDLE)
  - GestureDispatcher full gesture execution in StubEnv
  - Orchestrator tick loop with StubDetector
  - msg_bridge round-trip (Pydantic → dict → Pydantic, without rclpy)
  - Visualizer FK geometry sanity check

Run with:  pytest tests/test_integration.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import numpy as np
import pytest

from drona.contracts import (
    AdvisingQuery,
    AdvisingResponse,
    BiasFlag,
    DataTier,
    GestureType,
    InteractionAction,
    PathwayRecommendation,
    RetrievalCitation,
    StudentProfile,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_query(text: str = "What careers suit a Python developer in Nepal?") -> AdvisingQuery:
    return AdvisingQuery(
        query_id=str(uuid.uuid4()),
        query_text=text,
        profile=StudentProfile(session_id=str(uuid.uuid4())),
    )


def _make_action(gesture: GestureType | str = GestureType.GREET) -> InteractionAction:
    return InteractionAction(
        action_id=str(uuid.uuid4()),
        gesture=gesture,
    )


def _make_response(n_pathways: int = 3) -> AdvisingResponse:
    cit = RetrievalCitation(
        source_type="job_posting",  # type: ignore[arg-type]
        source_id=str(uuid.uuid4()),
        tier=DataTier.NEPAL,
        excerpt="Senior Python developer role at Leapfrog Technology.",
        relevance_score=0.85,
    )
    return AdvisingResponse(
        query_id=str(uuid.uuid4()),
        summary="Three strong career pathways for your Python background.",
        pathways=[
            PathwayRecommendation(
                pathway_title=f"Pathway {i}",
                rationale="Strong match.",
                confidence="high",
                citations=[cit],
            )
            for i in range(n_pathways)
        ],
        bias_flags=[],
        refusal=False,
        speak_text="Here are your career options.",
        generation_time_ms=320,
    )


def _make_detection(engagement=None, confidence: float = 0.9, distance_m: float = 1.2):
    from drona.perception.mediapipe_detector import EngagementState, StudentDetection
    if engagement is None:
        engagement = EngagementState.ENGAGED
    return StudentDetection(
        detection_id=str(uuid.uuid4()),
        engagement=engagement,
        confidence=confidence,
        estimated_distance_m=distance_m,
    )


# ── Bias detector → prompt builder pipeline ───────────────────────────────────

class TestBiasPromptPipeline:
    def test_biased_query_produces_flags(self) -> None:
        from drona.advising.bias_detector import BiasDetector
        bd = BiasDetector()
        flags = bd.detect("I only want to work at Google, nowhere else.")
        assert any(f.bias_type == "anchoring" for f in flags)

    def test_flags_appear_in_system_prompt(self) -> None:
        from drona.advising.bias_detector import BiasDetector
        from drona.advising.prompt_builder import build_prompt
        bd = BiasDetector()
        query_text = "I've already told my parents I'll be a data scientist. I can't change now."
        flags = bd.detect(query_text)
        query = _make_query(query_text)
        system, user = build_prompt(query, citations=[], bias_flags=flags)
        assert "consistency" in system.lower() or "commit" in system.lower()

    def test_clean_query_no_flags(self) -> None:
        from drona.advising.bias_detector import BiasDetector
        bd = BiasDetector()
        flags = bd.detect("What careers are available for BSc Computing graduates in Nepal?")
        assert flags == []

    def test_prompt_builder_orders_nepal_citations_first(self) -> None:
        from drona.advising.prompt_builder import build_prompt
        nepal_cit = RetrievalCitation(
            source_type="job_posting", source_id="n1",  # type: ignore[arg-type]
            tier=DataTier.NEPAL, excerpt="Nepal job.", relevance_score=0.9,
        )
        intl_cit = RetrievalCitation(
            source_type="job_posting", source_id="i1",  # type: ignore[arg-type]
            tier=DataTier.INTERNATIONAL, excerpt="Intl job.", relevance_score=0.95,
        )
        query = _make_query("test")
        _, user = build_prompt(query, [intl_cit, nepal_cit], [])
        nepal_pos = user.find("Nepal job.")
        intl_pos = user.find("Intl job.")
        assert nepal_pos < intl_pos, "Nepal citations must appear before international"


# ── AdvisingEngine with mocked LLM ────────────────────────────────────────────

class TestAdvisingEngineMocked:
    def _make_docs(self, n: int = 5):
        from drona.advising.retriever import _Doc
        return [
            _Doc(
                id=f"doc{i}", text=f"Nepal tech job {i}.",
                metadata={"source_type": "job_posting", "tier": "nepal"},
                rrf_score=0.5 - i * 0.05,
            )
            for i in range(n)
        ]

    def _make_mock_retriever(self, n_docs: int = 5):
        docs = self._make_docs(n_docs)
        mock_retriever = MagicMock()
        mock_retriever.retrieve_raw.return_value = docs
        return mock_retriever

    def _make_mock_reranker(self, n_docs: int = 5):
        docs = self._make_docs(n_docs)
        mock_reranker = MagicMock()
        mock_reranker.rerank_docs.return_value = docs
        return mock_reranker

    def _make_mock_llm(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = (
            [PathwayRecommendation(
                pathway_title="Software Developer",
                rationale="Strong Python background.",
                confidence="high",
            )],
            "You have strong options as a software developer.",
            False,
            None,
        )
        return mock_llm

    def test_advise_returns_response(self) -> None:
        from drona.advising.engine import AdvisingEngine
        engine = AdvisingEngine(
            retriever=self._make_mock_retriever(),
            reranker=self._make_mock_reranker(),
            llm=self._make_mock_llm(),
        )
        response = engine.advise(_make_query())
        assert isinstance(response, AdvisingResponse)

    def test_advise_non_empty_pathways(self) -> None:
        from drona.advising.engine import AdvisingEngine
        engine = AdvisingEngine(
            retriever=self._make_mock_retriever(),
            reranker=self._make_mock_reranker(),
            llm=self._make_mock_llm(),
        )
        response = engine.advise(_make_query())
        assert len(response.pathways) > 0

    def test_biased_query_sets_flags(self) -> None:
        from drona.advising.engine import AdvisingEngine
        engine = AdvisingEngine(
            retriever=self._make_mock_retriever(),
            reranker=self._make_mock_reranker(),
            llm=self._make_mock_llm(),
        )
        q = _make_query("I only want to work at Google or Microsoft, nowhere else.")
        response = engine.advise(q)
        assert len(response.bias_flags) > 0

    def test_generation_time_recorded(self) -> None:
        from drona.advising.engine import AdvisingEngine
        engine = AdvisingEngine(
            retriever=self._make_mock_retriever(),
            reranker=self._make_mock_reranker(),
            llm=self._make_mock_llm(),
        )
        response = engine.advise(_make_query())
        assert response.generation_time_ms is not None
        assert response.generation_time_ms >= 0

    def test_no_coverage_triggers_refusal(self) -> None:
        from drona.advising.engine import AdvisingEngine
        mock_retriever = MagicMock()
        mock_retriever.retrieve_raw.return_value = []
        mock_reranker = MagicMock()
        mock_reranker.rerank_docs.return_value = []
        mock_llm = MagicMock()

        engine = AdvisingEngine(retriever=mock_retriever, reranker=mock_reranker, llm=mock_llm)
        response = engine.advise(_make_query())
        assert response.refusal is True
        mock_llm.generate.assert_not_called()


# ── Session machine lifecycle ──────────────────────────────────────────────────

class TestSessionLifecycle:
    def test_full_session_idle_to_idle(self) -> None:
        from drona.orchestrator.session_machine import SessionMachine
        from drona.orchestrator.session_machine import SessionState as SessState
        from drona.perception.mediapipe_detector import EngagementState

        machine = SessionMachine(timeout_s=999.0)
        assert machine.state == SessState.IDLE

        machine.feed_detection(_make_detection(EngagementState.ENGAGED, 0.9, 1.2))
        assert machine.state == SessState.GREETING

        machine.mark_greeted()
        assert machine.state == SessState.NEEDS_ASSESSMENT

        machine.submit_query("What jobs suit me?")
        assert machine.state == SessState.ADVISING

        machine.mark_response_delivered()
        assert machine.state == SessState.CLOSURE

        machine.mark_session_closed()
        assert machine.state == SessState.IDLE

    def test_session_id_changes_after_close(self) -> None:
        from drona.orchestrator.session_machine import SessionMachine
        from drona.perception.mediapipe_detector import EngagementState

        machine = SessionMachine()
        first_id = machine.session_id

        machine.feed_detection(_make_detection(EngagementState.ENGAGED, 0.9, 1.2))
        machine.mark_greeted()
        machine.submit_query("test")
        machine.mark_response_delivered()
        machine.mark_session_closed()

        second_id = machine.session_id
        assert first_id != second_id, "New UUID must be assigned on session close"

    def test_query_count_increments(self) -> None:
        from drona.orchestrator.session_machine import SessionMachine
        from drona.perception.mediapipe_detector import EngagementState

        machine = SessionMachine()
        machine.feed_detection(_make_detection(EngagementState.ENGAGED, 0.9, 1.2))
        machine.mark_greeted()
        machine.submit_query("Q1")
        summary = machine.session_summary()
        assert summary["query_count"] == 1

    def test_timeout_returns_to_idle(self) -> None:
        import time

        from drona.orchestrator.session_machine import SessionMachine
        from drona.orchestrator.session_machine import SessionState as SessState
        from drona.perception.mediapipe_detector import EngagementState

        machine = SessionMachine(timeout_s=0.05)
        machine.feed_detection(_make_detection(EngagementState.ENGAGED, 0.9, 1.2))
        assert machine.state == SessState.GREETING

        time.sleep(0.1)
        machine.feed_detection(_make_detection(EngagementState.DISENGAGING, 0.2, 3.0))
        assert machine.state == SessState.IDLE


# ── GestureDispatcher full execution ──────────────────────────────────────────

class TestGestureDispatcherIntegration:
    @pytest.mark.parametrize("gesture", [
        GestureType.GREET, GestureType.NOD, GestureType.POINT,
        GestureType.IDLE, GestureType.LISTEN, GestureType.FAREWELL,
    ])
    def test_all_gestures_execute_successfully(self, gesture: GestureType) -> None:
        from drona.interaction.gesture_dispatcher import GestureDispatcher

        dispatcher = GestureDispatcher(checkpoint_base_dir=None)
        action = _make_action(gesture)
        result = dispatcher.execute(action)

        assert result.success, f"Gesture '{gesture}' failed: {result.error_message}"
        assert result.actual_duration_seconds is not None
        assert result.actual_duration_seconds >= 0.0

    def test_point_gesture_uses_direction(self) -> None:
        from drona.interaction.gesture_dispatcher import GestureDispatcher

        dispatcher = GestureDispatcher(checkpoint_base_dir=None)
        action = InteractionAction(
            action_id=str(uuid.uuid4()),
            gesture=GestureType.POINT,
            target_direction=(1.0, 0.5, 0.8),
        )
        result = dispatcher.execute(action)
        assert result.success

    def test_invalid_gesture_rejected_by_contract(self) -> None:
        """GestureType is a strict enum; invalid values are rejected at construction."""
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            InteractionAction(
                action_id=str(uuid.uuid4()),
                gesture="nonexistent_gesture",  # type: ignore[arg-type]
            )


# ── Orchestrator tick loop ─────────────────────────────────────────────────────

class TestOrchestratorTickLoop:
    def test_tick_loop_drives_greeting(self) -> None:
        from drona.interaction.gesture_dispatcher import GestureDispatcher
        from drona.orchestrator.orchestrator import Orchestrator
        from drona.orchestrator.session_machine import SessionState as SessState
        from drona.perception.mediapipe_detector import EngagementState, StubDetector

        dispatcher = GestureDispatcher(checkpoint_base_dir=None)

        script = (
            [(EngagementState.ENGAGED, 0.9, 1.0)] * 5
            + [(EngagementState.ABSENT, 0.0, 5.0)] * 10
        )
        detector = StubDetector(script=script)

        orch = Orchestrator(
            detector=detector,
            dispatcher=dispatcher,
            engine=None,
        )

        for _ in range(6):
            orch.tick()
            if orch._machine.state in (SessState.GREETING, SessState.NEEDS_ASSESSMENT):
                break

        # After an ENGAGED sequence the machine should have advanced past IDLE
        assert orch._machine.state in (SessState.GREETING, SessState.NEEDS_ASSESSMENT, SessState.ADVISING)


# ── Visualizer FK sanity ───────────────────────────────────────────────────────

class TestVisualizerFK:
    def test_fk_returns_five_points(self) -> None:
        from drona.interaction.demonstration import REST_POSE
        from drona.interaction.visualizer import _forward_kinematics
        pts = _forward_kinematics(REST_POSE)
        assert len(pts) == 5  # base + 4 joints

    def test_gesture_positions_all_finite(self) -> None:
        from drona.interaction.demonstration import GESTURE_KEYFRAMES, interpolate_keyframes
        from drona.interaction.visualizer import _forward_kinematics

        for gesture, kfs in GESTURE_KEYFRAMES.items():
            traj = interpolate_keyframes(kfs, dt=0.1)
            for q, _ in traj:
                pts = _forward_kinematics(q)
                for pt in pts:
                    assert np.all(np.isfinite(pt)), f"Non-finite in {gesture}: {pt}"

    def test_rest_pose_base_at_origin(self) -> None:
        from drona.interaction.demonstration import REST_POSE
        from drona.interaction.visualizer import _forward_kinematics
        pts = _forward_kinematics(REST_POSE)
        # Base joint is always at origin
        np.testing.assert_array_almost_equal(pts[0], [0.0, 0.0, 0.0])

    def test_fk_tip_is_finite(self) -> None:
        from drona.interaction.demonstration import REST_POSE
        from drona.interaction.visualizer import _forward_kinematics
        pts = _forward_kinematics(REST_POSE)
        assert np.all(np.isfinite(pts[-1])), "Tip position must be finite"


# ── Contract round-trip serialisation ────────────────────────────────────────

class TestContractSerialisation:
    def test_advising_response_json_round_trip(self) -> None:
        resp = _make_response(n_pathways=3)
        json_str = resp.model_dump_json()
        resp2 = AdvisingResponse.model_validate_json(json_str)
        assert resp2.query_id == resp.query_id
        assert len(resp2.pathways) == 3

    def test_bias_flag_round_trip(self) -> None:
        flag = BiasFlag(
            bias_type="anchoring",  # type: ignore[arg-type]
            detected_signal="only Google",
            mitigation_applied="Show diverse options.",
        )
        d = flag.model_dump()
        flag2 = BiasFlag.model_validate(d)
        assert flag2.bias_type == flag.bias_type

    def test_retrieval_citation_tier_preserved(self) -> None:
        cit = RetrievalCitation(
            source_type="curriculum",  # type: ignore[arg-type]
            source_id="x",
            tier=DataTier.NEPAL,
            excerpt="Nepal content.",
            relevance_score=0.7,
        )
        d = cit.model_dump()
        cit2 = RetrievalCitation.model_validate(d)
        assert cit2.tier == DataTier.NEPAL
