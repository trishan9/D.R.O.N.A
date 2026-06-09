"""
Gold-set curation for the LoRA fine-tune (Phase 3).

We can't hand-review 500 synthetic pairs, but the proposal calls for a
human-reviewed gold subset (~50). This module selects a STRATIFIED sample
(balanced across the seven bias classes) and writes a review file the human
edits: flip ``approved`` to true/false and optionally fix ``target_response``.
Approved pairs become the gold set used for evaluation (and optionally upweighted
in training).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from loguru import logger

from drona.finetune.qa_schema import AdvisingQAPair


def select_gold_candidates(
    pairs: list[AdvisingQAPair], n: int = 50, seed: int = 230352
) -> list[AdvisingQAPair]:
    """Stratified-sample ~n pairs balanced across bias classes.

    Picks round-robin from each bias bucket so all seven classes (including
    clean) are represented for review, even when generation is unbalanced.
    """
    import random

    rng = random.Random(seed)
    buckets: dict[str | None, list[AdvisingQAPair]] = defaultdict(list)
    for p in pairs:
        buckets[p.bias_type].append(p)
    for b in buckets.values():
        rng.shuffle(b)

    selected: list[AdvisingQAPair] = []
    classes = list(buckets.keys())
    while len(selected) < min(n, len(pairs)):
        progressed = False
        for cls in classes:
            if buckets[cls]:
                selected.append(buckets[cls].pop())
                progressed = True
                if len(selected) >= min(n, len(pairs)):
                    break
        if not progressed:
            break
    logger.info(f"Selected {len(selected)} gold candidates across {len(classes)} bias classes")
    return selected


def write_review_file(candidates: list[AdvisingQAPair], path: Path) -> None:
    """Write a human-review JSONL: edit `approved` + `reviewer_note` then reload."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in candidates:
            row = c.model_dump(mode="json")
            row["_REVIEW_INSTRUCTIONS"] = (
                "Set approved=true if the gold answer is correct, false to reject. "
                "You may edit target_response. Add reviewer_note."
            )
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    logger.success(f"Wrote {len(candidates)} pairs to review → {path}")


def load_reviewed(path: Path) -> list[AdvisingQAPair]:
    """Load a reviewed file, returning only approved gold pairs."""
    gold: list[AdvisingQAPair] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            row.pop("_REVIEW_INSTRUCTIONS", None)
            pair = AdvisingQAPair.model_validate(row)
            if pair.reviewed and pair.approved:
                gold.append(pair)
    logger.info(f"Loaded {len(gold)} approved gold pairs from {path}")
    return gold
