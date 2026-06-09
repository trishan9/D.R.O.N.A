"""
Schema for synthetic advising Q&A pairs used to LoRA-fine-tune Phi-3.5.

Each pair is a (student question + context) → (gold JSON advising response)
example. Pairs are SYNTHETIC by construction (the build prompt forbids silently
mixing synthetic and real data), grounded in real anchors via ``anchor_ids``,
and carry a human-review flag so the ~50-item gold set is auditable.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from drona.contracts import RetrievalCitation, StudentProfile

BiasLabel = str  # one of contracts.BiasFlag.bias_type values, or None for clean


class AdvisingQAPair(BaseModel):
    """One supervised fine-tuning example for the advising task."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    profile: StudentProfile
    # The bias the question is designed to elicit (None = clean/no-bias example).
    bias_type: BiasLabel | None = None
    # Retrieval context the gold answer is allowed to cite (built from real anchors).
    context_citations: list[RetrievalCitation] = Field(default_factory=list)
    # Gold assistant output — the exact JSON object the model should produce.
    target_response: dict = Field(default_factory=dict)

    # Provenance / review
    is_synthetic: bool = True
    anchor_ids: list[str] = Field(default_factory=list)
    reviewed: bool = False
    approved: bool | None = None
    reviewer_note: str | None = None

    @property
    def is_gold(self) -> bool:
        return self.reviewed and self.approved is True
