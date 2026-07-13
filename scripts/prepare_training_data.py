"""One command to prepare EVERY training input for D.R.O.N.A.

Runs the whole data-prep chain so the Colab/Kaggle training notebooks (and the
local pipeline) have everything they need:

  1. placeholder curriculum + Nepali jobs        (make_placeholder_data)
  2. real O*NET 30.3 download + parse  -> parquet (network)
  3. export pathway + curriculum JSON anchors
  4. load manual jobs                  -> data/processed/manual_postings.json
  5. synthetic advising Q&A / SFT data -> data/finetune/  (LoRA input, nb09)
  6. gesture demonstrations            -> data/demonstrations/  (ACT/Diffusion, nb07/08)

Idempotent and safe to re-run. Use the --skip-* flags to avoid re-doing slow
steps (e.g. --skip-onet once the zip is cached).

Usage:
    python scripts/prepare_training_data.py
    python scripts/prepare_training_data.py --skip-onet
    python scripts/prepare_training_data.py --qa-n 800 --episodes 30
"""

from __future__ import annotations

import ast
import json
import math
import sys
from pathlib import Path

import typer

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = typer.Typer(help=__doc__)


@app.command()
def main(
    skip_placeholder: bool = typer.Option(False, "--skip-placeholder", help="Don't (re)write dummy data"),
    skip_onet: bool = typer.Option(False, "--skip-onet", help="Skip O*NET download/parse (use cached parquet)"),
    skip_ingest: bool = typer.Option(True, "--skip-ingest/--ingest", help="Also build ChromaDB (slow; not needed for training)"),
    qa_n: int = typer.Option(500, "--qa-n", help="Number of synthetic Q&A pairs (LoRA)"),
    episodes: int = typer.Option(25, "--episodes", help="Demonstration episodes per gesture (ACT/Diffusion)"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    from drona.utils.logging import setup_logging
    from drona.utils.settings import settings
    setup_logging(level=log_level, log_file=settings.log_file)
    settings.ensure_dirs()

    proc = ROOT / "data" / "processed"
    proc.mkdir(parents=True, exist_ok=True)

    # ── 1. placeholder data ──────────────────────────────────────────────────
    if not skip_placeholder:
        typer.secho("\n[1/6] placeholder curriculum + jobs", bold=True)
        import make_placeholder_data as mpd
        mpd._write_curriculum()
        mpd._write_jobs()
    else:
        typer.secho("\n[1/6] placeholder data - skipped", fg=typer.colors.YELLOW)

    # ── 2. O*NET ─────────────────────────────────────────────────────────────
    typer.secho("\n[2/6] O*NET 30.3 career pathways", bold=True)
    parquet = proc / "onet_career_pathways.parquet"
    if skip_onet and parquet.exists():
        typer.echo("  using cached parquet")
    else:
        from drona.data_pipeline import onet
        zip_path = onet.download_zip()
        pathways = onet.parse(zip_path)
        onet.save_parquet(pathways, parquet)
        onet.build_data_card(zip_path, pathways, parquet)
        typer.echo(f"  parsed {len(pathways)} pathways")

    # ── 3. export JSON anchors ───────────────────────────────────────────────
    typer.secho("\n[3/6] export pathway + curriculum JSON anchors", bold=True)
    import pandas as pd

    from drona.contracts import CareerPathway
    from drona.data_pipeline import curriculum
    df = pd.read_parquet(parquet)
    pathways = []
    for _, row in df.iterrows():
        d = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.to_dict().items()}
        for lf in ("typical_skills", "typical_education", "related_softwarica_modules", "sample_employers_nepal"):
            v = d.get(lf, "[]")
            if isinstance(v, str):
                d[lf] = ast.literal_eval(v)
        for tf in ("local_salary_range_npr", "international_salary_range_usd"):
            v = d.get(tf)
            d[tf] = ast.literal_eval(v) if isinstance(v, str) and v not in ("None", "nan") else None
        pathways.append(CareerPathway.model_validate(d))
    # BLS OEWS wage enrichment - applies automatically when the table is present
    # (data/raw/bls/; notebook 01 can auto-download it). Fills the USD salary
    # bands that are otherwise honestly empty.
    bls_dir = ROOT / "data" / "raw" / "bls"
    bls_files = ([p for p in bls_dir.rglob("*") if p.suffix in (".xlsx", ".xls", ".csv")]
                 if bls_dir.exists() else [])
    if bls_files:
        from drona.data_pipeline import bls
        wages = bls.load_wage_table(bls_files[0])
        pathways = bls.enrich_pathways(pathways, wages)
        enriched = sum(1 for p in pathways if p.international_salary_range_usd)
        typer.echo(f"  BLS OEWS: USD wage bands attached to {enriched}/{len(pathways)} pathways")

    (proc / "onet_career_pathways.json").write_text(
        json.dumps([p.model_dump(mode="json") for p in pathways], ensure_ascii=False, indent=2), encoding="utf-8")
    mods = curriculum.parse_directory(ROOT / "data" / "raw" / "curriculum")
    (proc / "curriculum_modules.json").write_text(
        json.dumps([m.model_dump(mode="json") for m in mods], ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"  {len(pathways)} pathways + {len(mods)} modules")

    # ── 4. manual jobs -> processed ──────────────────────────────────────────
    typer.secho("\n[4/6] load manual job postings", bold=True)
    from drona.data_pipeline.scrapers import manual_loader
    posts = manual_loader.load_all_manual(settings.data_manual_dir)
    (proc / "manual_postings.json").write_text(
        json.dumps([json.loads(p.model_dump_json()) for p in posts], ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"  {len(posts)} postings")

    # ── 5. SFT dataset (LoRA) ────────────────────────────────────────────────
    typer.secho("\n[5/6] synthetic Q&A / SFT dataset (LoRA, nb09)", bold=True)
    from drona.finetune import dataset as ds
    from drona.finetune import gold_set, qa_generator
    pairs = qa_generator.generate_qa_pairs(pathways, mods, posts, target_count=qa_n)
    examples = ds.build_sft_dataset(pairs)
    train, val = ds.train_val_split(examples)
    fine = ROOT / "data" / "finetune"
    fine.mkdir(parents=True, exist_ok=True)
    ds.export_jsonl(train, fine / "sft_train.jsonl")
    ds.export_jsonl(val, fine / "sft_val.jsonl")
    gold_set.write_review_file(gold_set.select_gold_candidates(pairs, n=50), fine / "gold_review.jsonl")
    typer.echo(f"  SFT train={len(train)} val={len(val)}")

    # ── 6. demonstrations (ACT/Diffusion) ────────────────────────────────────
    typer.secho("\n[6/6] gesture demonstrations (ACT/Diffusion, nb07/08)", bold=True)
    import numpy as np

    from drona.interaction.demonstration import (
        GESTURE_KEYFRAMES,
        DemonstrationDataset,
        DemonstrationEpisode,
        interpolate_keyframes,
    )
    rng = np.random.default_rng(42)
    dset = DemonstrationDataset(name="drona_gestures")
    idx = 0
    for gesture, keyframes in GESTURE_KEYFRAMES.items():
        for _ in range(episodes):
            traj = interpolate_keyframes(keyframes, dt=0.05)
            ep = DemonstrationEpisode(episode_index=idx, gesture_label=gesture,
                                      metadata={"source": "keyframe+jitter"})
            for i, (q, _t) in enumerate(traj):
                nq = traj[min(i + 1, len(traj) - 1)][0]
                obs = np.array(q, dtype=np.float32) + rng.normal(0, 0.02, size=len(q)).astype(np.float32)
                ep.add_frame(obs=obs, action=np.array(nq, dtype=np.float32), timestamp=i * 0.05)
            dset.add_episode(ep)
            idx += 1
    demo_dir = ROOT / "data" / "demonstrations"
    demo_dir.mkdir(parents=True, exist_ok=True)
    dset.save_jsonl(demo_dir / "demonstrations.jsonl")
    typer.echo(f"  {dset.total_frames} frames / {len(dset.episodes)} episodes")

    # ── optional ChromaDB ────────────────────────────────────────────────────
    if not skip_ingest:
        typer.secho("\n[+] building ChromaDB (for retrieval/advising)", bold=True)
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts" / "ingest_data.py")], check=False)

    typer.secho("\nAll training inputs ready:", fg=typer.colors.GREEN, bold=True)
    typer.echo("  LoRA (nb09)         : data/finetune/sft_train.jsonl, sft_val.jsonl")
    typer.echo("  ACT/Diffusion (07/08): data/demonstrations/demonstrations.jsonl")
    typer.echo("  retrieval anchors    : data/processed/*.json (+ parquet)")


if __name__ == "__main__":
    app()
