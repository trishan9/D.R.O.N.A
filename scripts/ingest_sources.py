"""
Phase 1 data-source ingestion CLI for D.R.O.N.A.

Parses each external data source into DRONA contracts, writes a Parquet artifact
plus a data card (YAML + Markdown), and (optionally) indexes into the configured
vector backend. Every subcommand accepts explicit paths and has --help.

Examples:
    python scripts/ingest_sources.py esco --csv-dir data/raw/esco
    python scripts/ingest_sources.py bls  --oews data/raw/oews_national_M2025.xlsx --onet-parquet data/processed/onet_career_pathways.parquet
    python scripts/ingest_sources.py nlfs --pdf data/raw/nlfs_2017_18.pdf
    python scripts/ingest_sources.py synthetic --jobs data/cards/job_postings_nepal.json --n 2
    python scripts/ingest_sources.py --help
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from drona.contracts import CareerPathway, JobPosting  # noqa: E402
from drona.data_pipeline import bls, esco, nlfs, synthetic  # noqa: E402
from drona.utils.logging import setup_logging  # noqa: E402
from drona.utils.settings import settings  # noqa: E402

app = typer.Typer(help=__doc__, no_args_is_help=True)


def _save_json(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.success(f"Wrote {len(records)} records → {path}")


@app.command("esco")
def esco_cmd(
    csv_dir: Path = typer.Option(..., "--csv-dir", help="Unzipped ESCO CSV distribution dir"),
    out: Path = typer.Option(Path("data/processed/esco_career_pathways.json"), "--out"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Ingest ESCO v1.2.1 ICT occupations from the CSV bulk distribution."""
    setup_logging(level=log_level, log_file=settings.log_file)
    pathways = esco.parse_csv_dir(csv_dir)
    _save_json([p.model_dump(mode="json") for p in pathways], out)
    esco.build_data_card(pathways, out)


@app.command("bls")
def bls_cmd(
    oews: Path = typer.Option(..., "--oews", help="BLS OEWS national file (.xlsx/.csv)"),
    onet_parquet: Path = typer.Option(
        None, "--onet-parquet", help="O*NET parquet to enrich with wage bands"
    ),
    out: Path = typer.Option(Path("data/processed/bls_oews_wages.json"), "--out"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Ingest BLS OEWS wages; optionally enrich an O*NET pathways parquet."""
    setup_logging(level=log_level, log_file=settings.log_file)
    wages = bls.load_wage_table(oews)
    _save_json([{"soc": k, "pct10": v[0], "pct90": v[1]} for k, v in wages.items()], out)
    bls.build_data_card(wages, out)
    if onet_parquet and onet_parquet.exists():
        import pandas as pd

        df = pd.read_parquet(onet_parquet)
        pathways = [CareerPathway.model_validate(r) for r in df.to_dict(orient="records")]
        enriched = bls.enrich_pathways(pathways, wages)
        _save_json(
            [p.model_dump(mode="json") for p in enriched],
            onet_parquet.with_name("onet_career_pathways_enriched.json"),
        )


@app.command("nlfs")
def nlfs_cmd(
    pdf: Path = typer.Option(None, "--pdf", help="NLFS PDF path; downloads if omitted"),
    out: Path = typer.Option(Path("data/processed/nlfs_labour_snippets.json"), "--out"),
    max_pages: int = typer.Option(None, "--max-pages", help="Cap pages (debug)"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Ingest NLFS 2017/18 labour-market snippets from the PDF."""
    setup_logging(level=log_level, log_file=settings.log_file)
    pdf_path = pdf or nlfs.download_pdf()
    snippets = nlfs.extract_snippets(pdf_path, max_pages=max_pages)
    _save_json([s.model_dump(mode="json") for s in snippets], out)
    nlfs.build_data_card(snippets, out)


@app.command("synthetic")
def synthetic_cmd(
    jobs: Path = typer.Option(..., "--jobs", help="JSON of real anchor JobPostings"),
    n: int = typer.Option(2, "--n", help="Synthetic variants per anchor"),
    out: Path = typer.Option(Path("data/processed/synthetic_job_postings.json"), "--out"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Generate labelled synthetic postings anchored to real ones (rule-based)."""
    setup_logging(level=log_level, log_file=settings.log_file)
    raw = json.loads(jobs.read_text(encoding="utf-8"))
    anchors = [JobPosting.model_validate(r) for r in raw]
    postings = synthetic.generate_from_anchors(anchors, n_per_anchor=n)
    _save_json([p.model_dump(mode="json") for p in postings], out)
    synthetic.build_data_card(postings, out)


if __name__ == "__main__":
    app()
