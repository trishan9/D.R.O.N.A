"""
Retrieval-augmented, span-grounded cognitive-bias detection - the detector the
system actually uses.

THE PROBLEM THIS SOLVES
-----------------------
Three earlier designs were built and measured on held-out v2 before this one:

  regex rules      P=1.000  R=0.511   never wrong, but only fires on phrasings
                                      someone anticipated.
  semantic kNN     P=0.361  R=0.256   sentence encoders group by TOPIC, and a
                                      cognitive bias is a property of FRAMING.
  zero-shot LLM    P=0.521  R=0.911   finds nearly every bias - and flags all 8
                                      neutral controls. Asked "find the biases",
                                      a model finds biases.

The zero-shot LLM's failure is **base-rate neglect**: nothing in the prompt tells
it that most student questions are ordinary factual requests. That is a prompt
construction problem, not a capability problem, and it has two known fixes -
both applied here.

FIX 1 - RETRIEVED FEW-SHOT (the RAG part)
-----------------------------------------
Instead of a fixed prompt, the k nearest labelled questions are retrieved from
the development bank and shown as worked examples. This is RAG applied to
classification: the same retrieve-then-generate structure as the advising path,
with labelled exemplars instead of curriculum chunks.

Crucially the bank includes **neutral** questions labelled ``[]``. The model sees
that roughly a quarter of retrieved neighbours are unbiased, which restores the
base rate the zero-shot prompt destroyed, and it sees Nepali exemplars when the
query is Nepali.

FIX 2 - SPAN GROUNDING (the anti-hallucination part)
-----------------------------------------------------
Every flag must come with the exact words from the question that triggered it,
and that quote is verified against the question before the flag is accepted. A
flag whose evidence does not appear in the text is dropped.

This is the citation-verification trick from grounded QA, used as a classifier
precision filter: a model inventing a bias has to invent a quote too, and an
invented quote fails the check mechanically - no second model call, no threshold.
It also means every flag shown to a student carries the span that caused it,
which is what the reasoning view displays.

METHODOLOGY
-----------
The exemplar bank is DEVELOPMENT data only (C2 bank + held-out v1). Held-out v2
is never retrieved from - it is the evaluation set, and putting it in the bank
would make the benchmark measure memorisation. Treat the bank as training data.
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from drona.advising.bias_detector import _MITIGATIONS
from drona.advising.llm_bias import BIAS_TYPES
from drona.contracts import BiasFlag, StudentProfile

# How many labelled neighbours to put in the prompt. Enough to carry the base
# rate and a couple of same-language examples; small enough to stay fast.
DEFAULT_K = 8

# A quoted span is accepted if it appears verbatim (normalised) or if this much
# of it overlaps the question by token. Models routinely paraphrase a quote
# slightly - "already spent three years" for "I've already spent 3 years" - and
# rejecting those would throw away correct flags.
SPAN_OVERLAP_MIN = 0.6

# A quote covering more of the question than this is rejected as non-evidence.
#
# This closes the loophole that made the first grounding implementation useless.
# Substring verification alone is trivially satisfied by quoting the WHOLE
# question, and that is exactly what the model did on every false positive it
# produced on held-out v2 - all three were "evidence" spans equal to the entire
# input. Quoting everything is not pointing at anything: a genuine bias trigger
# is a localised fragment ("Google or nothing", "right?", "already spent three
# years"), so a quote that swallows the question means the model found no
# specific signal and is confabulating a label.
#
# 0.90 was chosen on DEVELOPMENT data (scripts/tune_span_grounding.py: retrieve
# from the C2 bank, tune on held-out v1) and applied to v2 unchanged. It beat
# 0.60-0.80 on both precision and recall at the same false-positive count, and
# disabling the cap entirely took false positives from 1/8 to 5/8.
SPAN_MAX_COVERAGE = 0.90

_PROMPT = """You label a student's career question with the cognitive biases in it.

Bias types:
- availability_heuristic: generalising from one vivid case - a friend's or
  senior's outcome, a news story, a video, a social-media post.
- anchoring: fixating on ONE employer, number, or place and excluding the rest.
- confirmation: seeking agreement for a belief already held ("right?", "don't
  you agree?").
- loss_aversion: framed around avoiding a loss or risk rather than pursuing a goal.
- consistency: continuing because of prior investment or a public commitment
  (sunk cost, "I already told everyone", "too late to change").
- dunning_kruger: mis-calibrated self-assessment in EITHER direction, over- or
  under-confident.

MOST QUESTIONS ARE NEUTRAL. A student asking what a module covers, how something
is assessed, or what two careers differ in is asking a factual question and has
NO bias. Only label a bias when specific words in the question show it.

Worked examples:
{examples}

Now label this question. It may be English, Nepali, or a mix. Judge the framing,
not the topic.

Question: "{query}"

Reply with ONLY a JSON array. Each element is {{"bias": <type>, "evidence": <the
exact words from the question that show it>}}. The evidence must be copied
verbatim from the question. Reply [] if the question is neutral.
No explanation."""


def _normalise(text: str) -> str:
    """Casefold and collapse whitespace for span comparison."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^\wऀ-ॿ]+", _normalise(text)) if t]


