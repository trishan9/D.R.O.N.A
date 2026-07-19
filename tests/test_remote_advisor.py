"""Tests for the RemoteAdvisor thin client (robot -> GPU-served brain).

Uses httpx's MockTransport so no real server is needed - we assert the request
mapping and, crucially, that every failure path degrades to a refusal instead of
raising (a robot must never crash on a network fault).
"""

from __future__ import annotations

import httpx
import pytest

from drona.advising.engine import make_query
from drona.advising.remote import RemoteAdvisor, _query_to_payload, make_advisor
from drona.api.schemas import AdviseRequest


def test_payload_matches_api_schema():
    """The client's request body must validate against the API's AdviseRequest."""
    q = make_query(
        "How do I get into MIT?", programme="csai", goal="postgrad_abroad",
        target_institutions=["MIT"], timeline_years=2, year=3,
        skills=["python"], completed=["CS101"],
    )
    payload = _query_to_payload(q)
    req = AdviseRequest.model_validate(payload)  # raises if fields drift
    assert req.goal == "postgrad_abroad"
    assert req.target_institutions == ["MIT"]
    assert req.programme == "csai"


def test_advise_round_trip(monkeypatch):
    """A 200 with a valid AdvisingResponse body is returned as-is."""
    q = make_query("hello", programme="csai")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = request.content
        return httpx.Response(200, json={
            "query_id": q.query_id,
            "summary": "ok",
            "pathways": [],
            "bias_flags": [],
            "refusal": False,
            "refusal_reason": None,
            "speak_text": "here you go",
            "requires_human_followup": False,
            "generation_time_ms": 10,
        })

    transport = httpx.MockTransport(handler)

    def fake_post(url, **kw):
        return httpx.Client(transport=transport).post(url, **kw)

    monkeypatch.setattr(httpx, "post", fake_post)
    adv = RemoteAdvisor("http://brain.local", timeout=5, retries=0)
    resp = adv.advise(q)

    assert not resp.refusal
    assert resp.query_id == q.query_id
    assert resp.speak_text == "here you go"
    assert captured["url"].endswith("/advise")


def test_advise_degrades_on_http_error(monkeypatch):
    """A non-200 must degrade to a refusal, not raise."""
    q = make_query("hello")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: httpx.Client(transport=transport).post(url, **kw)
    )
    adv = RemoteAdvisor("http://brain.local", timeout=5, retries=1)
    resp = adv.advise(q)

    assert resp.refusal
    assert resp.pathways == []
    assert resp.requires_human_followup


def test_advise_degrades_on_network_error(monkeypatch):
    """A transport exception must degrade to a refusal, not propagate."""
    q = make_query("hello")

    def boom(url, **kw):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(httpx, "post", boom)
    adv = RemoteAdvisor("http://brain.local", timeout=2, retries=1)
    resp = adv.advise(q)

    assert resp.refusal
    assert "human advisor" in resp.speak_text.lower()


def test_empty_url_raises():
    """Constructing without a URL is a config error (fail fast, at setup)."""
    with pytest.raises(ValueError):
        RemoteAdvisor("")


def test_make_advisor_falls_back_to_local_engine(monkeypatch):
    """With no remote URL, make_advisor returns the in-process engine, not a client."""
    # Avoid building the heavy engine: stub it.
    import drona.advising.engine as eng

    class _Stub:
        pass

    monkeypatch.setattr(eng, "AdvisingEngine", _Stub)
    advisor = make_advisor(None)
    assert isinstance(advisor, _Stub)


def test_make_advisor_uses_remote_when_url_set():
    advisor = make_advisor("http://brain.local")
    assert isinstance(advisor, RemoteAdvisor)
    assert advisor.base_url == "http://brain.local"
