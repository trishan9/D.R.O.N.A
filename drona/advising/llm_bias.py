"""
LLM-based cognitive-bias detection.

WHY NOT EMBEDDINGS
------------------
Nearest-neighbour over sentence embeddings was tried first
(``semantic_bias.py``) and measured **worse** than regexes on held-out v2
(F1 0.292 vs 0.645). The reason is structural, not a tuning failure: sentence
encoders represent **topic**, while a cognitive bias is a property of **framing**.
Three anchoring questions about Google, a salary figure and Kathmandu share
almost no topical content, whereas an anchoring question and a confirmation
question about data science are near-neighbours. kNN therefore groups by subject
matter and cuts across the labels.

WHY AN LLM
----------
Detecting "this student is fixating on one option to the exclusion of others" is
a pragmatic judgement about the *speech act*, which is what an instruction-tuned
LLM is good at and what both regexes and topical embeddings miss. The trade-off
is latency and non-determinism, so this detector is opt-in and always degrades
to the rule-based detector on any failure.

The prompt asks for a bare JSON array and nothing else; the model runs with
thinking disabled (reasoning models otherwise spend the budget deliberating and
return empty content).
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from drona.advising.bias_detector import _MITIGATIONS
from drona.contracts import BiasFlag, StudentProfile

BIAS_TYPES = (
    "availability_heuristic",
    "anchoring",
    "confirmation",
    "loss_aversion",
    "consistency",
    "dunning_kruger",
)

_PROMPT = """You analyse a student's career question for cognitive biases.

Bias types and what they look like:
- availability_heuristic: generalising from one vivid example - a friend's or
  senior's outcome, a news story, a video, a social-media post.
- anchoring: fixating on ONE option, employer, salary figure, or place and
  excluding alternatives ("only X", "X or nothing", a specific number).
- confirmation: seeking agreement for a belief already held, rather than
  evidence ("right?", "don't you agree?", "just confirm").
- loss_aversion: framed around avoiding a loss or risk rather than pursuing a
  goal ("scared of wasting", "what if I fail", "not worth the risk").
- consistency: continuing because of prior investment or a public commitment -
  sunk cost ("already spent 3 years", "I told everyone", "too late to change").
- dunning_kruger: mis-calibrated self-assessment in EITHER direction -
  overconfidence ("I already know everything") or underconfidence ("I'm just
  average", "not smart enough").

The question may be in English, Nepali, or a mix. Judge the framing, not the topic.

Question: "{query}"

Reply with ONLY a JSON array of the bias types present. Use [] if the question is
a neutral factual request. No explanation.
Example: ["anchoring", "confirmation"]"""


def _parse_types(raw: str) -> list[str]:
    """Extract the bias-type list from the model's reply, tolerating stray text."""
    if not raw:
        return []
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return [str(x).strip().lower() for x in parsed]
        except json.JSONDecodeError:
            pass
    # Fall back to scanning for known labels if the array was malformed.
    return [b for b in BIAS_TYPES if b in raw.lower()]


class LLMBiasDetector:
    """Classifies bias with an instruction-tuned LLM.

    Same ``detect(query_text, profile)`` contract as the rule-based detector, so
    it is a drop-in and can be ensembled. Any failure (model down, unparseable
    reply) falls back to the rule-based detector rather than returning nothing -
    losing bias detection silently would be worse than being slow.
    """

    def __init__(self, model: str | None = None, client: Any = None) -> None:
        self._model = model
        self._client = client
        self._rules = None

    def _get_client(self):
        if self._client is None:
            from drona.advising.llm_client import LLMClient
            from drona.utils.settings import settings

            self._client = LLMClient(model=self._model or settings.nepali_ollama_model)
        return self._client

    def _get_rules(self):
        if self._rules is None:
            from drona.advising.bias_detector import BiasDetector

            self._rules = BiasDetector()
        return self._rules

    def detect(
        self, query_text: str, profile: StudentProfile | None = None
    ) -> list[BiasFlag]:
        if not query_text.strip():
            return []
        try:
            raw = self._get_client().complete(
                _PROMPT.format(query=query_text), max_tokens=64, temperature=0.0
            )
            types = [t for t in _parse_types(raw) if t in BIAS_TYPES]
        except Exception as exc:  # noqa: BLE001 - never break advising
            logger.warning(f"LLM bias detection failed ({exc}); using rules")
            return self._get_rules().detect(query_text, profile=profile)

        if not raw:
            logger.warning("LLM bias detection returned nothing; using rules")
            return self._get_rules().detect(query_text, profile=profile)

        return [
            BiasFlag(
                bias_type=t,  # type: ignore[arg-type]
                detected_signal=f"identified by the language model as {t.replace('_', ' ')}",
                mitigation_applied=_MITIGATIONS.get(t, ""),
            )
            for t in dict.fromkeys(types)  # de-duplicate, preserve order
        ]


class LLMHybridBiasDetector:
    """Rules ∪ LLM.

    Rules are free and have never produced a false positive; the LLM adds the
    paraphrases no one wrote a pattern for. Union means the hybrid inherits every
    rule hit, so recall can only improve - what it costs in precision is the
    empirical question the benchmark answers.
    """

    def __init__(self, model: str | None = None) -> None:
        from drona.advising.bias_detector import BiasDetector

        self._rules = BiasDetector()
        self._llm = LLMBiasDetector(model=model)

    def detect(
        self, query_text: str, profile: StudentProfile | None = None
    ) -> list[BiasFlag]:
        flags = list(self._rules.detect(query_text, profile=profile))
        seen = {f.bias_type for f in flags}
        for f in self._llm.detect(query_text, profile=profile):
            if f.bias_type not in seen:
                flags.append(f)
                seen.add(f.bias_type)
        return flags
