"""
Format advising Q&A pairs into supervised fine-tuning (SFT) examples.

The fine-tune must teach the model to produce the SAME prompt→JSON behaviour the
live engine expects, so we reconstruct each example with the production
``prompt_builder`` (system + user with retrieval context) and use the gold JSON
as the assistant target. This keeps train-time and inference-time prompts
identical - critical for the LoRA adapter to transfer (Zhao et al. 2023 style
behaviour-cloning rationale, applied to text).

Outputs are JSONL with both:
  - "messages": chat format (system/user/assistant) for trl SFTTrainer chat mode
  - "text":     a single rendered string for plain causal-LM SFT
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from loguru import logger

from drona.advising.prompt_builder import build_prompt
from drona.contracts import AdvisingQuery, BiasFlag
from drona.finetune.qa_schema import AdvisingQAPair


def _bias_flags(pair: AdvisingQAPair) -> list[BiasFlag]:
    if not pair.bias_type:
        return []
    return [
        BiasFlag(
            bias_type=pair.bias_type,  # type: ignore[arg-type]
            detected_signal="(synthetic training example)",
            mitigation_applied="bias-aware framing applied in gold answer",
        )
    ]


def to_chat_example(pair: AdvisingQAPair) -> dict:
    """Render one Q&A pair into an SFT example (messages + text)."""
    n_pathways = max(1, len(pair.target_response.get("pathways", [])) or 3)
    query = AdvisingQuery(
        query_id=pair.id,
        query_text=pair.question,
        profile=pair.profile,
        max_pathways=n_pathways,
    )
    system, user = build_prompt(query, pair.context_citations, _bias_flags(pair))
    assistant = json.dumps(pair.target_response, ensure_ascii=False)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]
    text = f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n{assistant}"
    return {
        "id": pair.id,
        "bias_type": pair.bias_type,
        "is_synthetic": pair.is_synthetic,
        "is_gold": pair.is_gold,
        "messages": messages,
        "text": text,
    }


def build_sft_dataset(pairs: list[AdvisingQAPair]) -> list[dict]:
    """Convert pairs into SFT examples, de-duplicating by question.

    The template generator can emit the same question more than once when the
    target count exceeds the achievable question diversity; training on exact
    duplicates just risks overfitting, so we keep the first occurrence of each
    question (its grounded gold answer) and drop the rest.
    """
    seen: set[str] = set()
    examples: list[dict] = []
    for p in pairs:
        q = (p.question or "").strip().lower()
        if q in seen:
            continue
        seen.add(q)
        examples.append(to_chat_example(p))
    return examples


def train_val_split(
    examples: list[dict], val_fraction: float = 0.1, seed: int = 230352
) -> tuple[list[dict], list[dict]]:
    """Deterministic shuffle + split into (train, val)."""
    if not 0.0 < val_fraction < 1.0:
        raise ValueError("val_fraction must be in (0, 1)")
    shuffled = examples[:]
    random.Random(seed).shuffle(shuffled)
    n_val = max(1, int(len(shuffled) * val_fraction))
    return shuffled[n_val:], shuffled[:n_val]


def export_jsonl(examples: list[dict], path: Path) -> None:
    """Write examples to JSONL (one JSON object per line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    logger.success(f"Wrote {len(examples)} SFT examples → {path}")


def load_jsonl(path: Path) -> list[dict]:
    """Read a JSONL SFT file."""
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
