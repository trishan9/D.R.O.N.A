"""
Hugging Face transformers LLM backend for D.R.O.N.A. - the Ollama alternative.

Serves the advising LLM **directly from Hugging Face weights** (exactly like
the embedding models are served), including the fine-tuned LoRA adapter with
no GGUF conversion step. Same interface as ``llm_client.LLMClient``, selected
via ``LLM_BACKEND=transformers`` in ``.env``.

When to use which backend (honest guidance):

  | Situation | Best backend | Why |
  |---|---|---|
  | Student PC, CPU only | **ollama** (default) | llama.cpp's quantised CPU inference is several times faster than PyTorch on CPU |
  | Any CUDA GPU (Colab demo, RTX box) | **transformers** | full/4-bit precision (no GGUF quantisation loss), and the LoRA adapter loads directly - no merge/convert step |
  | Evaluating the fine-tune right after training | **transformers** | the adapter dir from notebook 04 is served as-is |

Both backends stay strictly local/open-source - no paid APIs (C4 invariant).

Config (settings / .env):
    LLM_BACKEND=transformers
    HF_MODEL=Qwen/Qwen3-4B-Instruct-2507     # base weights
    HF_ADAPTER_PATH=models/advising-lora     # loaded when the dir exists
    HF_LOAD_4BIT=true                        # GPU only; ignored on CPU
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from loguru import logger

from drona.advising.llm_client import _extract_json, _parse_pathways
from drona.contracts import (
    AdvisingQuery,
    BiasFlag,
    PathwayRecommendation,
    RetrievalCitation,
)
from drona.utils.settings import settings


class HFLocalClient:
    """Transformers-backed LLM client - drop-in for ``LLMClient``."""

    def __init__(
        self,
        model: str | None = None,
        adapter_path: str | Path | None = None,
        load_4bit: bool | None = None,
    ) -> None:
        self._model_name = model or settings.hf_model
        self._adapter_path = Path(adapter_path or settings.hf_adapter_path)
        self._load_4bit = settings.hf_load_4bit if load_4bit is None else load_4bit
        self._model: Any = None      # lazy
        self._tokenizer: Any = None  # lazy

    # ── Availability / loading ────────────────────────────────────────────────

    def is_available(self) -> bool:
        """True if torch + transformers are importable (weights load lazily)."""
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return True
        except ImportError as exc:
            logger.warning(f"transformers backend unavailable: {exc}")
            return False

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        use_cuda = torch.cuda.is_available()
        if not use_cuda:
            logger.warning(
                "transformers backend on CPU - expect slow generation; "
                "the ollama backend (GGUF/llama.cpp) is faster on CPU."
            )

        kwargs: dict[str, Any] = {"device_map": "auto" if use_cuda else None}
        if use_cuda and self._load_4bit:
            from transformers import BitsAndBytesConfig

            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
        elif use_cuda:
            kwargs["torch_dtype"] = torch.bfloat16

        has_adapter = (self._adapter_path / "adapter_config.json").exists()
        t0 = time.monotonic()
        if has_adapter:
            # Adapter dir references its base model; loads base + LoRA in one go.
            from peft import AutoPeftModelForCausalLM

            self._model = AutoPeftModelForCausalLM.from_pretrained(
                str(self._adapter_path), **kwargs
            )
            self._tokenizer = AutoTokenizer.from_pretrained(str(self._adapter_path))
            logger.info(
                f"HF backend: base + LoRA adapter loaded from {self._adapter_path} "
                f"in {time.monotonic() - t0:.1f}s"
            )
        else:
            self._model = AutoModelForCausalLM.from_pretrained(self._model_name, **kwargs)
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            logger.info(
                f"HF backend: {self._model_name} loaded (no adapter at "
                f"{self._adapter_path}) in {time.monotonic() - t0:.1f}s"
            )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._model.eval()

    # ── Generation (same contract as LLMClient.generate) ─────────────────────

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        query: AdvisingQuery,
        citations: list[RetrievalCitation],
        bias_flags: list[BiasFlag],
        max_retries: int = 2,
    ) -> tuple[list[PathwayRecommendation], str, bool, str | None]:
        """Call the local HF model and parse the structured JSON response."""
        try:
            self._ensure_model()
        except Exception as exc:
            return [], ("I'm sorry, I could not generate a response right now. "
                        "Please try again or speak with a human advisor."), True, str(exc)

        import torch

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        inputs = self._tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        ).to(self._model.device)

        do_sample = settings.llm_temperature > 0
        last_error: str | None = None
        for attempt in range(max_retries + 1):
            t0 = time.monotonic()
            try:
                with torch.no_grad():
                    out = self._model.generate(
                        inputs,
                        max_new_tokens=settings.llm_max_tokens,
                        do_sample=do_sample,
                        temperature=settings.llm_temperature if do_sample else None,
                        pad_token_id=self._tokenizer.pad_token_id,
                    )
                raw_text = self._tokenizer.decode(
                    out[0][inputs.shape[1]:], skip_special_tokens=True
                )
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                logger.debug(
                    f"HF [{self._model_name}] response in {elapsed_ms}ms "
                    f"({len(raw_text)} chars, attempt {attempt + 1})"
                )

                parsed = _extract_json(raw_text)
                if parsed is None:
                    last_error = (f"Could not extract JSON from HF output "
                                  f"(attempt {attempt + 1})")
                    logger.warning(last_error)
                    continue

                pathways = _parse_pathways(parsed.get("pathways", []), citations)
                speak_text = str(parsed.get("speak_text", ""))
                return pathways, speak_text, False, None

            except Exception as exc:
                last_error = f"HF generation failed: {exc}"
                logger.warning(last_error)

        return (
            [],
            "I'm sorry, I could not generate a response right now. "
            "Please try again or speak with a human advisor.",
            True,
            last_error,
        )
