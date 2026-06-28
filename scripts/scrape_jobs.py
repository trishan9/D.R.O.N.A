"""
Scrape Nepali tech job postings from automated sources and load manual collections.

Automated (robots.txt verified May 2026):
  - jobsnepal   - SSR site, sitemap-based discovery
  - internsathi - sitemap-based, individual pages only
  - kumarijob   - /search endpoint + individual pages

Manual loaders (JS-rendered or ToS restricts automation):
  - merojob     - load from data/manual_collection/merojob/
  - linkedin    - load from data/manual_collection/linkedin/

Usage:
    python scripts/scrape_jobs.py                       # all sources, default limits
    python scripts/scrape_jobs.py --source jobsnepal    # single source
    python scripts/scrape_jobs.py --limit 50            # cap pages per source
    python scripts/scrape_jobs.py --dry-run             # discover URLs, don't scrape
    python scripts/scrape_jobs.py --help
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

import typer
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from drona.contracts import JobPosting
from drona.data_pipeline.scrapers import internsathi, jobsnepal, kumarijob, manual_loader
from drona.utils.logging import setup_logging
from drona.utils.settings import settings

SourceType = Literal["jobsnepal", "internsathi", "kumarijob", "manual", "all"]

app = typer.Typer(help=__doc__)


def _save_postings(postings: list[JobPosting], out_dir: Path, source: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{source}_postings.json"
    data = [p.model_dump(mode="json") for p in postings]
    # Convert datetime objects to strings
    def _clean(obj: object) -> object:
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(i) for i in obj]
        return str(obj) if hasattr(obj, "isoformat") else obj

    out_path.write_text(
        json.dumps([_clean(d) for d in data], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.success(f"Saved {len(postings)} {source} postings → {out_path}")
    return out_path


@app.command()
def main(
    source: SourceType = typer.Option("all", "--source", help="Which source to scrape"),
    limit: int | None = typer.Option(None, "--limit", help="Max pages per automated source"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Only count URLs, don't parse"),
    out_dir: Path = typer.Option(None, "--out-dir", help="Output directory"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level, log_file=settings.log_file)
    settings.ensure_dirs()
    out = out_dir or settings.data_processed_dir

    if dry_run:
        logger.info("DRY RUN - discovering URLs only, not scraping pages")

    all_postings: list[JobPosting] = []

    # ── JobsNepal ──────────────────────────────────────────────────────────
    if source in ("jobsnepal", "all"):
        logger.info("=== JobsNepal ===")
        if dry_run:
            from drona.data_pipeline.scrapers._http import PoliteScraper
            from drona.data_pipeline.scrapers.jobsnepal import _discover_tech_urls
            with PoliteScraper() as sc:
                urls = _discover_tech_urls(sc, limit=limit)
            logger.info(f"JobsNepal: would scrape {len(urls)} URLs")
        else:
            posts = jobsnepal.scrape(limit=limit)
            all_postings.extend(posts)
            if posts:
                p = _save_postings(posts, out, "jobsnepal")
                jobsnepal.build_data_card(posts, p)

    # ── Internsathi ────────────────────────────────────────────────────────
    if source in ("internsathi", "all"):
        logger.info("=== Internsathi ===")
        if dry_run:
            from drona.data_pipeline.scrapers._http import PoliteScraper
            from drona.data_pipeline.scrapers.internsathi import _discover_opportunity_urls
            with PoliteScraper() as sc:
                urls = _discover_opportunity_urls(sc, limit=limit)
            logger.info(f"Internsathi: would scrape {len(urls)} URLs")
        else:
            posts = internsathi.scrape(limit=limit)
            all_postings.extend(posts)
            if posts:
                p = _save_postings(posts, out, "internsathi")
                internsathi.build_data_card(posts, p)

    # ── KumariJob ──────────────────────────────────────────────────────────
    if source in ("kumarijob", "all"):
        logger.info("=== KumariJob ===")
        if not dry_run:
            posts = kumarijob.scrape(limit=limit)
            all_postings.extend(posts)
            if posts:
                p = _save_postings(posts, out, "kumarijob")
                kumarijob.build_data_card(posts, p)

    # ── Manual collections ────────────────────────────────────────────────
    if source in ("manual", "all"):
        logger.info("=== Manual collections (MeroJob, LinkedIn) ===")
        manual_posts = manual_loader.load_all_manual(settings.data_manual_dir)
        if manual_posts:
            all_postings.extend(manual_posts)
            p = _save_postings(manual_posts, out, "manual")
        else:
            logger.warning(
                "No manual postings found. "
                "Follow data/manual_collection/README.md to add them."
            )

    logger.success(
        f"Total job postings collected: {len(all_postings)} "
        f"(Nepal tier: {sum(1 for p in all_postings if p.tier.value == 'nepal')})"
    )


if __name__ == "__main__":
    app()
