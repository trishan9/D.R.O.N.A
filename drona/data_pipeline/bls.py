"""
BLS OEWS (Occupational Employment and Wage Statistics) ingestion for D.R.O.N.A.

BLS OEWS gives US wage distributions per SOC occupation code. We use it ONLY to
attach an international salary band (USD, 10th–90th percentile) to O*NET
pathways, which share the SOC taxonomy. This provides honest international wage
context that the advising layer contrasts against Nepal-tier salary evidence —
directly serving the anti-anchoring goal (C2/C4): never present US salaries as
locally attainable.

License: BLS data is US Government public domain.
Source:  https://www.bls.gov/oes/tables.htm (national OEWS, May 2025)

The national file is an .xlsx/.csv with columns including OCC_CODE, OCC_TITLE,
A_PCT10, A_MEAN, A_PCT90 (annual wages). We read whichever format is present.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from drona.contracts import CareerPathway
from drona.data_pipeline.data_card import DataCard

OEWS_VERSION = "May 2025"
OEWS_SOURCE_URL = "https://www.bls.gov/oes/tables.htm"

# Computing SOC major group. OEWS uses 6-digit "15-1252" style; O*NET adds ".00".
_COMPUTING_SOC_PREFIX = "15-"


def _to_int(value: object) -> int | None:
    """OEWS marks unavailable/cap values with '*', '#', '>=', etc."""
    try:
        s = str(value).replace(",", "").replace("$", "").strip()
        if not s or s in {"*", "#", "**"} or s.startswith(">"):
            return None
        return int(float(s))
    except (ValueError, TypeError):
        return None


def load_wage_table(path: Path) -> dict[str, tuple[int, int]]:
    """Load OEWS national file → {SOC code: (annual_pct10_usd, annual_pct90_usd)}.

    Accepts .xlsx or .csv. Filters to computing occupations (SOC 15-xxxx).
    SOC keys are normalised to the 6-digit form without the O*NET ".00" suffix.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"OEWS file not found: {path}. Download the national OEWS table "
            f"({OEWS_VERSION}) from {OEWS_SOURCE_URL}."
        )

    logger.info(f"Loading BLS OEWS wage table from {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)
    df.columns = [c.upper().strip() for c in df.columns]

    code_col = next((c for c in ("OCC_CODE", "OCC CODE") if c in df.columns), None)
    if code_col is None:
        raise ValueError(f"OEWS file missing OCC_CODE column; got {list(df.columns)}")

    wages: dict[str, tuple[int, int]] = {}
    for _, row in df.iterrows():
        soc = str(row[code_col]).strip()
        if not soc.startswith(_COMPUTING_SOC_PREFIX):
            continue
        pct10 = _to_int(row.get("A_PCT10"))
        pct90 = _to_int(row.get("A_PCT90"))
        mean = _to_int(row.get("A_MEAN"))
        lo = pct10 if pct10 is not None else mean
        hi = pct90 if pct90 is not None else mean
        if lo is not None and hi is not None:
            wages[soc] = (lo, hi)

    logger.success(f"  Loaded wage bands for {len(wages)} computing occupations")
    return wages


def enrich_pathways(
    pathways: list[CareerPathway], wages: dict[str, tuple[int, int]]
) -> list[CareerPathway]:
    """Attach international_salary_range_usd to O*NET pathways via SOC match.

    Returns NEW CareerPathway objects (contracts are effectively immutable in
    intent); pathways without a SOC match are returned unchanged.
    """
    enriched: list[CareerPathway] = []
    hits = 0
    for pw in pathways:
        soc = pw.onet_soc_code
        band = None
        if soc:
            # O*NET "15-1252.00" → OEWS "15-1252"
            band = wages.get(soc) or wages.get(soc.split(".")[0])
        if band:
            hits += 1
            enriched.append(pw.model_copy(update={"international_salary_range_usd": band}))
        else:
            enriched.append(pw)
    logger.info(f"  Enriched {hits}/{len(pathways)} pathways with OEWS wage bands")
    return enriched


def build_data_card(wages: dict[str, tuple[int, int]], output_path: Path) -> DataCard:
    """Create and write the BLS OEWS data card (YAML + Markdown)."""
    card = DataCard(
        name="bls_oews_wages",
        version=OEWS_VERSION,
        source_name=f"BLS OEWS {OEWS_VERSION}",
        source_url=OEWS_SOURCE_URL,
        license="US Government public domain",
        tier="international",
        collection_method="automated_bulk_download",
        record_count=len(wages),
        fields=["soc_code", "annual_pct10_usd", "annual_pct90_usd"],
        description=(
            "US annual wage bands (10th–90th percentile) for computing occupations "
            "(SOC 15-xxxx). Used solely to attach honest international salary context "
            "to O*NET pathways; the advising layer always contrasts these against "
            "Nepal-tier evidence to avoid anchoring (C2/C4)."
        ),
        known_limitations=[
            "US wages only — NOT representative of Nepal compensation",
            "Percentiles capped by BLS for very high earners",
            "SOC matching to O*NET drops the .00 detail-occupation suffix",
        ],
        contains_synthetic=False,
        output_files=[str(output_path)],
        notes="Consumed by bls.enrich_pathways() to fill international_salary_range_usd.",
    )
    card.write(output_path.parent / "bls_oews_wages_data_card.yaml")
    logger.info("BLS OEWS data card written")
    return card
