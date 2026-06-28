"""
Phase 2 tests - citation verification, Qwen fallback, LangGraph orchestration,
and the FastAPI advising API.

Pure-logic tests run everywhere. LangGraph and FastAPI tests use importorskip so
the suite still passes on a [dev]-only install (CI), while running fully when the
[backend] extras are present.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from drona.advising import graph as gmod
from drona.advising.engine import make_query
from drona.advising.verify import verify_pathways
from drona.contracts import (
    AdvisingResponse,
    DataTier,
    PathwayRecommendation,
    RetrievalCitation,
)


def _cit(source_id: str, score: float = 0.05) -> RetrievalCitation:
    return RetrievalCitation(
        source_type="job_posting",
        source_id=source_id,
        tier=DataTier.NEPAL,
        excerpt="Nepali tech role excerpt.",
        relevance_score=score,
    )


def _pathway(title: str, cits: list[RetrievalCitation]) -> PathwayRecommendation:
    return PathwayRecommendation(
        pathway_title=title, rationale="because", citations=cits, confidence="high"
    )


# ── Citation verification ─────────────────────────────────────────────────────

class TestVerify:
    def test_grounded_pathway_kept(self) -> None:
        retrieved = [_cit("a"), _cit("b")]
        pw = _pathway("Backend Dev", [_cit("a")])
        report = verify_pathways([pw], retrieved)
        assert report.all_grounded
        assert report.grounded_pathways[0].citations[0].source_id == "a"

    def test_hallucinated_citation_dropped_and_flagged(self) -> None:
        retrieved = [_cit("a")]
        pw = _pathway("Ghost Dev", [_cit("zzz")])  # cites a doc that wasn't retrieved
        report = verify_pathways([pw], retrieved)
        assert "Ghost Dev" in report.ungrounded_titles
        assert report.grounded_pathways[0].confidence == "low"
        assert report.grounded_pathways[0].citations == []
        assert report.issues

    def test_mixed_citations_keeps_valid_only(self) -> None:
        retrieved = [_cit("a"), _cit("b")]
        pw = _pathway("Mixed", [_cit("a"), _cit("nope")])
        report = verify_pathways([pw], retrieved)
        kept = report.grounded_pathways[0].citations
        assert len(kept) == 1 and kept[0].source_id == "a"

    def test_grounded_fraction(self) -> None:
        retrieved = [_cit("a")]
        good = _pathway("Good", [_cit("a")])
        bad = _pathway("Bad", [_cit("x")])
        report = verify_pathways([good, bad], retrieved)
        assert report.grounded_fraction == 0.5


# ── Qwen fallback in LLMClient ────────────────────────────────────────────────

class TestLLMFallback:
    def _client_with(self, loaded: list[str]):
        from drona.advising.llm_client import LLMClient

        client = LLMClient(model="phi3.5:x", fallback_model="qwen2.5:y")
        mock = MagicMock()
        mock.list.return_value = SimpleNamespace(
            models=[SimpleNamespace(model=name) for name in loaded]
        )
        client._client = mock
        return client, mock

    def test_available_models_prefers_primary(self) -> None:
        client, _ = self._client_with(["phi3.5:latest", "qwen2.5:3b"])
        assert client._available_models() == ["phi3.5:x", "qwen2.5:y"]

    def test_available_models_fallback_only(self) -> None:
        client, _ = self._client_with(["qwen2.5:3b"])
        assert client._available_models() == ["qwen2.5:y"]

    def test_is_available_true_if_only_fallback(self) -> None:
        client, _ = self._client_with(["qwen2.5:3b"])
        assert client.is_available() is True

    def test_generate_falls_back_to_qwen_on_primary_failure(self) -> None:
        client, mock = self._client_with(["phi3.5:latest", "qwen2.5:3b"])

        def chat(model, messages, options, keep_alive=None):
            if model == "phi3.5:x":
                raise RuntimeError("primary down")
            return SimpleNamespace(
                message=SimpleNamespace(content='{"pathways": [], "speak_text": "hi from qwen"}')
            )

        mock.chat.side_effect = chat
        pathways, speak, refusal, err = client.generate(
            system_prompt="s", user_prompt="u",
            query=make_query("test"), citations=[], bias_flags=[], max_retries=1,
        )
        assert refusal is False
        assert speak == "hi from qwen"


# ── Graph nodes (no LangGraph required) ───────────────────────────────────────

class TestGraphNodes:
    def _stub_doc(self, id_: str):
        return SimpleNamespace(
            id=id_,
            text="Python developer roles in Kathmandu need 2+ years.",
            metadata={"tier": "nepal", "source_type": "job_posting"},
            rrf_score=0.05,
        )

    def _components(self, llm_returns=None, available=True):
        retriever = MagicMock()
        docs = [self._stub_doc("doc1"), self._stub_doc("doc2")]
        retriever.retrieve_raw.return_value = docs
        reranker = MagicMock()
        reranker.rerank_docs.return_value = docs
        detector = MagicMock()
        detector.detect.return_value = []
        llm = MagicMock()
        llm.is_available.return_value = available
        if llm_returns is None:
            pw = _pathway("Software Developer", [_cit("doc1")])
            llm_returns = ([pw], "Found a pathway.", False, None)
        llm.generate.return_value = llm_returns
        return gmod.GraphComponents(retriever=retriever, reranker=reranker, detector=detector, llm=llm)

    def test_node_retrieve_sets_coverage(self) -> None:
        comp = self._components()
        out = gmod.node_retrieve(comp, {"query": make_query("python jobs")})
        assert out["coverage_ok"] is True
        assert len(out["citations"]) == 2

    def test_node_retrieve_low_coverage_refuses(self) -> None:
        comp = self._components()
        comp.retriever.retrieve_raw.return_value = [self._stub_doc("only")]
        comp.reranker.rerank_docs.return_value = [self._stub_doc("only")]
        out = gmod.node_retrieve(comp, {"query": make_query("rare")})
        assert out["coverage_ok"] is False

    def test_node_generate_unavailable_refuses(self) -> None:
        comp = self._components(available=False)
        out = gmod.node_generate(comp, {"query": make_query("x"), "citations": [_cit("doc1")]})
        assert out["refusal"] is True
        assert "not available" in out["refusal_reason"].lower()

    def test_route_after_retrieve(self) -> None:
        assert gmod.route_after_retrieve({"coverage_ok": True}) == "generate"
        assert gmod.route_after_retrieve({"coverage_ok": False}) == "format"

    def test_route_after_generate_retries_on_parse_failure(self) -> None:
        state = {"refusal": True, "refusal_reason": "JSON parse error", "generate_attempts": 1}
        assert gmod.route_after_generate(state) == "generate"

    def test_route_after_generate_no_retry_when_unavailable(self) -> None:
        state = {"refusal": True, "refusal_reason": "model is not available", "generate_attempts": 1}
        assert gmod.route_after_generate(state) == "verify"

    def test_node_format_builds_response(self) -> None:
        comp = self._components()
        pw = _pathway("Dev", [_cit("doc1")])
        out = gmod.node_format(comp, {
            "query": make_query("x"), "coverage_ok": True,
            "pathways": [pw], "citations": [_cit("doc1")], "speak_text": "hi",
        })
        assert isinstance(out["response"], AdvisingResponse)
        assert out["response"].refusal is False

    def test_node_format_refusal_on_low_coverage(self) -> None:
        comp = self._components()
        out = gmod.node_format(comp, {"query": make_query("x"), "coverage_ok": False})
        assert out["response"].refusal is True


# ── Full LangGraph run (requires langgraph) ───────────────────────────────────

class TestAdvisingGraph:
    def _components(self):
        return TestGraphNodes()._components()

    def test_graph_runs_end_to_end(self) -> None:
        pytest.importorskip("langgraph")
        comp = self._components()
        ag = gmod.AdvisingGraph(comp)
        resp = ag.advise(make_query("What Python jobs exist in Nepal?"))
        assert isinstance(resp, AdvisingResponse)
        assert resp.refusal is False
        assert len(resp.pathways) == 1

    def test_graph_stream_yields_nodes_then_response(self) -> None:
        pytest.importorskip("langgraph")
        comp = self._components()
        ag = gmod.AdvisingGraph(comp)
        chunks = list(ag.stream(make_query("python jobs")))
        nodes_seen = {k for chunk in chunks for k in chunk}
        assert "format" in nodes_seen


# ── FastAPI app (requires fastapi) ────────────────────────────────────────────

class TestApi:
    def _client(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from drona.api import dependencies
        from drona.api.app import app

        stub = MagicMock()
        resp = AdvisingResponse(
            query_id=str(uuid.uuid4()),
            summary="A summary.",
            pathways=[_pathway("Dev", [_cit("doc1")])],
            speak_text="Here you go.",
        )
        stub.advise.return_value = resp

        def stub_stream(query):
            yield {"detect_bias": {"bias_flags": []}}
            yield {"retrieve": {"coverage_ok": True}}
            yield {"format": {"response": resp}}

        stub.stream.side_effect = stub_stream
        dependencies.set_advisor(stub)
        app.dependency_overrides[dependencies.get_advisor] = lambda: stub
        return TestClient(app), stub

    def test_health(self) -> None:
        client, _ = self._client()
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["orchestrator"]

    def test_advise_returns_response(self) -> None:
        client, _ = self._client()
        r = client.post("/advise", json={"query_text": "What jobs use Python in Nepal?"})
        assert r.status_code == 200
        body = r.json()
        assert body["summary"] == "A summary."
        assert body["pathways"][0]["pathway_title"] == "Dev"

    def test_advise_validates_input(self) -> None:
        client, _ = self._client()
        r = client.post("/advise", json={"query_text": ""})  # min_length=1
        assert r.status_code == 422

    def test_websocket_streams_events(self) -> None:
        client, _ = self._client()
        with client.websocket_connect("/ws/advise") as ws:
            ws.send_json({"query_text": "python jobs in nepal"})
            events = []
            while True:
                msg = ws.receive_json()
                events.append(msg)
                if msg["event"] == "result":
                    break
        kinds = [e["event"] for e in events]
        assert "node" in kinds
        assert kinds[-1] == "result"
        assert events[-1]["response"]["summary"] == "A summary."
