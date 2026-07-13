"""
D.R.O.N.A. FastAPI application.

Endpoints:
  GET  /health        - liveness + LLM/orchestrator/backend status
  GET  /evaluation    - thesis evaluation results (notebook 05 + training reports)
  POST /advise        - synchronous advising (returns AdvisingResponse)
  WS   /ws/advise     - streaming advising (node-by-node progress + result)

Hard guarantee (proposal C4 "local-only advising"): on startup we assert that
Gemini/Vertex are NOT permitted in the request path. The advising endpoints call
ONLY the local Ollama models via the advisor; no cloud LLM is reachable here.
"""

from __future__ import annotations

import contextlib
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from drona.api.dependencies import Advisor, get_advisor, orchestrator_name
from drona.api.schemas import AdviseRequest, HealthResponse
from drona.api.streaming import stream_graph_events
from drona.contracts import AdvisingResponse
from drona.utils.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce the local-only invariant before serving a single request.
    if settings.allow_gemini_in_request_path:
        raise RuntimeError(
            "ALLOW_GEMINI_IN_REQUEST_PATH must be False - the advising request path "
            "is local-only (Ollama). Gemini/Vertex are offline-only (synthetic gen / eval)."
        )
    logger.info("D.R.O.N.A. API starting - advising request path is LOCAL-ONLY (Ollama)")
    yield
    logger.info("D.R.O.N.A. API shutting down")


app = FastAPI(
    title="D.R.O.N.A. Advising API",
    version="0.1.0",
    description="Bias-aware, locally-grounded academic advising (local LLM only).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.api_cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    advisor = get_advisor()
    llm = getattr(advisor, "_comp", None)
    llm_ok = False
    try:
        if llm is not None:
            llm_ok = llm.llm.is_available()
        elif hasattr(advisor, "_llm"):
            llm_ok = advisor._llm.is_available()
    except Exception:
        llm_ok = False
    return HealthResponse(
        status="ok" if llm_ok else "degraded",
        llm_available=llm_ok,
        orchestrator=orchestrator_name(),
        vector_backend=settings.vector_backend,
    )


@app.get("/evaluation")
def evaluation() -> dict:
    """Real evaluation results for the dashboard Analytics page.

    Reads the artifacts written by notebook 05 (reports/evaluation_report.json)
    and notebook 04 (reports/sft_metrics.json). Returns {"available": False}
    until those runs exist, so the frontend can fall back gracefully.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    out: dict = {"available": False}

    report_path = root / "reports" / "evaluation_report.json"
    if report_path.exists():
        try:
            rep = json.loads(report_path.read_text(encoding="utf-8"))
            out["available"] = True
            out["generated"] = rep.get("generated")
            # {"ndcg@5": {"hybrid": 0.76, ...}, ...} -> rows per system
            abl = rep.get("c1_ablation", {})
            systems = sorted({s for col in abl.values() for s in col})
            out["c1_ablation"] = [
                {"method": s,
                 **{metric.replace("@", ""): round(col.get(s, 0.0), 3)
                    for metric, col in abl.items()}}
                for s in systems
            ]
            out["c2_per_type"] = [
                {"bias": name, "precision": round(v.get("precision", 0), 3),
                 "recall": round(v.get("recall", 0), 3), "f1": round(v.get("f1", 0), 3)}
                for name, v in rep.get("c2_per_type", {}).items()
            ]
            out["c2_macro_f1"] = rep.get("c2_macro_f1")
            out["c3_policies"] = [
                {"policy": name, **{k: round(float(x), 5) for k, x in v.items()}}
                for name, v in rep.get("c3_summary", {}).items()
            ]
            out["c4"] = rep.get("c4", {})
            out["verdict"] = rep.get("verdict", [])
        except Exception as exc:  # malformed report must not kill the API
            logger.warning(f"/evaluation: could not parse report: {exc}")

    sft_path = root / "reports" / "sft_metrics.json"
    if sft_path.exists():
        try:
            sft = json.loads(sft_path.read_text(encoding="utf-8"))
            out["llm"] = {
                "base_model": sft.get("base_model"),
                "base_eval_loss": sft.get("base_eval_loss"),
                "final_eval_loss": sft.get("final_eval_loss"),
                "curve": [{"step": h["step"], "eval_loss": round(h["eval_loss"], 4)}
                          for h in sft.get("log_history", []) if "eval_loss" in h],
            }
            out["available"] = True
        except Exception as exc:
            logger.warning(f"/evaluation: could not parse sft metrics: {exc}")

    return out


@app.post("/advise", response_model=AdvisingResponse)
async def advise(req: AdviseRequest, advisor: Advisor = Depends(get_advisor)) -> AdvisingResponse:
    """Run the full advising pipeline synchronously (off the event loop)."""
    query = req.to_query()
    return await run_in_threadpool(advisor.advise, query)


@app.websocket("/ws/advise")
async def ws_advise(websocket: WebSocket) -> None:
    """Stream advising progress node-by-node, then the final response.

    Protocol: client sends one AdviseRequest JSON; server streams events:
      {"event":"node",...} * N, then {"event":"result","response":{...}}.
    """
    await websocket.accept()
    advisor = get_advisor()
    try:
        payload = await websocket.receive_json()
        req = AdviseRequest.model_validate(payload)
        query = req.to_query()

        if hasattr(advisor, "stream"):
            async for event in stream_graph_events(advisor, query):
                await websocket.send_json(event)
        else:
            # Advisor can't stream - run once and emit a single result event.
            response = await run_in_threadpool(advisor.advise, query)
            await websocket.send_json(
                {"event": "result", "response": response.model_dump(mode="json")}
            )
    except WebSocketDisconnect:
        logger.info("Websocket client disconnected")
    except Exception as exc:
        logger.warning(f"Websocket advising error: {exc}")
        with contextlib.suppress(Exception):
            await websocket.send_json({"event": "error", "detail": str(exc)})
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
