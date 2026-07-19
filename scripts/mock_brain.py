#!/usr/bin/env python3
"""
Mock advising brain - a tiny stand-in for the T4 /advise API.

Serves the same POST /advise + GET /health contract as the real brain
(drona.api.app) but returns a canned, deterministic AdvisingResponse instantly.
Used to test the robot's full ask -> advise -> speak loop without a GPU or the
slow local LLM. Point the robot at it with advisor_remote_url:=http://HOST:8099.

Uses only the Python standard library so it runs in the thin robot runtime
(no FastAPI/uvicorn needed).

    python3 scripts/mock_brain.py [port]
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _answer(query_text: str, goal: str) -> dict:
    q = (query_text or "your question").strip()
    speak = (
        "Great question. Based on your interests and the Softwarica curriculum, "
        "I'd suggest three grounded next steps: strengthen your data-structures "
        "and systems modules, build one real project you can show, and target the "
        "Kathmandu tech companies that hire for those skills. "
        "I've put the full pathways on the screen."
    )
    return {
        "query_id": "mock-" + str(abs(hash(q)) % 10000),
        "summary": f"Three pathways relevant to: {q[:60]}",
        # Fields mirror drona.contracts.PathwayRecommendation exactly (the real
        # brain validates against it, so the mock must too): confidence is a
        # Literal low|medium|high, citations use RetrievalCitation's schema.
        "pathways": [{
            "pathway_title": "Backend Engineer (Nepal-first)",
            "rationale": "Matches your completed modules; strong local demand.",
            "matched_softwarica_modules": ["Databases", "Web Technologies"],
            "local_market_evidence": "Kathmandu postings list SQL + REST APIs.",
            "next_concrete_steps": [
                "Finish the Databases and Web modules",
                "Ship one REST API project on GitHub",
                "Apply to Deerwalk / Leapfrog / Fusemachines",
            ],
            "citations": [{
                "source_type": "curriculum",
                "source_id": "MOD-DB",
                "tier": "nepal",
                "excerpt": "Relational databases and SQL",
                "relevance_score": 0.9,
            }],
            "confidence": "high",
            "goal_type": goal,
        }],
        "bias_flags": [],
        "refusal": False,
        "refusal_reason": None,
        "speak_text": speak,
        "requires_human_followup": False,
        "generation_time_ms": 5,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_a) -> None:  # quiet
        pass

    def _send(self, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send({"status": "ok", "llm_available": True, "backend": "mock"})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/advise":
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            req = {}
        self._send(_answer(req.get("query_text", ""), req.get("goal", "employment")))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    print(f"mock brain on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
