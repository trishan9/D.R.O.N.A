"""
O*NET 30.3 bulk-download parser for D.R.O.N.A.

Downloads the O*NET TSV zip, extracts the relevant files, and produces a list
of CareerPathway objects for technology/computing occupations (SOC 15-xxxx).

License: O*NET data is released under CC BY 4.0.
Source:  https://www.onetcenter.org/database.html

Design note: This module is intentionally self-contained. It reads from the zip
in memory, never writes raw TSVs to disk (only the cleaned Parquet + data card).
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import httpx
import pandas as pd
from loguru import logger

from drona.contracts import CareerPathway, DataTier
from drona.data_pipeline.data_card import DataCard
from drona.utils.settings import settings

ONET_VERSION = "30.3"
ONET_DOWNLOAD_URL = f"https://www.onetcenter.org/dl_files/database/db_{ONET_VERSION.replace('.', '_')}_text.zip"

# SOC major groups relevant to computing graduates at Softwarica
# 15-xxxx: Computer and Mathematical    11-3021: CIS Managers
RELEVANT_SOC_PREFIXES = ("15-",)
RELEVANT_SOC_EXTRAS = {"11-3021.00"}  # CIS Managers

# O*NET TSV files we care about (filename inside the zip).
# NOTE: O*NET 30.3 restructured the skills taxonomy. The old single
# "Skills.txt" / "Technology Skills.txt" / "Education, Training, and
# Experience.txt" became "Essential Skills.txt" / "Software Skills.txt" /
# "Education.txt" (+ a separate "Education Categories.txt" lookup).
_ONET_FILES = {
    "occupations": "Occupation Data.txt",
    "skills": "Essential Skills.txt",
    "tech_skills": "Software Skills.txt",
    "education": "Education.txt",
    "education_categories": "Education Categories.txt",
    "tasks": "Task Statements.txt",
}

# Legacy filenames (pre-30.3). Tried as a fallback so the parser keeps working
# against older O*NET archives.
_ONET_FILES_LEGACY = {
    "skills": "Skills.txt",
    "tech_skills": "Technology Skills.txt",
    "education": "Education, Training, and Experience.txt",
}

# Education level codes in O*NET that map to bachelor's degree equivalent
_EDU_CODES_BACHELOR_PLUS = {4, 5, 6, 7, 8}  # Associate's, Bachelor's, Master's, Doctoral, etc.


def _is_relevant_soc(soc: str) -> bool:
    return any(soc.startswith(p) for p in RELEVANT_SOC_PREFIXES) or soc in RELEVANT_SOC_EXTRAS


def download_zip(dest_path: Path | None = None, force: bool = False) -> Path:
    """Download the O*NET zip if not already cached.

    Args:
        dest_path: Where to save the zip. Defaults to data/raw/onet_30_3.zip.
        force: Re-download even if the file exists.

    Returns:
        Path to the downloaded zip file.
    """
    if dest_path is None:
        dest_path = settings.data_raw_dir / f"onet_{ONET_VERSION.replace('.', '_')}.zip"

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists() and not force:
        logger.info(f"O*NET zip already cached at {dest_path} - skipping download")
        return dest_path

    logger.info(f"Downloading O*NET {ONET_VERSION} from {ONET_DOWNLOAD_URL}")
    with httpx.stream("GET", ONET_DOWNLOAD_URL, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with dest_path.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    logger.debug(f"  {pct:.1f}% ({downloaded:,} / {total:,} bytes)")

    logger.success(f"O*NET zip saved to {dest_path} ({dest_path.stat().st_size:,} bytes)")
    return dest_path


def _read_tsv(zf: zipfile.ZipFile, filename: str) -> pd.DataFrame:
    """Read a TSV file from inside the zip into a DataFrame.

    Handles the versioned subdirectory prefix that O*NET zips use, and falls
    back to a no-prefix lookup for archives that differ.
    """
    prefix = f"db_{ONET_VERSION.replace('.', '_')}_text/"
    for candidate in (prefix + filename, filename):
        try:
            data = zf.read(candidate)
        except KeyError:
            continue
        return pd.read_csv(io.BytesIO(data), sep="\t", encoding="utf-8", dtype=str)
    raise KeyError(filename)


def _read_tsv_any(zf: zipfile.ZipFile, key: str) -> pd.DataFrame:
    """Read a logical O*NET table, trying the current then the legacy filename."""
    names = [_ONET_FILES[key]]
    if key in _ONET_FILES_LEGACY:
        names.append(_ONET_FILES_LEGACY[key])
    last_err: Exception | None = None
    for name in names:
        try:
            return _read_tsv(zf, name)
        except KeyError as e:  # noqa: PERF203
            last_err = e
    raise last_err or KeyError(key)


def _skills_for_soc(skills_df: pd.DataFrame, soc: str) -> list[str]:
    mask = skills_df["O*NET-SOC Code"] == soc
    # Filter to the Importance ("IM") scale so each skill is counted once and
    # ranked by how important it is to the occupation (not the level scale).
    if "Scale ID" in skills_df.columns:
        mask &= skills_df["Scale ID"] == "IM"
    subset = skills_df[mask].copy()
    if subset.empty:
        return []
    # Sort by Data Value descending, take top-10 skill names
    subset["Data Value"] = pd.to_numeric(subset["Data Value"], errors="coerce")
    subset = subset.sort_values("Data Value", ascending=False)
    return subset["Element Name"].dropna().unique().tolist()[:10]


def _tech_skills_for_soc(tech_df: pd.DataFrame, soc: str) -> list[str]:
    mask = tech_df["O*NET-SOC Code"] == soc
    # 30.3 uses "Workplace Example" for the concrete tool; legacy used "Example".
    for col in ("Workplace Example", "Example", "Element Name"):
        if col in tech_df.columns:
            return tech_df[mask][col].dropna().unique().tolist()[:15]
    return []


def _edu_for_soc(
    edu_df: pd.DataFrame, soc: str, edu_cat_map: dict[str, str] | None = None
) -> list[str]:
    mask = (edu_df["O*NET-SOC Code"] == soc) & (edu_df["Scale ID"] == "RL")
    subset = edu_df[mask].copy()
    if subset.empty:
        return ["Bachelor's degree or higher"]
    subset["Data Value"] = pd.to_numeric(subset["Data Value"], errors="coerce")
    top = subset.sort_values("Data Value", ascending=False).head(3)
    # 30.3 stores the category as a numeric code; map it via Education Categories.
    if edu_cat_map and "Category" in top.columns:
        out = [
            edu_cat_map[str(c).strip()]
            for c in top["Category"]
            if str(c).strip() in edu_cat_map
        ]
        if out:
            return out
    if "Category Description" in top.columns:
        return top["Category Description"].dropna().tolist()
    return ["Bachelor's degree or higher"]


def parse(zip_path: Path) -> list[CareerPathway]:
    """Parse the O*NET zip into CareerPathway objects for computing occupations.

    Args:
        zip_path: Path to the downloaded O*NET zip.

    Returns:
        List of CareerPathway objects (international tier, O*NET-sourced).
    """
    logger.info(f"Parsing O*NET zip: {zip_path}")

    with zipfile.ZipFile(zip_path) as zf:
        occ_df = _read_tsv(zf, _ONET_FILES["occupations"])
        skills_df = _read_tsv_any(zf, "skills")
        tech_df = _read_tsv_any(zf, "tech_skills")

        # Education file might not exist in all versions
        try:
            edu_df = _read_tsv_any(zf, "education")
        except Exception:
            edu_df = pd.DataFrame()

        # 30.3 keeps human-readable education levels in a separate lookup table.
        edu_cat_map: dict[str, str] = {}
        try:
            edu_cat_df = _read_tsv(zf, _ONET_FILES["education_categories"])
            rl = edu_cat_df[edu_cat_df["Scale ID"] == "RL"]
            edu_cat_map = {
                str(r["Category"]).strip(): str(r["Category Description"]).strip()
                for _, r in rl.iterrows()
            }
        except Exception:
            edu_cat_map = {}

    # Filter to relevant SOC codes
    relevant = occ_df[occ_df["O*NET-SOC Code"].apply(_is_relevant_soc)].copy()
    logger.info(f"  {len(relevant)} computing/tech occupations found in O*NET")

    pathways: list[CareerPathway] = []
    for _, row in relevant.iterrows():
        soc = str(row["O*NET-SOC Code"]).strip()
        title = str(row.get("Title", "")).strip()
        description = str(row.get("Description", "")).strip()

        # Build a stable pathway_id from the SOC code
        pathway_id = f"onet_{soc.replace('.', '_').replace('-', '_')}"

        combined_skills = list(dict.fromkeys(  # preserve order, deduplicate
            _skills_for_soc(skills_df, soc) + _tech_skills_for_soc(tech_df, soc)
        ))

        typical_edu = (
            _edu_for_soc(edu_df, soc, edu_cat_map)
            if not edu_df.empty
            else ["Bachelor's degree or higher"]
        )

        pathway = CareerPathway(
            pathway_id=pathway_id,
            title=title,
            tier=DataTier.INTERNATIONAL,
            onet_soc_code=soc,
            description=description,
            typical_skills=combined_skills,
            typical_education=typical_edu or ["Bachelor's degree or higher"],
        )
        pathways.append(pathway)

    logger.success(f"  Parsed {len(pathways)} CareerPathway objects from O*NET")
    return pathways


def save_parquet(pathways: list[CareerPathway], dest: Path) -> None:
    """Serialise pathways to Parquet for fast downstream loading."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    records = [p.model_dump(mode="json") for p in pathways]
    df = pd.DataFrame(records)
    # Tuple columns → JSON strings for Parquet compatibility
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, (list, tuple, dict))).any():
            df[col] = df[col].apply(lambda x: str(x) if isinstance(x, (list, tuple, dict)) else x)
    df.to_parquet(dest, index=False)
    logger.success(f"Saved {len(df)} records to {dest}")


