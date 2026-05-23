"""
Download and parse the O*NET 30.3 database.

Usage:
    python scripts/download_onet.py
    python scripts/download_onet.py --force          # re-download even if cached
    python scripts/download_onet.py --help

Outputs:
    data/raw/onet_30_3.zip                             ← raw zip (gitignored)
    data/processed/onet_career_pathways.parquet        ← clean data
    data/processed/onet_career_pathways_data_card.yaml ← provenance record
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from loguru import logger

# Ensure project root is on path when running scripts/ directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from drona.data_pipeline import onet
from drona.utils.logging import setup_logging
from drona.utils.settings import settings

app = typer.Typer(help=__doc__)


@app.command()
def main(
    force: bool = typer.Option(False, "--force", help="Re-download even if zip is cached"),
    out_dir: Path = typer.Option(None, "--out-dir", help="Output directory for parquet + card"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level, log_file=settings.log_file)
    settings.ensure_dirs()

    out = out_dir or settings.data_processed_dir
    out.mkdir(parents=True, exist_ok=True)

    zip_path = onet.download_zip(force=force)
    pathways = onet.parse(zip_path)

    out_parquet = out / "onet_career_pathways.parquet"
    onet.save_parquet(pathways, out_parquet)
    card = onet.build_data_card(zip_path, pathways, out_parquet)

    logger.success(
        f"Done. {len(pathways)} career pathways written to {out_parquet}\n"
        f"Data card: {out / 'onet_career_pathways_data_card.yaml'}"
    )
    logger.info(f"License: {card.license}")


if __name__ == "__main__":
    app()
