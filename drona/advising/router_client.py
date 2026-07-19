"""
Language-routing LLM client for D.R.O.N.A.'s bilingual advising.

Routes each advising request to the right model by the query's language, while
retrieval stays shared - so an English and a Nepali student get answers grounded
in the *same* Softwarica curriculum, each in their own language:

    English query  -> the primary brain (fine-tuned Qwen3-4B; transformers or
                      Ollama per LLM_BACKEND) - keeps the Softwarica + bias fine-tune
    Nepali query   -> Himalaya Gemma (Nepali-specialised) served via Ollama,
                      grounded by the retrieved English context

The language for the turn is resolved deterministically from the same inputs the
prompt builder uses (settings.advisor_language + the query text), so the prompt's
"answer in Nepali" instruction and the model that receives it never disagree.

Graceful degradation: if the Nepali model is not installed/available, the request
falls back to the primary model (Qwen3 is multilingual and can still answer in
Nepali when the prompt asks it to), so a missing Ollama model degrades quality
rather than breaking the robot.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from drona.advising.llm_client import LLMClient
from drona.contracts import AdvisingQuery, BiasFlag, PathwayRecommendation, RetrievalCitation
from drona.utils.language import resolve_language
from drona.utils.settings import settings


def _make_primary_client():
    """The English/primary backend, per LLM_BACKEND (transformers or ollama)."""
    if settings.llm_backend == "transformers":
        from drona.advising.hf_client import HFLocalClient

        return HFLocalClient()
    return LLMClient()


class LanguageRoutingClient:
    """Dispatches generate() to a per-language backend. Same interface as the
    individual clients, so it is a drop-in for AdvisingEngine's LLM client."""

    def __init__(self, primary: Any = None, nepali: Any = None) -> None:
        self._primary = primary or _make_primary_client()
        # Lazily built the first time a Nepali query actually arrives, so an
        # English-only deployment never touches Ollama/Gemma.
        self._nepali = nepali
        self._nepali_tried = nepali is not None

    # ── Client selection ────────────────────────────────────────────────────────

    def _nepali_client(self):
        if not self._nepali_tried:
            self._nepali_tried = True
            try:
                self._nepali = LLMClient(model=settings.nepali_ollama_model)
                logger.info(f"Nepali brain: {settings.nepali_ollama_model}")
            except Exception as exc:  # noqa: BLE001 - fall back to primary
                logger.warning(f"Nepali brain unavailable ({exc}); using primary model")
                self._nepali = None
        return self._nepali

    def client_for_language(self, lang: str):
        if lang != "ne":
            return self._primary, "en"
        ne = self._nepali_client()
        if ne is not None and ne.is_available():
            return ne, "ne"
        logger.warning(
            "Nepali model not available - falling back to the primary "
            "(multilingual) model, still prompted to answer in Nepali."
        )
        return self._primary, "ne-fallback"

    # ── Cross-lingual retrieval ─────────────────────────────────────────────────

    def translate_to_english(self, text: str) -> str:
        """Translate a Nepali query to English for retrieval.

        The curriculum is embedded with an English model, so a pure-Nepali query
        retrieves poorly; translating it to English first fixes grounding while
        the answer is still generated in Nepali. Best-effort: returns "" if no
        model can translate, so the engine falls back to the raw query (which
        still works for the code-switched Nepali students usually type).
        """
        prompt = (
            "Translate this Nepali student question into a concise English search "
            "query. Keep technical terms and proper nouns. Output ONLY the English "
            f"translation, nothing else.\n\n{text}"
        )
        # Prefer the Nepali model (bilingual NE<->EN); fall back to the primary.
        for client in (self._nepali_client(), self._primary):
            if client is not None and hasattr(client, "complete"):
                try:
                    if not client.is_available():
                        continue
                    out = client.complete(prompt, max_tokens=80).strip().strip('"')
                    if out:
                        return out
                except Exception:  # noqa: BLE001 - try the next client
                    continue
        return ""

    # ── LLMClient interface ─────────────────────────────────────────────────────

    def is_available(self) -> bool:
        # Available if EITHER backend can serve: an English-only box has the
        # primary; a Nepali-only box (e.g. only the Gemma model pulled) has the
        # Nepali client. Short-circuits on the primary so English-only never
        # eagerly creates the Nepali client.
        if self._primary.is_available():
            return True
        ne = self._nepali_client()
        return ne is not None and ne.is_available()

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        query: AdvisingQuery,
        citations: list[RetrievalCitation],
        bias_flags: list[BiasFlag],
        max_retries: int = 2,
    ) -> tuple[list[PathwayRecommendation], str, bool, str | None]:
        lang = resolve_language(settings.advisor_language, query.query_text)
        client, route = self.client_for_language(lang)
        logger.info(f"Advising language={lang} route={route}")
        return client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            query=query,
            citations=citations,
            bias_flags=bias_flags,
            max_retries=max_retries,
        )
