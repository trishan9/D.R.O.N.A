"""
Request/response schemas for the advising API.

The wire request is intentionally PII-free and session-scoped: only what a
student volunteers for the current question. It maps onto the internal
``AdvisingQuery``/``StudentProfile`` contracts. Responses are the existing
``AdvisingResponse`` contract, serialised as-is.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from drona.contracts import AdvisingQuery, StudentProfile


class AdviseRequest(BaseModel):
    """Inbound advising request (no PII, session-scoped)."""

    query_text: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, description="Random UUID; never identity-linked")
    year_of_study: int | None = Field(default=None, ge=1, le=4)
    completed_modules: list[str] = Field(default_factory=list)
    declared_interests: list[str] = Field(default_factory=list)
    declared_skills: list[str] = Field(default_factory=list)
    self_assessed_skill_levels: dict[str, int] = Field(default_factory=dict)
    aspirations: list[str] = Field(default_factory=list)
    aspiration_geography: Literal["nepal", "regional", "international", "any"] = "any"
    max_pathways: int = Field(default=3, ge=1, le=6)
    require_local_first: bool = True

    def to_query(self) -> AdvisingQuery:
        profile = StudentProfile(
            session_id=self.session_id or str(uuid.uuid4()),
            year_of_study=self.year_of_study,
            completed_modules=self.completed_modules,
            declared_interests=self.declared_interests,
            declared_skills=self.declared_skills,
            self_assessed_skill_levels=self.self_assessed_skill_levels,
            aspirations=self.aspirations,
            aspiration_geography=self.aspiration_geography,
        )
        return AdvisingQuery(
            query_id=str(uuid.uuid4()),
            query_text=self.query_text,
            profile=profile,
            max_pathways=self.max_pathways,
            require_local_first=self.require_local_first,
        )


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    llm_available: bool
    orchestrator: str
    vector_backend: str
