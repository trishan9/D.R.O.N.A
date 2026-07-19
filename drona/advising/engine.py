"""
Advising engine for D.R.O.N.A. - end-to-end AdvisingQuery → AdvisingResponse.

Pipeline (four stages, each independently testable):
  1. Retrieval  - hybrid dense+BM25 → top-20 raw docs (Retriever)
  2. Reranking  - cross-encoder → top-5 docs (Reranker)
  3. Bias detection - rule-based query analysis (BiasDetector)
  4. Generation - bias-aware prompt → local LLM → structured parse (LLMClient)

Fallback chain:
  If the LLM is unavailable or generation fails, the engine returns a refusal
  AdvisingResponse (refusal=True) rather than raising. The orchestrator layer
  can then route to a human advisor. This ensures the robot never gets stuck
  in an error state during an advising session.

Minimum citation coverage check:
  If retrieval returns fewer than 2 relevant documents (all with rrf_score
  below settings.min_citation_score), we skip generation and return a
  refusal response explaining the coverage gap. Better to be honest about
  lack of data than to hallucinate.
"""

from __future__ import annotations

import time
import uuid

from loguru import logger

from drona.advising.bias_detector import BiasDetector
from drona.advising.llm_client import LLMClient, make_llm_client
from drona.advising.prompt_builder import build_prompt
from drona.advising.reranker import Reranker
from drona.advising.retriever import Retriever
from drona.contracts import AdvisingQuery, AdvisingResponse, BiasFlag, RetrievalCitation
from drona.utils.settings import settings

_MIN_CITATION_SCORE = 0.01  # RRF scores are small floats; 0.01 is a real hit


