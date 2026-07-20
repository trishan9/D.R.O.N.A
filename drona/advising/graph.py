"""
LangGraph orchestration for D.R.O.N.A. advising (Mower et al. 2026, Nat. Mach.
Intell. - LLMs in embodied AI; Lewis et al. 2020 - RAG).

The advising request is a small state machine, made explicit as a LangGraph so
the control flow (and its retry/refusal branches) is inspectable and defensible
at viva, rather than buried in imperative code:

    detect_bias → retrieve → generate → verify → format
                                  ↑________│  (retry on parse/grounding failure)

Design choices:
  - Node logic lives in standalone functions (``node_*``) that take the injected
    components + state and return state updates. This makes every node unit-
    testable WITHOUT LangGraph installed (CI runs on [dev] only).
  - LangGraph is imported LAZILY in ``build_graph``; importing this module never
    requires it.
  - The graph reuses the SAME tested components as ``AdvisingEngine``
    (Retriever, Reranker, BiasDetector, LLMClient) plus the new citation
    ``verify`` stage - so this is an orchestration upgrade, not a rewrite.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, TypedDict

from loguru import logger

from drona.advising.llm_client import make_llm_client
from drona.advising.prompt_builder import build_prompt
from drona.advising.rag_bias import make_bias_detector
from drona.advising.reranker import Reranker
from drona.advising.retriever import Retriever, _build_citation
from drona.advising.verify import verify_pathways
from drona.contracts import (
    AdvisingQuery,
    AdvisingResponse,
    BiasFlag,
    PathwayRecommendation,
    RetrievalCitation,
)
from drona.utils.settings import settings

_MIN_CITATION_SCORE = 0.01
_MAX_GENERATE_ATTEMPTS = 2


@dataclass
class GraphComponents:
    """Injected dependencies for the advising graph (mockable in tests)."""

    retriever: Any
    reranker: Any
    detector: Any
    llm: Any

    @classmethod
    def default(cls) -> GraphComponents:
        return cls(
            retriever=Retriever(),
            reranker=Reranker(),
            detector=make_bias_detector(),
            llm=make_llm_client(),
        )


class AdvisingState(TypedDict, total=False):
    """Mutable state threaded through the graph."""

    query: AdvisingQuery
    bias_flags: list[BiasFlag]
    citations: list[RetrievalCitation]
    coverage_ok: bool
    pathways: list[PathwayRecommendation]
    speak_text: str
    refusal: bool
    refusal_reason: str | None
    generate_attempts: int
    verification_issues: list[str]
    t_start: float
    response: AdvisingResponse


# ── Nodes (pure-ish: components injected, return state deltas) ──────────────────

def node_detect_bias(comp: GraphComponents, state: AdvisingState) -> AdvisingState:
    query = state["query"]
    flags = comp.detector.detect(query.query_text, profile=query.profile)
    if flags:
        logger.debug(f"Bias flags: {[f.bias_type for f in flags]}")
    return {"bias_flags": flags}


def node_retrieve(comp: GraphComponents, state: AdvisingState) -> AdvisingState:
    query = state["query"]
    raw = comp.retriever.retrieve_raw(query.query_text, top_k=settings.retrieval_top_k)
    # Gate on the typo-tolerant embedding-retrieval scores; the cross-encoder
    # reranker only re-orders (it scores misspelled queries very low, so gating
    # on its scores would wrongly refuse answerable questions).
    good_raw = [d for d in raw if getattr(d, "rrf_score", 0.0) >= _MIN_CITATION_SCORE]
    reranked = comp.reranker.rerank_docs(query.query_text, raw, top_n=settings.rerank_top_k)
    citations = [_build_citation(d) for d in reranked]
    return {"citations": citations, "coverage_ok": len(good_raw) >= 2}


def node_generate(comp: GraphComponents, state: AdvisingState) -> AdvisingState:
    query = state["query"]
    citations = state.get("citations", [])
    bias_flags = state.get("bias_flags", [])
    attempts = state.get("generate_attempts", 0) + 1

    if not comp.llm.is_available():
        return {
            "refusal": True,
            "refusal_reason": (
                "The language model is not available right now. "
                "Please try again shortly or speak with a human advisor."
            ),
            "pathways": [],
            "speak_text": "",
            "generate_attempts": attempts,
        }

    system_prompt, user_prompt = build_prompt(query, citations, bias_flags)
    pathways, speak_text, refusal, refusal_reason = comp.llm.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        query=query,
        citations=citations,
        bias_flags=bias_flags,
    )
    return {
        "pathways": pathways,
        "speak_text": speak_text,
        "refusal": refusal,
        "refusal_reason": refusal_reason,
        "generate_attempts": attempts,
    }


def node_verify(comp: GraphComponents, state: AdvisingState) -> AdvisingState:
    pathways = state.get("pathways", [])
    citations = state.get("citations", [])
    report = verify_pathways(pathways, citations)
    if report.issues:
        logger.debug(f"Verification issues: {report.issues}")
    return {
        "pathways": report.grounded_pathways,
        "verification_issues": report.issues,
    }


def node_format(comp: GraphComponents, state: AdvisingState) -> AdvisingState:
    query = state["query"]
    elapsed_ms = int((time.monotonic() - state.get("t_start", time.monotonic())) * 1000)

    if state.get("refusal") or not state.get("coverage_ok", True):
        reason = state.get("refusal_reason") or (
            "The knowledge base does not have enough relevant documents to answer "
            "this reliably. Please consult a human advisor or rephrase your question."
        )
        return {"response": _refusal(query, reason, elapsed_ms, state.get("bias_flags", []))}

    pathways = state.get("pathways", [])
    citations = state.get("citations", [])
    summary = _build_summary(pathways, citations)
    speak = state.get("speak_text") or _default_speak(pathways)
    return {
        "response": AdvisingResponse(
            query_id=query.query_id,
            summary=summary,
            pathways=pathways,
            bias_flags=state.get("bias_flags", []),
            refusal=False,
            refusal_reason=None,
            speak_text=speak,
            requires_human_followup=len(pathways) == 0,
            generation_time_ms=elapsed_ms,
        )
    }


# ── Routing ─────────────────────────────────────────────────────────────────

def route_after_retrieve(state: AdvisingState) -> str:
    """Skip straight to format (refusal) when retrieval coverage is too thin."""
    return "generate" if state.get("coverage_ok") else "format"


def route_after_generate(state: AdvisingState) -> str:
    """Retry generation on parse failure (bounded), else verify."""
    if state.get("refusal") and state.get("generate_attempts", 0) < _MAX_GENERATE_ATTEMPTS:
        # Only retry transient parse/generation failures, not "LLM unavailable".
        reason = (state.get("refusal_reason") or "").lower()
        if "not available" not in reason:
            logger.info("Retrying generation after parse failure")
            return "generate"
    return "verify"


# ── Graph builder (LangGraph, lazy) ───────────────────────────────────────────

def build_graph(comp: GraphComponents | None = None):
    """Compile and return the LangGraph StateGraph. Requires langgraph installed."""
    from langgraph.graph import END, START, StateGraph

    components = comp or GraphComponents.default()

    def _bind(fn):
        return lambda state: fn(components, state)

    g = StateGraph(AdvisingState)
    g.add_node("detect_bias", _bind(node_detect_bias))
    g.add_node("retrieve", _bind(node_retrieve))
    g.add_node("generate", _bind(node_generate))
    g.add_node("verify", _bind(node_verify))
    g.add_node("format", _bind(node_format))

    g.add_edge(START, "detect_bias")
    g.add_edge("detect_bias", "retrieve")
    g.add_conditional_edges("retrieve", route_after_retrieve, {"generate": "generate", "format": "format"})
    g.add_conditional_edges("generate", route_after_generate, {"generate": "generate", "verify": "verify"})
    g.add_edge("verify", "format")
    g.add_edge("format", END)
    return g.compile()


class AdvisingGraph:
    """LangGraph-backed advising orchestrator - drop-in for AdvisingEngine.advise."""

    def __init__(self, comp: GraphComponents | None = None) -> None:
        self._comp = comp or GraphComponents.default()
        self._graph = build_graph(self._comp)

    def advise(self, query: AdvisingQuery) -> AdvisingResponse:
        logger.info(f"[graph] advising [{query.query_id}]: {query.query_text[:80]}…")
        final = self._graph.invoke({"query": query, "t_start": time.monotonic()})
        return final["response"]

    def stream(self, query: AdvisingQuery):
        """Yield per-node state deltas ({node_name: delta}) for websocket streaming."""
        yield from self._graph.stream({"query": query, "t_start": time.monotonic()})


# ── Shared helpers (kept consistent with engine.py) ───────────────────────────

def _refusal(
    query: AdvisingQuery, reason: str, elapsed_ms: int, bias_flags: list[BiasFlag]
) -> AdvisingResponse:
    return AdvisingResponse(
        query_id=query.query_id,
        summary=reason,
        pathways=[],
        bias_flags=bias_flags,
        refusal=True,
        refusal_reason=reason,
        speak_text=(
            "I'm sorry, I don't have enough information to answer that right now. "
            "Please speak with a human advisor."
        ),
        requires_human_followup=True,
        generation_time_ms=elapsed_ms,
    )


def _build_summary(pathways: list, citations: list) -> str:
    if not pathways:
        return "No relevant career pathways could be identified for this query."
    titles = ", ".join(p.pathway_title for p in pathways)
    n = len(citations)
    return (
        f"Based on {n} retrieved document{'s' if n != 1 else ''}, here are "
        f"{len(pathways)} career pathway{'s' if len(pathways) != 1 else ''} "
        f"to consider: {titles}."
    )


def _default_speak(pathways: list) -> str:
    if not pathways:
        return "I've found some relevant information. Let me show you the details on screen."
    first = pathways[0].pathway_title
    n = len(pathways)
    if n == 1:
        return f"I found one pathway that matches your interests: {first}. Let me show you the details."
    return (
        f"I found {n} pathways that match your interests. The first one is {first}. "
        f"You can see all of them on the screen."
    )


def make_query_id() -> str:
    return str(uuid.uuid4())
