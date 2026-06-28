"""
ESCO v1.2.1 ingestion for D.R.O.N.A.

ESCO (European Skills, Competences, Qualifications and Occupations) is the EU's
multilingual classification. We use it as a second international-tier occupation
source alongside O*NET, because ESCO's skill taxonomy is finer-grained for ICT
roles and bridges nicely to the JobBERT-v3 career embedding space (contribution
C1, dual-embedding).

License: ESCO is released under CC BY 4.0.
Source:  https://esco.ec.europa.eu/en/use-esco/download (CSV bulk, v1.2.1)
         API: https://ec.europa.eu/esco/api (optional, see fetch_via_api)

Two ingestion paths:
  1. CSV bulk (PRIMARY, offline, reproducible) - expects the unzipped CSV
     distribution in a directory (occupations_en.csv, skills_en.csv,
     occupationSkillRelations_en.csv).
  2. API fallback (fetch_via_api) - for spot lookups when CSVs aren't present.

We filter to ICT occupations (ISCO unit group 25 - "Information and
communications technology professionals") so the dataset stays relevant to
Softwarica computing graduates.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from drona.contracts import CareerPathway, DataTier
from drona.data_pipeline.data_card import DataCard

ESCO_VERSION = "1.2.1"
ESCO_DOWNLOAD_PAGE = "https://esco.ec.europa.eu/en/use-esco/download"
ESCO_API_BASE = "https://ec.europa.eu/esco/api"

# ISCO group 25 = ICT professionals; 35 = ICT technicians. Keep both.
_ICT_ISCO_PREFIXES = ("25", "35")

# CSV filenames inside the ESCO distribution (English locale)
_F_OCCUPATIONS = "occupations_en.csv"
_F_SKILLS = "skills_en.csv"
_F_RELATIONS = "occupationSkillRelations_en.csv"


def _is_ict(isco_group: str | float | None) -> bool:
    if not isinstance(isco_group, str):
        isco_group = "" if isco_group is None else str(isco_group)
    code = isco_group.strip().lstrip("C")  # ESCO sometimes prefixes ISCO with 'C'
    return any(code.startswith(p) for p in _ICT_ISCO_PREFIXES)


def parse_csv_dir(csv_dir: Path) -> list[CareerPathway]:
    """Parse an unzipped ESCO CSV distribution into CareerPathway objects.

    Args:
        csv_dir: Directory containing occupations_en.csv (+ optional skills and
            relations CSVs). Missing optional files degrade gracefully.

    Returns:
        List of ICT CareerPathway objects (international tier, ESCO-sourced).
    """
    occ_path = csv_dir / _F_OCCUPATIONS
    if not occ_path.exists():
        raise FileNotFoundError(
            f"ESCO occupations file not found: {occ_path}. Download the v{ESCO_VERSION} "
            f"CSV bulk from {ESCO_DOWNLOAD_PAGE} and unzip into {csv_dir}."
        )

    logger.info(f"Parsing ESCO occupations from {occ_path}")
    occ = pd.read_csv(occ_path, dtype=str).fillna("")

    # Skill relations are optional - without them, pathways have empty skills.
    skill_label: dict[str, str] = {}
    relations: dict[str, list[str]] = {}
    rel_path = csv_dir / _F_RELATIONS
    skl_path = csv_dir / _F_SKILLS
    if rel_path.exists() and skl_path.exists():
        skl = pd.read_csv(skl_path, dtype=str).fillna("")
        skill_label = dict(zip(skl["conceptUri"], skl["preferredLabel"], strict=False))
        rel = pd.read_csv(rel_path, dtype=str).fillna("")
        for occ_uri, grp in rel.groupby("occupationUri"):
            relations[occ_uri] = grp["skillUri"].tolist()
        logger.info(f"  Loaded {len(skill_label)} skills, relations for {len(relations)} occupations")
    else:
        logger.warning("  Skill/relation CSVs absent - pathways will have empty skill lists")

    pathways: list[CareerPathway] = []
    for _, row in occ.iterrows():
        isco = row.get("iscoGroup", "")
        if not _is_ict(isco):
            continue
        uri = row.get("conceptUri", "")
        code = row.get("code", "") or isco
        skills: list[str] = []
        for skill_uri in relations.get(uri, [])[:15]:
            label = skill_label.get(skill_uri)
            if label:
                skills.append(label)

        pathway_id = f"esco_{code.replace('.', '_').replace('/', '_')}" if code else f"esco_{abs(hash(uri))}"
        pathways.append(
            CareerPathway(
                pathway_id=pathway_id,
                title=str(row.get("preferredLabel", "")).strip(),
                tier=DataTier.INTERNATIONAL,
                esco_code=code or None,
                description=str(row.get("description", "")).strip()[:2000],
                typical_skills=skills,
                typical_education=["Bachelor's degree or equivalent (ISCO skill level 4)"],
            )
        )

    logger.success(f"  Parsed {len(pathways)} ICT CareerPathway objects from ESCO")
    return pathways


def fetch_via_api(search_text: str, limit: int = 10, timeout: int = 30) -> list[CareerPathway]:
    """Spot-fetch ICT occupations from the ESCO API (CSV-less fallback).

    Used only when the CSV distribution isn't available. Network-dependent;
    not part of the reproducible offline pipeline.
    """
    import httpx

    logger.info(f"ESCO API search: '{search_text}' (limit={limit})")
    url = f"{ESCO_API_BASE}/search"
    params = {"text": search_text, "language": "en", "type": "occupation", "limit": str(limit)}
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        results = resp.json().get("_embedded", {}).get("results", [])

    pathways: list[CareerPathway] = []
    for item in results:
        title = item.get("title", "") or item.get("preferredLabel", {}).get("en-us", "")
        uri = item.get("uri", "")
        pathways.append(
            CareerPathway(
                pathway_id=f"esco_api_{abs(hash(uri))}",
                title=title,
                tier=DataTier.INTERNATIONAL,
                esco_code=uri or None,
                description="",
            )
        )
    return pathways


def build_data_card(pathways: list[CareerPathway], output_path: Path) -> DataCard:
    """Create and write the ESCO data card (YAML + Markdown)."""
    card = DataCard(
        name="esco_career_pathways",
        version=ESCO_VERSION,
        source_name=f"ESCO v{ESCO_VERSION}",
        source_url=ESCO_DOWNLOAD_PAGE,
        license="CC BY 4.0",
        tier="international",
        collection_method="automated_bulk_download",
        record_count=len(pathways),
        fields=list(CareerPathway.model_fields.keys()),
        description=(
            f"ICT occupations (ISCO groups 25/35) parsed from the ESCO v{ESCO_VERSION} "
            f"CSV distribution. Provides EU-standard occupation titles, descriptions, "
            f"and fine-grained skill associations. Used as a second international-tier "
            f"anchor (with O*NET) for the dual-embedding career retriever (C1)."
        ),
        known_limitations=[
            "European labour-market framing; titles may differ from Nepal usage",
            "No salary data (ESCO is a taxonomy, not a wage survey)",
            "Skill lists truncated to top 15 per occupation for embedding brevity",
        ],
        contains_synthetic=False,
        derived_from=[],
        output_files=[str(output_path)],
        notes=f"ISCO ICT filter prefixes: {_ICT_ISCO_PREFIXES}",
    )
    card.write(output_path.parent / "esco_career_pathways_data_card.yaml")
    logger.info("ESCO data card written")
    return card
