"""
Remote advising client - lets a low-power robot use a GPU-served brain.

The robot (WSL2 dev box, Jetson, or a Raspberry Pi on the real hardware) does
not have the RAM or VRAM to run the retrieval stack (ChromaDB + a 2.3 GB
cross-encoder) *and* a 4B LLM. Instead it becomes a thin client: this class
POSTs the query to a D.R.O.N.A. advising API running on a GPU (the Colab T4
notebook, or any deployed server) and returns the identical AdvisingResponse
the local engine would have produced.

    robot (thin)  --HTTP-->  advising API on GPU  (retrieval + rerank + LLM)

Why this is the right split for a robot:
  - the heavy models live once, on hardware that can serve them fast;
  - the robot process stays small, so gestures and perception keep their CPU;
  - swapping the brain (bigger model, new adapter) needs no robot redeploy.

Failure policy - a robot must never crash or hang on a network fault:
  every error path returns a *refusal* AdvisingResponse (the same contract the
  engine uses when the LLM is down), so the orchestrator can hand off to a human
  advisor and the session continues. Nothing here raises.
"""

from __future__ import annotations

import time

from loguru import logger

from drona.contracts import AdvisingQuery, AdvisingResponse
from drona.utils.settings import settings

# A GPU-served response includes retrieval + rerank + generation, so allow
# generous headroom; the robot stays responsive because this runs off the
# gesture/perception threads.
_DEFAULT_TIMEOUT = 180.0
_HEALTH_TIMEOUT = 5.0


class RemoteAdvisor:
    """Calls a remote D.R.O.N.A. advising API instead of running the engine locally.

    Exposes ``advise()`` with the same signature as ``AdvisingEngine.advise()``,
    so it is a drop-in substitute anywhere the engine is used.

    Args:
        base_url: Root of the advising API, e.g. ``https://xyz.trycloudflare.com``.
            Defaults to ``settings.advisor_remote_url``.
        timeout: Per-request timeout in seconds for ``/advise``.
        retries: Extra attempts after the first failure (transient network/tunnel
            hiccups are common with tunnelled Colab endpoints).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        retries: int = 2,
    ) -> None:
        url = (base_url or settings.advisor_remote_url or "").strip().rstrip("/")
        if not url:
            raise ValueError(
                "RemoteAdvisor needs a base_url (or settings.advisor_remote_url). "
                "Set ADVISOR_REMOTE_URL to the API URL printed by notebook 07."
            )
        self.base_url = url
        self._timeout = timeout
        self._retries = max(0, retries)
        logger.info(f"RemoteAdvisor -> {self.base_url}")

    # ── Availability ───────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """True if the remote API answers /health. Never raises."""
        try:
            import httpx

            r = httpx.get(f"{self.base_url}/health", timeout=_HEALTH_TIMEOUT)
            return r.status_code == 200
        except Exception as exc:  # noqa: BLE001 - availability probe must not raise
            logger.warning(f"RemoteAdvisor health check failed: {exc}")
            return False

    # ── Advising ───────────────────────────────────────────────────────────────

    def advise(self, query: AdvisingQuery) -> AdvisingResponse:
        """POST the query to the remote API and return its AdvisingResponse.

        Returns a refusal response (never raises) if the remote is unreachable
        or replies with something unparseable.
        """
        t0 = time.monotonic()
        payload = _query_to_payload(query)

        last_error = "unknown error"
        for attempt in range(self._retries + 1):
            try:
                import httpx

                r = httpx.post(
                    f"{self.base_url}/advise", json=payload, timeout=self._timeout
                )
                if r.status_code != 200:
                    last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                    logger.warning(f"RemoteAdvisor attempt {attempt + 1}: {last_error}")
                    continue

                response = AdvisingResponse.model_validate(r.json())
                elapsed = int((time.monotonic() - t0) * 1000)
                logger.info(
                    f"RemoteAdvisor [{query.query_id[:8]}] {elapsed}ms - "
                    f"{len(response.pathways)} pathways, "
                    f"{len(response.bias_flags)} bias flags"
                )
                return response

            except Exception as exc:  # noqa: BLE001 - robot must degrade, not crash
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(f"RemoteAdvisor attempt {attempt + 1} failed: {last_error}")
                if attempt < self._retries:
                    time.sleep(1.5 * (attempt + 1))  # brief linear backoff

        elapsed = int((time.monotonic() - t0) * 1000)
        logger.error(f"RemoteAdvisor unreachable after {self._retries + 1} attempts")
        return _refusal(
            query,
            reason=(
                "The advising service is not reachable right now "
                f"({last_error}). Please speak with a human advisor."
            ),
            generation_time_ms=elapsed,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _query_to_payload(query: AdvisingQuery) -> dict:
    """Map an AdvisingQuery onto the API's AdviseRequest body."""
    p = query.profile
    return {
        "query_text": query.query_text,
        "session_id": p.session_id,
        "programme": p.programme,
        "year_of_study": p.year_of_study,
        "completed_modules": list(p.completed_modules),
        "declared_interests": list(p.declared_interests),
        "declared_skills": list(p.declared_skills),
        "self_assessed_skill_levels": dict(p.self_assessed_skill_levels),
        "aspirations": list(p.aspirations),
        "aspiration_geography": p.aspiration_geography,
        "goal": p.goal,
        "target_institutions": list(p.target_institutions),
        "timeline_years": p.timeline_years,
        "max_pathways": query.max_pathways,
    }


def _refusal(
    query: AdvisingQuery, reason: str, generation_time_ms: int
) -> AdvisingResponse:
    """Same refusal contract the local engine returns when generation is impossible."""
    return AdvisingResponse(
        query_id=query.query_id,
        summary=reason,
        pathways=[],
        bias_flags=[],
        refusal=True,
        refusal_reason=reason,
        speak_text=(
            "I'm sorry, I can't reach my advising service right now. "
            "Please speak with a human advisor."
        ),
        requires_human_followup=True,
        generation_time_ms=generation_time_ms,
    )


def make_advisor(remote_url: str | None = None):
    """Return a RemoteAdvisor if a remote URL is configured, else the local engine.

    This is the single decision point for "where does the brain run", used by the
    ROS2 advising node and any CLI tool:

        ADVISOR_REMOTE_URL set  -> thin client against a GPU-served API
        unset                   -> in-process AdvisingEngine (needs local models)
    """
    url = (remote_url or settings.advisor_remote_url or "").strip()
    if url:
        return RemoteAdvisor(url)
    from drona.advising.engine import AdvisingEngine

    logger.info("No ADVISOR_REMOTE_URL set - using the in-process AdvisingEngine")
    return AdvisingEngine()