class AdvisingEngine:
    """End-to-end advising pipeline.

    Instantiating this class loads embedding models and the ChromaDB client.
    Keep a single instance alive for the session (models are lazy-loaded but
    expensive to initialise).
    """

    def __init__(
        self,
        retriever: Retriever | None = None,
        reranker: Reranker | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self._retriever = retriever or Retriever()
        self._reranker = reranker or Reranker()
        self._detector = BiasDetector()
        self._llm = llm or make_llm_client()

    # ── Public API ─────────────────────────────────────────────────────────────

    def advise(self, query: AdvisingQuery) -> AdvisingResponse:
        """Run the full advising pipeline.

        Args:
            query: An AdvisingQuery with query_text and student profile.

        Returns:
            An AdvisingResponse with pathways, bias flags, and speak_text.
        """
        t_total = time.monotonic()
        logger.info(f"Advising session [{query.query_id}]: {query.query_text[:80]}…")

        # Stage 1: Retrieve
        raw_docs = self._retriever.retrieve_raw(
            query.query_text,
            top_k=settings.retrieval_top_k,
        )

        # Coverage gate on the EMBEDDING-retrieval scores (RRF), which are robust
        # to typos/misspellings. The cross-encoder reranker below only RE-ORDERS;
        # it must not gate, because cross-encoders score misspelled queries very
        # low and would otherwise wrongly refuse a perfectly answerable question.
        good_raw = [
            d for d in raw_docs if getattr(d, "rrf_score", 0.0) >= _MIN_CITATION_SCORE
        ]
        if len(good_raw) < 2:
            elapsed_ms = int((time.monotonic() - t_total) * 1000)
            logger.warning(
                f"Insufficient retrieval coverage ({len(good_raw)} docs) "
                f"for query [{query.query_id}]"
            )
            return self._build_refusal(
                query,
                reason=(
                    "The knowledge base does not have enough relevant documents "
                    "to answer this question reliably. Please consult a human advisor "
                    "or try rephrasing your question."
                ),
                generation_time_ms=elapsed_ms,
            )

        # Stage 2: Rerank (re-orders the retrieved docs; does not gate)
        reranked_docs = self._reranker.rerank_docs(
            query.query_text,
            raw_docs,
            top_n=settings.rerank_top_k,
        )
        from drona.advising.retriever import _build_citation
        citations: list[RetrievalCitation] = [_build_citation(d) for d in reranked_docs]

        # Stage 3: Bias detection
        bias_flags: list[BiasFlag] = self._detector.detect(
            query.query_text,
            profile=query.profile,
        )
        if bias_flags:
            logger.debug(
                f"Bias flags: {[f.bias_type for f in bias_flags]}"
            )

        # Stage 4: Generate
        # Resolve the response language (auto-detects Nepali/Devanagari) and build
        # the prompt for it; the LLM router sends the turn to the matching model.
        from drona.utils.language import resolve_language
        language = resolve_language(settings.advisor_language, query.query_text)
        system_prompt, user_prompt = build_prompt(
            query, citations, bias_flags, language=language
        )

        if not self._llm.is_available():
            elapsed_ms = int((time.monotonic() - t_total) * 1000)
            logger.error("Ollama unavailable - returning refusal response")
            return self._build_refusal(
                query,
                reason=(
                    "The language model is not available right now. "
                    "Please try again shortly or speak with a human advisor."
                ),
                generation_time_ms=elapsed_ms,
                bias_flags=bias_flags,
                citations=citations,
            )

        pathways, speak_text, refusal, refusal_reason = self._llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            query=query,
            citations=citations,
            bias_flags=bias_flags,
        )

        elapsed_ms = int((time.monotonic() - t_total) * 1000)
        logger.info(
            f"Advising [{query.query_id}] complete in {elapsed_ms}ms - "
            f"{len(pathways)} pathways, {len(bias_flags)} bias flags, "
            f"refusal={refusal}"
        )

        if refusal:
            return self._build_refusal(
                query,
                reason=refusal_reason or "Generation failed.",
                generation_time_ms=elapsed_ms,
                bias_flags=bias_flags,
                citations=citations,
            )

        summary = _build_summary(pathways, citations)

        return AdvisingResponse(
            query_id=query.query_id,
            summary=summary,
            pathways=pathways,
            bias_flags=bias_flags,
            refusal=False,
            refusal_reason=None,
            speak_text=speak_text or _default_speak(pathways),
            requires_human_followup=len(pathways) == 0,
            generation_time_ms=elapsed_ms,
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_refusal(
        query: AdvisingQuery,
        reason: str,
        generation_time_ms: int,
        bias_flags: list[BiasFlag] | None = None,
        citations: list[RetrievalCitation] | None = None,
    ) -> AdvisingResponse:
        return AdvisingResponse(
            query_id=query.query_id,
            summary=reason,
            pathways=[],
            bias_flags=bias_flags or [],
            refusal=True,
            refusal_reason=reason,
            speak_text=(
                "I'm sorry, I don't have enough information to answer that right now. "
                "Please speak with a human advisor."
            ),
            requires_human_followup=True,
            generation_time_ms=generation_time_ms,
        )


# ── Convenience factory ────────────────────────────────────────────────────────

def make_query(
    text: str,
    session_id: str | None = None,
    year: int | None = None,
    completed: list[str] | None = None,
    skills: list[str] | None = None,
    geography: str = "any",
    max_pathways: int = 3,
    programme: str = "software_engineering",
    goal: str = "employment",
    target_institutions: list[str] | None = None,
    timeline_years: int | None = None,
) -> AdvisingQuery:
    """Helper to construct an AdvisingQuery without boilerplate.

    Useful for CLI scripts and tests. Carries the goal taxonomy (programme, goal,
    target_institutions, timeline) so goal-aware advising is reachable here too.
    """
    from drona.contracts import StudentProfile

    sid = session_id or str(uuid.uuid4())
    profile = StudentProfile(
        session_id=sid,
        programme=programme,
        year_of_study=year,
        completed_modules=completed or [],
        declared_skills=skills or [],
        aspiration_geography=geography,  # type: ignore[arg-type]
        goal=goal,  # type: ignore[arg-type]
        target_institutions=target_institutions or [],
        timeline_years=timeline_years,
    )
    return AdvisingQuery(
        query_id=str(uuid.uuid4()),
        query_text=text,
        profile=profile,
        max_pathways=max_pathways,
    )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _build_summary(pathways, citations) -> str:
    if not pathways:
        return "No relevant career pathways could be identified for this query."
    titles = ", ".join(p.pathway_title for p in pathways)
    n_cit = len(citations)
    return (
        f"Based on {n_cit} retrieved document{'s' if n_cit != 1 else ''}, "
        f"here are {len(pathways)} career pathway{'s' if len(pathways) != 1 else ''} "
        f"to consider: {titles}."
    )


def _default_speak(pathways) -> str:
    if not pathways:
        return "I've found some relevant information. Let me show you the details on screen."
    first = pathways[0].pathway_title
    n = len(pathways)
    if n == 1:
        return f"I found one pathway that matches your interests: {first}. Let me show you the details."
    return (
        f"I found {n} pathways that match your interests. "
        f"The first one is {first}. You can see all of them on the screen."
    )
