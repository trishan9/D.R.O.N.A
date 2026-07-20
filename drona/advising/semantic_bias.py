"""
Semantic (embedding-based) cognitive-bias detection - the learned counterpart to
the rule-based detector.

WHY
---
The regex detector in ``bias_detector.py`` scores **precision 1.000 / recall
0.511** on the held-out v2 set: it never false-accuses, but it only fires on
surface forms someone anticipated. Every miss is a novel phrasing of a bias the
system already models ("Google or nothing for me", "I have been telling
recruiters I am a Java developer"). Patterns cannot generalise; embeddings can.

HOW
---
Nearest-neighbour over labelled exemplars - RAG applied to classification:

  1. a bank of bias-labelled student questions is embedded once (bi-encoder);
  2. an incoming query is embedded (one forward pass);
  3. cosine similarity against every exemplar; a bias type fires when its best
     exemplar is at least ``threshold`` similar.

A **bi-encoder** is used deliberately. The cross-encoder reranker already in the
stack scores query-document pairs more accurately, but would need one forward
pass per exemplar (~37 per query, measured at tens of seconds on CPU) - far too
slow for an interactive robot. The bi-encoder embeds once and the comparison is
a dot product.

The encoder is **multilingual**, so Nepali and code-switched questions are
handled by the same mechanism rather than needing a parallel set of Devanagari
patterns.

METHODOLOGY - WHAT THE EXEMPLARS MAY CONTAIN
--------------------------------------------
The exemplar bank is built from the C2 development bank and held-out **v1**
only. Held-out **v2** is never used: it is the evaluation set, and fitting on it
would repeat exactly the mistake this module exists to measure. Treat the
exemplar bank as training data.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from loguru import logger

from drona.advising.bias_detector import _MITIGATIONS
from drona.contracts import BiasFlag, StudentProfile

# Compact multilingual bi-encoder (~470 MB, CPU-friendly, 50+ languages incl.
# Devanagari). LaBSE is the heavier upgrade if Nepali recall proves weak.
DEFAULT_ENCODER = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Fired when the closest labelled exemplar of a bias type is at least this
# similar. Chosen on development data only (see scripts/benchmark_bias_detectors.py).
DEFAULT_THRESHOLD = 0.55


@dataclass
class _Exemplar:
    text: str
    bias_type: str


def _build_exemplars() -> list[_Exemplar]:
    """Labelled exemplars from DEVELOPMENT data only (bank + v1, never v2)."""
    from drona.evaluation.heldout_queries import HELDOUT_C2_QUERIES
    from drona.evaluation.queries import C2_QUERIES

    out: list[_Exemplar] = []
    for q in list(C2_QUERIES) + list(HELDOUT_C2_QUERIES):
        for b in q.expected_biases:
            out.append(_Exemplar(text=q.query_text, bias_type=b))
    return out


class SemanticBiasDetector:
    """kNN bias classifier over embedded, labelled exemplars.

    Exposes the same ``detect(query_text, profile)`` contract as the rule-based
    ``BiasDetector``, so the two are interchangeable and can be ensembled.
    """

    def __init__(
        self,
        encoder_name: str = DEFAULT_ENCODER,
        threshold: float = DEFAULT_THRESHOLD,
        exemplars: list[_Exemplar] | None = None,
    ) -> None:
        self._encoder_name = encoder_name
        self._threshold = threshold
        self._exemplars = exemplars if exemplars is not None else _build_exemplars()
        self._model: Any = None
        self._matrix: np.ndarray | None = None

    # ── Lazy model + exemplar matrix ──────────────────────────────────────────

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - dependency is in core
            raise RuntimeError(
                "sentence-transformers is required for semantic bias detection"
            ) from exc
        logger.info(f"Loading semantic bias encoder: {self._encoder_name}")
        self._model = SentenceTransformer(self._encoder_name, device="cpu")
        texts = [e.text for e in self._exemplars]
        self._matrix = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        logger.info(f"Semantic bias detector ready ({len(texts)} exemplars)")

    def is_available(self) -> bool:
        try:
            self._ensure_model()
            return True
        except Exception as exc:  # noqa: BLE001 - degrade to rules-only
            logger.warning(f"Semantic bias detector unavailable: {exc}")
            return False

    # ── Detection ─────────────────────────────────────────────────────────────

    def scores(self, query_text: str) -> dict[str, float]:
        """Best exemplar similarity per bias type (diagnostics / threshold tuning)."""
        self._ensure_model()
        assert self._matrix is not None
        q = self._model.encode([query_text], normalize_embeddings=True)[0]
        sims = self._matrix @ q  # cosine: both sides are L2-normalised
        best: dict[str, float] = {}
        for ex, s in zip(self._exemplars, sims, strict=True):
            v = float(s)
            if v > best.get(ex.bias_type, -1.0):
                best[ex.bias_type] = v
        return best

    def detect(
        self, query_text: str, profile: StudentProfile | None = None
    ) -> list[BiasFlag]:
        """Return a BiasFlag per bias type whose nearest exemplar clears threshold."""
        if not query_text.strip():
            return []
        try:
            best = self.scores(query_text)
        except Exception as exc:  # noqa: BLE001 - never break advising
            logger.warning(f"Semantic bias detection failed: {exc}")
            return []

        flags: list[BiasFlag] = []
        for bias_type, sim in sorted(best.items(), key=lambda kv: -kv[1]):
            if sim < self._threshold:
                continue
            flags.append(
                BiasFlag(
                    bias_type=bias_type,  # type: ignore[arg-type]
                    detected_signal=(
                        f"semantically similar to a known {bias_type.replace('_', ' ')} "
                        f"phrasing (cosine {sim:.2f})"
                    ),
                    mitigation_applied=_MITIGATIONS.get(bias_type, ""),
                )
            )
        return flags


class HybridBiasDetector:
    """Rules ∪ semantic.

    The rule layer contributes precision (it has never produced a false positive
    in any evaluation) and costs nothing; the semantic layer contributes recall
    on phrasings nobody wrote a pattern for. Taking the union keeps every rule
    hit and adds semantic ones, so the hybrid can only match or exceed the rules'
    recall - the open question, answered by benchmarking, is what it costs in
    precision.

    Falls back to rules alone if the encoder cannot load, so a machine without
    the model still detects bias.
    """

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        encoder_name: str = DEFAULT_ENCODER,
    ) -> None:
        from drona.advising.bias_detector import BiasDetector

        self._rules = BiasDetector()
        self._semantic = SemanticBiasDetector(encoder_name, threshold)

    def detect(
        self, query_text: str, profile: StudentProfile | None = None
    ) -> list[BiasFlag]:
        flags = list(self._rules.detect(query_text, profile=profile))
        seen = {f.bias_type for f in flags}
        for f in self._semantic.detect(query_text, profile=profile):
            if f.bias_type not in seen:
                flags.append(f)
                seen.add(f.bias_type)
        return flags


@lru_cache(maxsize=1)
def default_hybrid_detector() -> HybridBiasDetector:
    """Process-wide hybrid detector (the encoder is loaded once)."""
    return HybridBiasDetector()