def span_is_grounded(evidence: str, query: str) -> bool:
    """True if ``evidence`` is a real, *localised* span of ``query``.

    Two conditions, and both matter:

    1. PRESENT - verbatim substring, or enough token overlap that a lightly
       reworded quote survives while an invented one does not.
    2. LOCALISED - shorter than ``SPAN_MAX_COVERAGE`` of the question. Without
       this, quoting the entire question satisfies (1) trivially, which is how
       every observed false positive got through.

    An empty quote is never grounded - that is the zero-shot failure mode this
    check exists to catch.
    """
    if not evidence or not evidence.strip():
        return False
    ev_tokens = _tokens(evidence)
    q_tokens_list = _tokens(query)
    if not ev_tokens or not q_tokens_list:
        return False

    # (2) localised: a quote that swallows the question is not evidence.
    if len(ev_tokens) / len(q_tokens_list) > SPAN_MAX_COVERAGE:
        return False

    # (1) present.
    if _normalise(evidence) in _normalise(query):
        return True
    q_tokens = set(q_tokens_list)
    hits = sum(1 for t in ev_tokens if t in q_tokens)
    return hits / len(ev_tokens) >= SPAN_OVERLAP_MIN


def _parse_flags(raw: str) -> list[tuple[str, str]]:
    """Pull (bias_type, evidence) pairs out of the reply, tolerating stray text."""
    if not raw:
        return []
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[tuple[str, str]] = []
    for item in parsed:
        if isinstance(item, dict):
            bias = str(item.get("bias", "")).strip().lower()
            evidence = str(item.get("evidence", "")).strip()
            if bias in BIAS_TYPES:
                out.append((bias, evidence))
    return out


