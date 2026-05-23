"""
Loader and validator for manually-collected job posting JSON files.

Used for:
  - MeroJob (JS-rendered site, no accessible API → manual collection)
  - LinkedIn (ToS prohibits automated collection → manual only)
  - Any portal where automation is not viable or not permitted

The manual collection protocol is documented in:
  data/manual_collection/README.md

Usage:
    postings = load_manual_dir(Path("data/manual_collection/merojob"))
    # Validates each entry against JobPosting schema, skips invalid entries with logging.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from drona.contracts import DataTier, JobPosting
from drona.data_pipeline.data_card import DataCard


def load_file(path: Path) -> list[JobPosting]:
    """Load and validate a single JSON file of job postings.

    Args:
        path: Path to a JSON file containing a list of raw posting dicts.

    Returns:
        List of valid JobPosting objects. Invalid entries are logged and skipped.
    """
    logger.info(f"Loading manual postings from {path}")
    raw: list[dict] = json.loads(path.read_text(encoding="utf-8"))

    postings: list[JobPosting] = []
    for i, entry in enumerate(raw):
        try:
            # Coerce tier string to enum if necessary
            if "tier" in entry and isinstance(entry["tier"], str):
                entry["tier"] = DataTier(entry["tier"].lower())
            posting = JobPosting.model_validate(entry)
            postings.append(posting)
        except Exception as e:
            logger.warning(f"  Entry {i} in {path.name} failed validation: {e}")

    logger.info(f"  Loaded {len(postings)} / {len(raw)} entries from {path.name}")
    return postings


def load_manual_dir(directory: Path) -> list[JobPosting]:
    """Load all JSON files from a manual collection directory.

    Args:
        directory: Directory containing *.json posting files.

    Returns:
        Combined list of all valid JobPosting objects across all files.
    """
    json_files = sorted(directory.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {directory}")
        return []

    all_postings: list[JobPosting] = []
    for f in json_files:
        all_postings.extend(load_file(f))

    # Deduplicate by posting_id
    seen: set[str] = set()
    unique: list[JobPosting] = []
    for p in all_postings:
        if p.posting_id not in seen:
            seen.add(p.posting_id)
            unique.append(p)
        else:
            logger.debug(f"  Duplicate posting_id skipped: {p.posting_id}")

    dupes = len(all_postings) - len(unique)
    if dupes:
        logger.warning(f"Removed {dupes} duplicate posting_ids from {directory}")

    logger.success(f"Manual loader: {len(unique)} unique postings from {directory}")
    return unique


def load_all_manual(base_dir: Path | None = None) -> list[JobPosting]:
    """Load manual postings from all portal subdirectories.

    Expected structure:
        base_dir/
          merojob/       ← MeroJob manual collection
          linkedin/      ← LinkedIn manual collection
          (others)       ← any other manual sources

    Args:
        base_dir: Root of manual collection. Defaults to data/manual_collection.
    """
    from drona.utils.settings import settings
    base = base_dir or settings.data_manual_dir

    all_postings: list[JobPosting] = []
    for subdir in sorted(base.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            all_postings.extend(load_manual_dir(subdir))

    logger.success(f"Total manual postings loaded: {len(all_postings)}")
    return all_postings


def build_data_card(
    postings: list[JobPosting],
    source_name: str,
    source_url: str,
    output_path: Path,
) -> DataCard:
    """Build a DataCard for a manually-collected portal dataset."""
    portal_slug = source_name.lower().replace(" ", "_")
    card = DataCard(
        name=f"{portal_slug}_manual_postings",
        source_name=source_name,
        source_url=source_url,
        license="custom — public job postings; paraphrased summaries, no PII",
        tier="nepal",
        collection_method="manual_user_collection",
        record_count=len(postings),
        fields=list(JobPosting.model_fields.keys()),
        description=(
            f"Tech job postings manually collected from {source_name}. "
            f"Collector visited public job pages and transcribed key fields "
            f"into the standard DRONA JobPosting JSON schema. "
            f"No automated requests were made. No PII captured."
        ),
        known_limitations=[
            "Sample size limited by manual effort (~50 postings per portal)",
            "Collector selection bias toward roles recognizable as 'tech'",
            "Descriptions are paraphrased, not verbatim",
        ],
        contains_synthetic=False,
        robots_txt_verified=True,
        robots_txt_allows_crawl=True,
        rate_limit_applied="N/A (manual collection)",
        output_files=[str(output_path)],
        notes=(
            "Manual collection guide and JSON template: "
            "data/manual_collection/README.md"
        ),
    )
    card.write(output_path.parent / f"{portal_slug}_data_card.yaml")
    return card