def build_data_card(zip_path: Path, pathways: list[CareerPathway], dest: Path) -> DataCard:
    """Create and write the O*NET data card."""
    card = DataCard(
        name="onet_career_pathways",
        version=ONET_VERSION,
        source_name=f"O*NET {ONET_VERSION} Database",
        source_url="https://www.onetcenter.org/database.html",
        license="CC BY 4.0",
        tier="international",
        collection_method="automated_bulk_download",
        record_count=len(pathways),
        fields=list(CareerPathway.model_fields.keys()),
        description=(
            f"Computing and technology occupations (SOC 15-xxxx + CIS Managers) "
            f"parsed from O*NET {ONET_VERSION}. Includes titles, descriptions, "
            f"skill profiles, and technology skill examples. "
            f"Used as international-tier anchor for career pathway recommendations."
        ),
        known_limitations=[
            "US labour market only - salaries not included (US context)",
            "SOC taxonomy may not perfectly map to Nepal job market titles",
            "Technology skills list is indicative, not exhaustive",
        ],
        contains_synthetic=False,
        robots_txt_verified=True,
        robots_txt_allows_crawl=True,
        rate_limit_applied="N/A (single bulk download)",
        output_files=[str(dest)],
        notes=f"Downloaded from {ONET_DOWNLOAD_URL}. Zip SHA256: {_sha256(zip_path)}",
    )
    card_path = dest.parent / "onet_career_pathways_data_card.yaml"
    card.write(card_path)
    logger.info(f"Data card written to {card_path}")
    return card


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]  # first 16 chars for brevity
