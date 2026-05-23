"""
D.R.O.N.A. system contracts.

These Pydantic models are the *interface* between modules. They are intentionally
shaped to mirror ROS2 message/action conventions:

  - Flat, serializable fields (no nested objects with methods)
  - Explicit timestamps + frame_ids where applicable
  - Enums as string literals (ROS2 friendly)
  - Optional fields default to None, never to mutable types

In Phase 1, modules pass these objects directly (Python imports).
In Phase 2, these become ROS2 .msg / .action files. The field structure
will translate 1:1. This is the single most important architectural decision
in the project: it makes Phase 1 → Phase 2 a port, not a rewrite.

Reference: proposal Figure 10 (System Architecture) and Objective 3
("modular architecture integrating robotics and AI within a deployable,
robot-independent framework").
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Common base
# ============================================================================

class DronaMessage(BaseModel):
    """Base for all inter-module messages. Mirrors a ROS2 std_msgs/Header."""
    model_config = ConfigDict(extra="forbid", frozen=False)

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    frame_id: str = "drona"  # ROS2 frame identifier; useful when robotics land


# ============================================================================
# WS1 — Data layer contracts
# ============================================================================

class DataTier(str, Enum):
    """Three-tier data provenance. Tier 1 (local) is prioritized in retrieval."""
    NEPAL = "nepal"
    REGIONAL = "regional"   # South Asia, India
    INTERNATIONAL = "international"
    SYNTHETIC = "synthetic"  # Always labeled, never silently mixed


class JobPosting(BaseModel):
    """Normalized job posting from any source.

    Manually collected from Nepali portals (MeroJob, JobsNepal, Internsathi,
    Kumari Jobs) and LinkedIn published reports. Source URL and collection
    date preserved for provenance.
    """
    model_config = ConfigDict(extra="forbid")

    posting_id: str  # hash of source + url + date
    source: str  # 'merojob' | 'jobsnepal' | 'internsathi' | 'kumarijobs' | 'linkedin_report' | etc.
    tier: DataTier
    title: str
    employer: str | None = None
    location: str | None = None
    skills_required: list[str] = Field(default_factory=list)
    skills_preferred: list[str] = Field(default_factory=list)
    experience_years_min: int | None = None
    salary_min_npr: int | None = None
    salary_max_npr: int | None = None
    description: str = ""
    posted_date: datetime | None = None
    collected_date: datetime = Field(default_factory=datetime.utcnow)
    source_url: str | None = None
    is_synthetic: bool = False
    synthetic_anchor_ids: list[str] = Field(default_factory=list)  # if synthetic, what real postings inspired it


class CurriculumModule(BaseModel):
    """A single Softwarica module. Real data, collected from college materials."""
    model_config = ConfigDict(extra="forbid")

    module_code: str  # e.g. '4001COMP'
    title: str
    year: int = Field(ge=1, le=4)
    semester: int | None = Field(default=None, ge=1, le=2)
    credits: int | None = None
    description: str = ""
    learning_outcomes: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)  # other module_codes
    skills_developed: list[str] = Field(default_factory=list)
    is_core: bool = True
    source_document: str | None = None


class CareerPathway(BaseModel):
    """A career pathway anchored in real occupation data (O*NET/ESCO/local)."""
    model_config = ConfigDict(extra="forbid")

    pathway_id: str
    title: str
    tier: DataTier
    onet_soc_code: str | None = None  # if from O*NET
    esco_code: str | None = None
    description: str = ""
    typical_skills: list[str] = Field(default_factory=list)
    typical_education: list[str] = Field(default_factory=list)
    local_salary_range_npr: tuple[int, int] | None = None
    international_salary_range_usd: tuple[int, int] | None = None
    related_softwarica_modules: list[str] = Field(default_factory=list)
    sample_employers_nepal: list[str] = Field(default_factory=list)


# ============================================================================
# WS2 — Advising intelligence contracts
# ============================================================================

class StudentProfile(BaseModel):
    """Session-scoped student profile. Never persisted, never PII.

    Captures only what the student volunteers in the current session for
    advising context. Discarded at session end.
    """
    model_config = ConfigDict(extra="forbid")

    session_id: str  # random UUID per session, never tied to identity
    year_of_study: int | None = Field(default=None, ge=1, le=4)
    completed_modules: list[str] = Field(default_factory=list)
    declared_interests: list[str] = Field(default_factory=list)
    declared_skills: list[str] = Field(default_factory=list)
    self_assessed_skill_levels: dict[str, int] = Field(default_factory=dict)  # skill → 1-5
    aspirations: list[str] = Field(default_factory=list)  # free-text goals
    aspiration_geography: Literal["nepal", "regional", "international", "any"] = "any"


class AdvisingQuery(DronaMessage):
    """A query into the advising intelligence layer.

    Phase 1: passed as Python object. Phase 2: ROS2 action goal.
    """
    query_id: str
    query_text: str
    profile: StudentProfile
    max_pathways: int = 3  # bias-mitigation default: always show multiple
    require_local_first: bool = True  # Tier 1 prioritization


class RetrievalCitation(BaseModel):
    """A single citation backing a claim in an advising response."""
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["curriculum", "job_posting", "career_pathway", "report", "synthetic"]
    source_id: str
    tier: DataTier
    excerpt: str
    relevance_score: float


class PathwayRecommendation(BaseModel):
    """One of multiple pathways surfaced in a response (anti-anchoring design)."""
    model_config = ConfigDict(extra="forbid")

    pathway_title: str
    rationale: str
    matched_softwarica_modules: list[str] = Field(default_factory=list)
    local_market_evidence: str | None = None  # what Nepali postings say
    international_context: str | None = None
    next_concrete_steps: list[str] = Field(default_factory=list)
    citations: list[RetrievalCitation] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


class BiasFlag(BaseModel):
    """Cognitive bias detected and addressed in the response.

    Operationalizes the proposal §Cognitive Biases section.
    """
    model_config = ConfigDict(extra="forbid")

    bias_type: Literal[
        "availability_heuristic",
        "anchoring",
        "confirmation",
        "dunning_kruger",
        "loss_aversion",
        "consistency",
    ]
    detected_signal: str  # what in the query suggested this bias
    mitigation_applied: str  # how the response counters it


class AdvisingResponse(DronaMessage):
    """The full structured response from the advising intelligence layer."""

    query_id: str
    summary: str  # 2-3 sentence top-line
    pathways: list[PathwayRecommendation]
    bias_flags: list[BiasFlag] = Field(default_factory=list)
    refusal: bool = False  # true if retrieval coverage was insufficient
    refusal_reason: str | None = None
    speak_text: str  # what the robot says aloud (shorter than full response)
    requires_human_followup: bool = False
    generation_time_ms: int | None = None


# ============================================================================
# WS3 — Interaction policy contracts (LeRobot side)
# ============================================================================

class GestureType(str, Enum):
    GREET = "greet"
    NOD = "nod"
    POINT = "point"
    IDLE = "idle"
    LISTEN = "listen"
    FAREWELL = "farewell"


class InteractionAction(DronaMessage):
    """A command to the robot to perform a learned gesture.

    Phase 1: directly consumed by sim. Phase 2: ROS2 action sent to robot driver.
    """
    action_id: str
    gesture: GestureType
    target_direction: tuple[float, float, float] | None = None  # for POINT
    speech_text: str | None = None  # optional accompanying utterance
    duration_seconds: float | None = None


class InteractionActionResult(DronaMessage):
    """Outcome of an InteractionAction. Mirrors a ROS2 action result."""
    action_id: str
    success: bool
    error_message: str | None = None
    actual_duration_seconds: float | None = None


# ============================================================================
# Perception + orchestration contracts
# ============================================================================

class EngagementState(str, Enum):
    ABSENT = "absent"
    PASSING_BY = "passing_by"
    APPROACHING = "approaching"
    ENGAGED = "engaged"
    DISENGAGING = "disengaging"


class StudentDetection(DronaMessage):
    """Output of the perception layer (MediaPipe in Phase 1, full vision in Phase 2)."""
    detection_id: str
    engagement: EngagementState
    estimated_distance_m: float | None = None
    gaze_on_robot: bool | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class SessionState(str, Enum):
    IDLE = "idle"
    GREETING = "greeting"
    NEEDS_ASSESSMENT = "needs_assessment"
    ADVISING = "advising"
    CLOSURE = "closure"


class SessionEvent(DronaMessage):
    """Orchestrator state transition event."""
    session_id: str
    from_state: SessionState
    to_state: SessionState
    trigger: str
