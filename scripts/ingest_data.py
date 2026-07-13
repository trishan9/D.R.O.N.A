"""
Ingest all processed data into ChromaDB dual-embedding collections.

Reads from data/processed/ (parquet files) and data/manual_collection/,
embeds with the configured models, and upserts into ChromaDB.

Run AFTER:
    python scripts/download_onet.py
    python scripts/scrape_jobs.py
    (and after adding curriculum files to data/raw/curriculum/)

Usage:
    python scripts/ingest_data.py
    python scripts/ingest_data.py --curriculum-dir data/raw/curriculum
    python scripts/ingest_data.py --skip-onet         # skip O*NET if not downloaded
    python scripts/ingest_data.py --stats-only        # just print collection counts
    python scripts/ingest_data.py --help
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from drona.contracts import CareerPathway, JobPosting
from drona.data_pipeline import curriculum
from drona.data_pipeline.ingest import Ingestor, print_stats
from drona.utils.logging import setup_logging
from drona.utils.settings import settings

app = typer.Typer(help=__doc__)


def _load_job_postings_json(path: Path) -> list[JobPosting]:
    """Load a processed JSON job postings file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    posts = []
    for entry in raw:
        try:
            posts.append(JobPosting.model_validate(entry))
        except Exception as e:
            logger.warning(f"  Skipping malformed posting: {e}")
    return posts


def _load_career_pathways_parquet(path: Path) -> list[CareerPathway]:
    """Load the O*NET parquet into CareerPathway objects."""
    import ast
    import math

    import pandas as pd

    df = pd.read_parquet(path)
    pathways = []
    for _, row in df.iterrows():
        try:
            # Parquet stores missing optionals (esco_code, salary tuples) as
            # float NaN. Coerce scalar NaN → None so Pydantic accepts them.
            d = {
                k: (None if isinstance(v, float) and math.isnan(v) else v)
                for k, v in row.to_dict().items()
            }
            # Parquet stores lists as strings due to our save_parquet() call
            for list_field in ("typical_skills", "typical_education",
                               "related_softwarica_modules", "sample_employers_nepal"):
                val = d.get(list_field, "[]")
                if isinstance(val, str):
                    d[list_field] = ast.literal_eval(val)
            for tuple_field in ("local_salary_range_npr", "international_salary_range_usd"):
                val = d.get(tuple_field)
                if isinstance(val, str) and val not in ("None", "nan"):
                    d[tuple_field] = ast.literal_eval(val)
                elif val in ("None", "nan") or val is None:
                    d[tuple_field] = None
            pathways.append(CareerPathway.model_validate(d))
        except Exception as e:
            logger.warning(f"  Skipping pathway row: {e}")
    return pathways


@app.command()
def main(
    curriculum_dir: Path = typer.Option(
        None, "--curriculum-dir",
        help="Directory of curriculum documents. Defaults to data/raw/curriculum/"
    ),
    processed_dir: Path = typer.Option(
        None, "--processed-dir",
        help="Directory with processed JSON/parquet files"
    ),
    skip_onet: bool = typer.Option(False, "--skip-onet", help="Skip O*NET pathways"),
    skip_jobs: bool = typer.Option(False, "--skip-jobs", help="Skip job postings"),
    skip_curriculum: bool = typer.Option(False, "--skip-curriculum", help="Skip curriculum"),
    stats_only: bool = typer.Option(False, "--stats-only", help="Print stats and exit"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level, log_file=settings.log_file)
    settings.ensure_dirs()

    if stats_only:
        print_stats()
        return

    proc = processed_dir or settings.data_processed_dir
    curr_dir = curriculum_dir or settings.data_raw_dir / "curriculum"

    with Ingestor() as ing:

        # ── Curriculum ──────────────────────────────────────────────────────
        if not skip_curriculum:
            if curr_dir.exists():
                modules = curriculum.parse_directory(curr_dir)
                if modules:
                    ing.add_curriculum_modules(modules)
                else:
                    logger.warning(
                        f"No curriculum modules parsed from {curr_dir}. "
                        "Add Softwarica module descriptor PDFs and re-run."
                    )
            else:
                logger.warning(
                    f"Curriculum directory not found: {curr_dir}. "
                    "Create it and add module PDFs, then re-run with --curriculum-dir."
                )

        # ── O*NET career pathways ────────────────────────────────────────
        if not skip_onet:
            onet_parquet = proc / "onet_career_pathways.parquet"
            if onet_parquet.exists():
                pathways = _load_career_pathways_parquet(onet_parquet)
                ing.add_career_pathways(pathways)
            else:
                logger.warning(
                    f"O*NET parquet not found at {onet_parquet}. "
                    "Run `python scripts/download_onet.py` first."
                )

        # ── Job postings ─────────────────────────────────────────────────
        if not skip_jobs:
            job_files = list(proc.glob("*_postings.json"))
            if not job_files:
                logger.warning(
                    f"No *_postings.json files found in {proc}. "
                    "Run `python scripts/scrape_jobs.py` first."
                )
            else:
                all_postings: list[JobPosting] = []
                for jf in sorted(job_files):
                    posts = _load_job_postings_json(jf)
                    logger.info(f"  Loaded {len(posts)} postings from {jf.name}")
                    all_postings.extend(posts)
                ing.add_job_postings(all_postings)

        s = ing.stats()

    logger.success(
        f"Ingestion complete.\n"
        f"  curriculum collection: {s['curriculum_docs']} documents\n"
        f"  career collection:     {s['career_docs']} documents"
    )


if __name__ == "__main__":
    app()
