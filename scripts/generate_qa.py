"""
Generate the synthetic advising Q&A dataset for the LoRA fine-tune (Phase 3).

Loads real career-pathway anchors (O*NET/ESCO parquet/JSON), optional curriculum
modules and Nepali job postings, generates ~N grounded Q&A pairs, writes:
  - the full SFT dataset (train/val JSONL),
  - a stratified gold-review file (~50 pairs) for human approval,
  - the model card stub.

Examples:
    python scripts/generate_qa.py --pathways data/processed/onet_career_pathways.json --n 500
    python scripts/generate_qa.py --help
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from drona.contracts import CareerPathway, CurriculumModule, JobPosting  # noqa: E402
from drona.finetune import dataset as ds  # noqa: E402
from drona.finetune import gold_set, qa_generator  # noqa: E402
from drona.finetune.lora_config import DronaLoraConfig  # noqa: E402
from drona.finetune.model_card import build_advising_lora_card  # noqa: E402
from drona.utils.logging import setup_logging  # noqa: E402
from drona.utils.settings import settings  # noqa: E402

app = typer.Typer(help=__doc__)


def _load(path: Path | None, model) -> list:
    if not path or not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):  # tolerate {"items":[...]} wrappers
        raw = raw.get("items") or raw.get("records") or []
    out = []
    for r in raw:
        try:
            out.append(model.model_validate(r))
        except Exception as e:
            logger.warning(f"skip invalid {model.__name__}: {e}")
    return out


@app.command()
def main(
    pathways: Path = typer.Option(..., "--pathways", help="JSON of CareerPathway anchors"),
    modules: Path = typer.Option(None, "--modules", help="JSON of CurriculumModule"),
    jobs: Path = typer.Option(None, "--jobs", help="JSON of JobPosting"),
    n: int = typer.Option(500, "--n", help="Number of Q&A pairs to generate"),
    out_dir: Path = typer.Option(Path("data/finetune"), "--out-dir"),
    gold_n: int = typer.Option(50, "--gold-n", help="Gold-review sample size"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level, log_file=settings.log_file)
    out_dir.mkdir(parents=True, exist_ok=True)

    pw = _load(pathways, CareerPathway)
    if not pw:
        raise typer.BadParameter(f"No valid CareerPathway anchors in {pathways}")
    mods = _load(modules, CurriculumModule)
    jbs = _load(jobs, JobPosting)
    logger.info(f"Anchors: {len(pw)} pathways, {len(mods)} modules, {len(jbs)} postings")

    pairs = qa_generator.generate_qa_pairs(pw, mods, jbs, target_count=n)

    # Full SFT dataset
    examples = ds.build_sft_dataset(pairs)
    train, val = ds.train_val_split(examples)
    ds.export_jsonl(train, out_dir / "sft_train.jsonl")
    ds.export_jsonl(val, out_dir / "sft_val.jsonl")

    # Gold review file
    candidates = gold_set.select_gold_candidates(pairs, n=gold_n)
    gold_set.write_review_file(candidates, out_dir / "gold_review.jsonl")

    # Model card stub
    cfg = DronaLoraConfig()
    card = build_advising_lora_card(
        hyperparameters={
            "r": cfg.r,
            "lora_alpha": cfg.lora_alpha,
            "epochs": cfg.num_train_epochs,
            "effective_batch_size": cfg.effective_batch_size,
            "learning_rate": cfg.learning_rate,
            "max_seq_length": cfg.max_seq_length,
            "quantization": cfg.bnb_4bit_quant_type + " 4-bit",
        },
        num_train=len(train),
        num_gold=len(candidates),
    )
    card.write(Path(cfg.output_dir) / "model_card.md")
    logger.success(
        f"Done. SFT train={len(train)}, val={len(val)}, gold_review={len(candidates)}. "
        f"Model card → {cfg.output_dir}/model_card.md"
    )


if __name__ == "__main__":
    app()
