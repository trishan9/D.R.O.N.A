"""
D.R.O.N.A. FastAPI application.

Endpoints:
  GET  /health        - liveness + LLM/orchestrator/backend status
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
