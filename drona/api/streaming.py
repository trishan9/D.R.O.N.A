"""
Bridge a synchronous LangGraph stream into an async event stream.

The advising pipeline is CPU-bound and synchronous (embeddings, reranker, local
LLM). To stream progress over a websocket without blocking the event loop, we
run the graph's ``.stream()`` in a worker thread and forward each node update to
an asyncio.Queue the websocket drains.

Each yielded event is a small JSON-able dict:
  {"event": "node",   "node": "<name>"}            # a graph node just ran
  {"event": "result", "response": {...}}           # final AdvisingResponse
  {"event": "error",  "detail": "<msg>"}
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from typing import Any

from drona.contracts import AdvisingQuery

_SENTINEL = object()

# Human-readable labels for UI progress (keeps the frontend dumb).
_NODE_LABELS = {
    "detect_bias": "Checking for cognitive biases…",
    "retrieve": "Searching curriculum + Nepali job market…",
    "generate": "Composing a grounded, bias-aware answer…",
    "verify": "Verifying citations…",
    "format": "Finalising response…",
}


async def stream_graph_events(graph: Any, query: AdvisingQuery) -> AsyncIterator[dict]:
    """Yield streaming events for one advising request.

    Args:
        graph: An object exposing ``.stream(query) -> Iterator[dict]`` where each
            item is ``{node_name: state_delta}`` (the LangGraph stream shape).
        query: The advising query.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def worker() -> None:
        try:
            for chunk in graph.stream(query):
                loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
        except Exception as exc:  # pragma: no cover - defensive
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, (_SENTINEL, None))

    threading.Thread(target=worker, daemon=True).start()

    final_response = None
    while True:
        kind, payload = await queue.get()
        if kind is _SENTINEL:
            break
        if kind == "error":
            yield {"event": "error", "detail": payload}
            return
        # payload is {node_name: state_delta}
        for node_name, delta in payload.items():
            yield {
                "event": "node",
                "node": node_name,
                "label": _NODE_LABELS.get(node_name, node_name),
            }
            if isinstance(delta, dict) and delta.get("response") is not None:
                final_response = delta["response"]

    if final_response is not None:
        yield {"event": "result", "response": final_response.model_dump(mode="json")}
    else:
        yield {"event": "error", "detail": "Pipeline produced no response"}