class RAGBiasDetector:
    """Retrieval-augmented few-shot LLM classifier with verified evidence spans.

    Same ``detect(query_text, profile)`` contract as every other detector here.
    Degrades to the rule-based detector on any failure - losing bias detection
    silently would be worse than being slow.
    """

    def __init__(
        self,
        k: int = DEFAULT_K,
        model: str | None = None,
        client: Any = None,
        require_grounding: bool = True,
    ) -> None:
        self._k = k
        self._model = model
        self._client = client
        self._require_grounding = require_grounding
        self._retriever: Any = None
        self._rules: Any = None
        self._pool: Any = None
        self._pool_matrix: Any = None
        self._llm_ok: bool | None = None  # latched availability probe

    # ── Lazy dependencies ────────────────────────────────────────────────────

    def _get_retriever(self):
        """Encoder + labelled exemplar bank, reused from the semantic detector."""
        if self._retriever is None:
            from drona.advising.semantic_bias import SemanticBiasDetector

            det = SemanticBiasDetector()
            det._ensure_model()  # noqa: SLF001 - deliberately sharing the encoder
            self._retriever = det
        return self._retriever

    def _get_client(self):
        if self._client is None:
            from drona.advising.llm_client import LLMClient
            from drona.utils.settings import settings

            self._client = LLMClient(model=self._model or settings.nepali_ollama_model)
        return self._client

    def _llm_available(self) -> bool:
        """Probe the model once per process and remember the answer.

        A stub or injected client is trusted without probing - tests supply one
        deliberately, and an injected client has no availability contract.
        """
        if self._llm_ok is None:
            if self._client is not None:
                self._llm_ok = True
            else:
                try:
                    self._llm_ok = bool(self._get_client().is_available())
                except Exception as exc:  # noqa: BLE001
                    self._llm_ok = False
                    logger.warning(f"bias-detection LLM probe failed: {exc}")
                if not self._llm_ok:
                    logger.info(
                        "No LLM served; bias detection runs rules-only "
                        "(recall 0.511 instead of 0.633)"
                    )
        return self._llm_ok

    def _get_rules(self):
        if self._rules is None:
            from drona.advising.bias_detector import BiasDetector

            self._rules = BiasDetector()
        return self._rules

    # ── Retrieval ────────────────────────────────────────────────────────────

    def _neighbours(self, query_text: str) -> list[tuple[str, list[str]]]:
        """The k nearest labelled dev questions, as (text, bias_types).

        Neutral questions carry an empty label list and are deliberately kept -
        they are what tells the model that "no bias" is a common answer.
        """
        det = self._get_retriever()
        if self._pool_matrix is None:
            from drona.evaluation.heldout_queries import HELDOUT_C2_QUERIES
            from drona.evaluation.queries import C2_QUERIES

            self._pool = list(C2_QUERIES) + list(HELDOUT_C2_QUERIES)
            self._pool_matrix = det._model.encode(  # noqa: SLF001
                [q.query_text for q in self._pool],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        pool = self._pool
        q_vec = det._model.encode(  # noqa: SLF001
            [query_text], normalize_embeddings=True
        )[0]
        sims = self._pool_matrix @ q_vec
        order = sorted(range(len(pool)), key=lambda i: -float(sims[i]))[: self._k]
        return [(pool[i].query_text, list(pool[i].expected_biases)) for i in order]

    def _format_examples(self, neighbours: list[tuple[str, list[str]]]) -> str:
        lines = []
        for text, biases in neighbours:
            if biases:
                labelled = json.dumps(
                    [{"bias": b, "evidence": "..."} for b in biases], ensure_ascii=False
                )
            else:
                labelled = "[]"
            lines.append(f'Question: "{text}"\nAnswer: {labelled}')
        return "\n\n".join(lines)

    # ── Detection ────────────────────────────────────────────────────────────

    def detect(
        self, query_text: str, profile: StudentProfile | None = None
    ) -> list[BiasFlag]:
        if not query_text.strip():
            return []

        # Cheap check before the expensive one. Retrieval loads a ~470 MB encoder;
        # the LLM probe is one HTTP call. Checking the LLM first means a robot (or
        # a CI runner) with no model served never pays for an encoder it cannot
        # use. The result is latched, so an unavailable model costs one probe for
        # the whole process instead of one per query.
        if not self._llm_available():
            return self._get_rules().detect(query_text, profile=profile)

        try:
            neighbours = self._neighbours(query_text)
            prompt = _PROMPT.format(
                examples=self._format_examples(neighbours), query=query_text
            )
            raw = self._get_client().complete(prompt, max_tokens=256, temperature=0.0)
        except Exception as exc:  # noqa: BLE001 - never break advising
            logger.warning(f"RAG bias detection failed ({exc}); using rules")
            return self._get_rules().detect(query_text, profile=profile)

        if not raw:
            logger.warning("RAG bias detection returned nothing; using rules")
            return self._get_rules().detect(query_text, profile=profile)

        flags: list[BiasFlag] = []
        seen: set[str] = set()
        for bias, evidence in _parse_flags(raw):
            if bias in seen:
                continue
            if self._require_grounding and not span_is_grounded(evidence, query_text):
                logger.debug(f"dropped ungrounded {bias} flag (evidence: {evidence!r})")
                continue
            seen.add(bias)
            quoted = evidence.strip() or query_text.strip()
            flags.append(
                BiasFlag(
                    bias_type=bias,  # type: ignore[arg-type]
                    detected_signal=f'"{quoted}"',
                    mitigation_applied=_MITIGATIONS.get(bias, ""),
                )
            )
        return flags


class RAGHybridBiasDetector:
    """Rules ∪ RAG-LLM - the production configuration.

    The rule layer is free and has never produced a false positive on any set;
    the RAG layer adds the phrasings nobody wrote a pattern for. Union keeps
    every rule hit, so recall can only improve on the rules alone.
    """

    def __init__(self, k: int = DEFAULT_K, model: str | None = None) -> None:
        from drona.advising.bias_detector import BiasDetector

        self._rules = BiasDetector()
        self._rag = RAGBiasDetector(k=k, model=model)

    def detect(
        self, query_text: str, profile: StudentProfile | None = None
    ) -> list[BiasFlag]:
        flags = list(self._rules.detect(query_text, profile=profile))
        seen = {f.bias_type for f in flags}
        for f in self._rag.detect(query_text, profile=profile):
            if f.bias_type not in seen:
                flags.append(f)
                seen.add(f.bias_type)
        return flags


def make_bias_detector():
    """The detector the advising pipeline should use, per ``settings.bias_detector``.

    Returns the grounded hybrid by default and the regex detector when configured
    for it - or when the hybrid cannot be constructed at all. Bias detection is a
    core safety behaviour of this system, so the failure mode is "less recall",
    never "no detection".
    """
    from drona.advising.bias_detector import BiasDetector
    from drona.utils.settings import settings

    if settings.bias_detector == "rules":
        return BiasDetector()
    try:
        return RAGHybridBiasDetector()
    except Exception as exc:  # noqa: BLE001 - degrade, never fail startup
        logger.warning(f"Hybrid bias detector unavailable ({exc}); using rules only")
        return BiasDetector()
