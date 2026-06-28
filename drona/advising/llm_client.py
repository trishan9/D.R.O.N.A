"""
Ollama LLM client for D.R.O.N.A.

Wraps the Ollama Python SDK with:
  - Structured JSON response parsing (the model outputs JSON; we validate it)
  - Automatic retry on parse failures (malformed JSON, field missing)
  - Hard timeout so advising latency stays bounded
  - Model availability check at startup
  - Graceful fallback: if Ollama is unreachable, return a refusal response
    rather than crashing the advising session

Model default: qwen2.5:3b-instruct-q4_K_M (3B, 4-bit). Chosen as primary for
  speed on modest hardware, robustness to typos/spelling, and strong multilingual
  (Nepali / code-switch) handling. Fallback: phi3.5:3.8b-mini-instruct-q4_K_M.
  Both run locally via Ollama (no API cost). Change via OLLAMA_MODEL in .env.
  The model is kept warm between requests (settings.ollama_keep_alive) and
  generation is bounded (settings.llm_max_tokens) so only the first call is slow.

Parsing strategy:
  The LLM is instructed to return a bare JSON object. We attempt json.loads()
  first; if that fails we try to extract the first {...} block from the response
  (handles models that add preamble text despite instructions).
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from loguru import logger

from drona.contracts import (
    AdvisingQuery,
    BiasFlag,
    PathwayRecommendation,
    RetrievalCitation,
)
from drona.utils.settings import settings

# ── Raw response schema (LLM output before full AdvisingResponse assembly) ────

def _parse_pathways(
    raw_pathways: list[dict[str, Any]],
    citations: list[RetrievalCitation],
) -> list[PathwayRecommendation]:
    """Convert raw pathway dicts from the LLM into PathwayRecommendation objects.

    Citation references in the LLM output are integers (1-based index into the
    citations list). We resolve them back to RetrievalCitation objects here.
    """
    result: list[PathwayRecommendation] = []
    for raw in raw_pathways:
        # Resolve citation indices to objects
        cit_indices: list[int] = raw.get("citations", [])
        resolved: list[RetrievalCitation] = []
        for idx in cit_indices:
            if isinstance(idx, int) and 1 <= idx <= len(citations):
                resolved.append(citations[idx - 1])

        try:
            conf = raw.get("confidence", "medium")
            if conf not in ("low", "medium", "high"):
                conf = "medium"
            pr = PathwayRecommendation(
                pathway_title=str(raw.get("pathway_title", "Unnamed pathway")),
                rationale=str(raw.get("rationale", "")),
                matched_softwarica_modules=raw.get("matched_softwarica_modules", []),
                local_market_evidence=raw.get("local_market_evidence") or None,
                international_context=raw.get("international_context") or None,
                next_concrete_steps=raw.get("next_concrete_steps", []),
                citations=resolved,
                confidence=conf,  # type: ignore[arg-type]
            )
            result.append(pr)
        except Exception as exc:
            logger.warning(f"Skipping malformed pathway from LLM: {exc}")
    return result


def _extract_json(text: str) -> dict[str, Any] | None:
    """Try json.loads; fall back to extracting first {...} block."""
    text = text.strip()
    try:
        return json.loads(text)  # type: ignore[return-value]
    except json.JSONDecodeError:
        pass
    # Find first {...} block (handles preamble text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))  # type: ignore[return-value]
        except json.JSONDecodeError:
            pass
    return None


# ── LLM client ────────────────────────────────────────────────────────────────

class LLMClient:
    """Ollama-backed LLM client for structured advising responses."""

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        fallback_model: str | None = None,
    ) -> None:
        self._model = model or settings.ollama_model
        # Multilingual fallback (Qwen2.5-3B) — still LOCAL, no API cost. Tried
        # when the primary model is unavailable or exhausts its retries, which
        # also helps for Nepali/code-switched queries (proposal Phase 2 seam).
        self._fallback_model = fallback_model or settings.ollama_fallback_model
        self._host = host or settings.ollama_host
        self._client: Any = None  # lazy import

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        try:
            import ollama
            self._client = ollama.Client(host=self._host)
        except ImportError as exc:
            raise RuntimeError(
                "ollama package not installed. Run: pip install ollama"
            ) from exc

    def _loaded_model_names(self) -> list[str]:
        self._ensure_client()
        models = self._client.list()
        return [m.model for m in (models.models or [])]

    def _model_present(self, model: str, names: list[str]) -> bool:
        base = model.split(":")[0]
        return any(n.startswith(base) for n in names)

    def is_available(self) -> bool:
        """Return True if Ollama is reachable and the primary OR fallback model is loaded."""
        try:
            names = self._loaded_model_names()
            return self._model_present(self._model, names) or self._model_present(
                self._fallback_model, names
            )
        except Exception as exc:
            logger.warning(f"Ollama availability check failed: {exc}")
            return False

    def _available_models(self) -> list[str]:
        """Ordered list of usable models: primary first, then fallback if loaded."""
        try:
            names = self._loaded_model_names()
        except Exception:
            return [self._model]
        usable = []
        if self._model_present(self._model, names):
            usable.append(self._model)
        if self._fallback_model and self._model_present(self._fallback_model, names):
            usable.append(self._fallback_model)
        return usable or [self._model]

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        query: AdvisingQuery,
        citations: list[RetrievalCitation],
        bias_flags: list[BiasFlag],
        max_retries: int = 2,
    ) -> tuple[list[PathwayRecommendation], str, bool, str | None]:
        """Call the LLM and parse the structured response.

        Returns:
            (pathways, speak_text, refusal, refusal_reason)
        """
        self._ensure_client()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: str | None = None
        # Try each usable model in order (primary → Qwen fallback). Each model
        # gets max_retries+1 attempts to emit parseable JSON.
        for model in self._available_models():
            for attempt in range(max_retries + 1):
                t0 = time.monotonic()
                try:
                    response = self._client.chat(
                        model=model,
                        messages=messages,
                        # keep_alive holds the model in memory between requests
                        # so only the FIRST query pays the cold-load cost.
                        keep_alive=settings.ollama_keep_alive,
                        options={
                            "temperature": settings.llm_temperature,
                            "num_ctx": settings.ollama_num_ctx,
                            "num_predict": settings.llm_max_tokens,
                        },
                    )
                    elapsed_ms = int((time.monotonic() - t0) * 1000)
                    raw_text: str = response.message.content or ""
                    logger.debug(
                        f"LLM [{model}] response in {elapsed_ms}ms "
                        f"({len(raw_text)} chars, attempt {attempt + 1})"
                    )

                    parsed = _extract_json(raw_text)
                    if parsed is None:
                        last_error = (
                            f"Could not extract JSON from {model} output "
                            f"(attempt {attempt + 1})"
                        )
                        logger.warning(last_error)
                        continue

                    pathways = _parse_pathways(parsed.get("pathways", []), citations)
                    speak_text = str(parsed.get("speak_text", ""))
                    return pathways, speak_text, False, None

                except Exception as exc:
                    elapsed_ms = int((time.monotonic() - t0) * 1000)
                    last_error = f"LLM [{model}] call failed after {elapsed_ms}ms: {exc}"
                    logger.warning(last_error)
            logger.warning(f"Model {model} exhausted retries; trying next fallback if any")

        # All models + retries exhausted
        return (
            [],
            "I'm sorry, I could not generate a response right now. "
            "Please try again or speak with a human advisor.",
            True,
            last_error,
        )
