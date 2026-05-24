"""
Pydantic ↔ ROS2 message conversion bridge for D.R.O.N.A.

Every function here is a pure conversion with no side effects. The bridge
ensures that Phase 1 logic (drona.*) never imports rclpy, and ROS2 nodes
never duplicate business logic — they only call bridge functions and
forward results.

Naming convention:
    pydantic_to_ros(obj) → ROS2 message
    ros_to_pydantic(msg) → Pydantic model
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only imported for type hints — rclpy not required at import time
    from drona_msgs.msg import (
        AdvisingQuery as RosAdvisingQuery,
        AdvisingResponse as RosAdvisingResponse,
        BiasFlag as RosBiasFlag,
        EngagementDetection as RosEngagementDetection,
        GestureCommand as RosGestureCommand,
        GestureResult as RosGestureResult,
        PathwayRecommendation as RosPathwayRecommendation,
        RetrievalCitation as RosRetrievalCitation,
        SessionState as RosSessionState,
    )


# ── Advising query ────────────────────────────────────────────────────────────

def advising_query_to_ros(pydantic_query) -> "RosAdvisingQuery":
    from drona_msgs.msg import AdvisingQuery
    msg = AdvisingQuery()
    msg.query_id = pydantic_query.query_id
    msg.query_text = pydantic_query.query_text
    p = pydantic_query.profile
    msg.year_of_study = p.year_of_study or 0
    msg.completed_modules = list(p.completed_modules or [])
    msg.declared_skills = list(p.declared_skills or [])
    msg.geography_preference = p.geography_preference or "any"
    msg.max_pathways = pydantic_query.max_pathways
    return msg


def ros_to_advising_query(msg: "RosAdvisingQuery"):
    from drona.contracts import AdvisingQuery, StudentProfile
    profile = StudentProfile(
        session_id=str(uuid.uuid4()),
        year_of_study=msg.year_of_study if msg.year_of_study > 0 else None,
        completed_modules=list(msg.completed_modules),
        declared_skills=list(msg.declared_skills),
        geography_preference=msg.geography_preference or "any",
    )
    return AdvisingQuery(
        query_id=msg.query_id or str(uuid.uuid4()),
        query_text=msg.query_text,
        profile=profile,
        max_pathways=msg.max_pathways if msg.max_pathways > 0 else 3,
    )


# ── Bias flag ─────────────────────────────────────────────────────────────────

def bias_flag_to_ros(flag) -> "RosBiasFlag":
    from drona_msgs.msg import BiasFlag
    msg = BiasFlag()
    msg.bias_type = str(flag.bias_type)
    msg.detected_signal = flag.detected_signal or ""
    msg.mitigation_applied = flag.mitigation_applied or ""
    return msg


def ros_to_bias_flag(msg: "RosBiasFlag"):
    from drona.contracts import BiasFlag
    return BiasFlag(
        bias_type=msg.bias_type,  # type: ignore[arg-type]
        detected_signal=msg.detected_signal,
        mitigation_applied=msg.mitigation_applied,
    )


# ── Retrieval citation ────────────────────────────────────────────────────────

def citation_to_ros(cit) -> "RosRetrievalCitation":
    from drona_msgs.msg import RetrievalCitation
    msg = RetrievalCitation()
    msg.source_type = str(cit.source_type)
    msg.source_id = cit.source_id
    msg.tier = str(cit.tier.value) if hasattr(cit.tier, "value") else str(cit.tier)
    msg.excerpt = (cit.excerpt or "")[:300]
    msg.relevance_score = float(cit.relevance_score or 0.0)
    return msg


def ros_to_citation(msg: "RosRetrievalCitation"):
    from drona.contracts import DataTier, RetrievalCitation
    tier_map = {t.value: t for t in DataTier}
    tier = tier_map.get(msg.tier, DataTier.INTERNATIONAL)
    return RetrievalCitation(
        source_type=msg.source_type,  # type: ignore[arg-type]
        source_id=msg.source_id,
        tier=tier,
        excerpt=msg.excerpt,
        relevance_score=msg.relevance_score,
    )


# ── Pathway recommendation ────────────────────────────────────────────────────

def pathway_to_ros(pw) -> "RosPathwayRecommendation":
    from drona_msgs.msg import PathwayRecommendation
    msg = PathwayRecommendation()
    msg.pathway_title = pw.pathway_title
    msg.rationale = pw.rationale
    msg.confidence = pw.confidence
    msg.local_market_evidence = pw.local_market_evidence or ""
    msg.next_concrete_steps = list(pw.next_concrete_steps or [])
    msg.citations = [citation_to_ros(c) for c in (pw.citations or [])]
    return msg


def ros_to_pathway(msg: "RosPathwayRecommendation"):
    from drona.contracts import PathwayRecommendation
    return PathwayRecommendation(
        pathway_title=msg.pathway_title,
        rationale=msg.rationale,
        confidence=msg.confidence,  # type: ignore[arg-type]
        local_market_evidence=msg.local_market_evidence or None,
        next_concrete_steps=list(msg.next_concrete_steps),
        citations=[ros_to_citation(c) for c in msg.citations],
    )


# ── Advising response ─────────────────────────────────────────────────────────

def advising_response_to_ros(resp) -> "RosAdvisingResponse":
    from drona_msgs.msg import AdvisingResponse
    msg = AdvisingResponse()
    msg.query_id = resp.query_id
    msg.summary = resp.summary or ""
    msg.pathways = [pathway_to_ros(pw) for pw in (resp.pathways or [])]
    msg.bias_flags = [bias_flag_to_ros(bf) for bf in (resp.bias_flags or [])]
    msg.refusal = bool(resp.refusal)
    msg.refusal_reason = resp.refusal_reason or ""
    msg.speak_text = resp.speak_text or ""
    msg.generation_time_ms = resp.generation_time_ms or 0
    return msg


def ros_to_advising_response(msg: "RosAdvisingResponse"):
    from drona.contracts import AdvisingResponse
    return AdvisingResponse(
        query_id=msg.query_id,
        summary=msg.summary,
        pathways=[ros_to_pathway(pw) for pw in msg.pathways],
        bias_flags=[ros_to_bias_flag(bf) for bf in msg.bias_flags],
        refusal=msg.refusal,
        refusal_reason=msg.refusal_reason or None,
        speak_text=msg.speak_text,
        generation_time_ms=msg.generation_time_ms or None,
    )


# ── Engagement detection ──────────────────────────────────────────────────────

def engagement_to_ros(detection, clock) -> "RosEngagementDetection":
    from drona_msgs.msg import EngagementDetection
    msg = EngagementDetection()
    msg.stamp = clock.now().to_msg()
    msg.state = str(detection.state.value) if hasattr(detection.state, "value") else str(detection.state)
    msg.confidence = float(detection.confidence)
    msg.distance_m = float(detection.distance_m or 0.0)
    return msg


# ── Gesture command / result ──────────────────────────────────────────────────

def gesture_command_to_ros(action, clock) -> "RosGestureCommand":
    from drona_msgs.msg import GestureCommand
    msg = GestureCommand()
    msg.stamp = clock.now().to_msg()
    msg.gesture_label = str(action.gesture)
    t = action.target_position
    if t is not None:
        msg.target_x, msg.target_y, msg.target_z = float(t[0]), float(t[1]), float(t[2])
    return msg


def ros_gesture_command_to_action(msg: "RosGestureCommand"):
    from drona.contracts import InteractionAction
    target = None
    if msg.target_x != 0.0 or msg.target_y != 0.0 or msg.target_z != 0.0:
        target = [msg.target_x, msg.target_y, msg.target_z]
    return InteractionAction(
        gesture=msg.gesture_label,  # type: ignore[arg-type]
        target_position=target,
    )


def gesture_result_to_ros(result, clock) -> "RosGestureResult":
    from drona_msgs.msg import GestureResult
    msg = GestureResult()
    msg.stamp = clock.now().to_msg()
    msg.gesture_label = result.gesture_label
    msg.success = result.success
    msg.frames_executed = result.frames_executed
    msg.duration_s = result.duration_s
    msg.policy_used = result.policy_used or ""
    msg.error_message = result.error_message or ""
    return msg


# ── Session state ─────────────────────────────────────────────────────────────

def session_state_to_ros(context, clock) -> "RosSessionState":
    from drona_msgs.msg import SessionState
    msg = SessionState()
    msg.stamp = clock.now().to_msg()
    msg.session_id = str(context.session_id)
    msg.state = str(context.state.value) if hasattr(context.state, "value") else str(context.state)
    msg.query_count = context.query_count
    return msg
