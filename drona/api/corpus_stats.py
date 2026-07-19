"""
Real corpus analytics for the dashboard.

Everything here is computed from the ACTUAL ingested artefacts - the Softwarica
curriculum, the O*NET pathway set, and the collected job postings - so the
dashboard shows measured data, never illustrative shapes.

The headline analysis is the **skill gap**: which skills the Nepali/international
market asks for in real postings, and whether the curriculum actually covers
them. That is the evidence behind "advice grounded in the local market", and it
is the chart an examiner will care about most.

Results are cached: the files are static between ingests, so the endpoint is
cheap to poll.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger

_ROOT = Path(__file__).resolve().parents[2]
_PROCESSED = _ROOT / "data" / "processed"

# Skills that appear in postings as noise rather than teachable competencies.
_SKILL_STOPWORDS = {
    "communication", "teamwork", "english", "time management", "leadership",
    "problem solving", "hard working", "team player", "self motivated",
}


def _load(name: str) -> list[dict[str, Any]]:
    p = _PROCESSED / name
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("items", [])
    except Exception as exc:  # noqa: BLE001 - analytics must never break the API
        logger.warning(f"corpus_stats: could not read {name}: {exc}")
        return []


def _norm_skill(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _top(counter: Counter[str], n: int) -> list[dict[str, Any]]:
    return [{"name": k, "count": v} for k, v in counter.most_common(n)]


@lru_cache(maxsize=1)
def corpus_stats() -> dict[str, Any]:
    """Aggregate the ingested corpus into dashboard-ready series."""
    modules = _load("curriculum_modules.json")
    pathways = _load("onet_career_pathways.json")
    postings = _load("manual_postings.json")

    # ── Curriculum ────────────────────────────────────────────────────────────
    by_programme: Counter[str] = Counter()
    by_year: Counter[str] = Counter()
    total_credits = 0
    for m in modules:
        by_programme[str(m.get("programme") or "unspecified")] += 1
        yr = m.get("year")
        by_year[f"Year {yr}" if yr else "unspecified"] += 1
        try:
            total_credits += int(m.get("credits") or 0)
        except (TypeError, ValueError):
            pass

    # ── Market (postings) ─────────────────────────────────────────────────────
    posting_tiers: Counter[str] = Counter()
    employers: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    demanded: Counter[str] = Counter()
    for p in postings:
        posting_tiers[str(p.get("tier") or "unspecified")] += 1
        if p.get("employer"):
            employers[str(p["employer"]).strip()] += 1
        if p.get("location"):
            locations[str(p["location"]).strip()] += 1
        for key in ("skills_required", "skills_preferred"):
            for s in p.get(key) or []:
                sk = _norm_skill(s)
                if sk and sk not in _SKILL_STOPWORDS and len(sk) > 1:
                    demanded[sk] += 1

    # ── Pathways ──────────────────────────────────────────────────────────────
    pathway_tiers: Counter[str] = Counter()
    for pw in pathways:
        pathway_tiers[str(pw.get("tier") or "unspecified")] += 1

    # ── SKILL GAP: demanded by the market vs covered by the curriculum ───────
    # A skill counts as "covered" if it appears in any module's title,
    # description or content. Rule-based and falsifiable - no LLM judgement.
    corpus_text = " \n ".join(
        f"{m.get('title','')} {m.get('description','')} {m.get('content','')}".lower()
        for m in modules
    )
    gap_rows: list[dict[str, Any]] = []
    covered_count = 0
    for skill, count in demanded.most_common(24):
        covered = skill in corpus_text
        covered_count += int(covered)
        gap_rows.append({
            "skill": skill,
            "demand": count,
            "covered": covered,
            # Charts want a numeric pair; taught=demand when covered so the bars
            # read as "market demand vs curriculum coverage" per skill.
            "taught": count if covered else 0,
            "gap": 0 if covered else count,
        })
    coverage_rate = (covered_count / len(gap_rows)) if gap_rows else 0.0

    return {
        "available": bool(modules or postings or pathways),
        "totals": {
            "modules": len(modules),
            "pathways": len(pathways),
            "postings": len(postings),
            "total_credits": total_credits,
            "distinct_skills_demanded": len(demanded),
            "employers": len(employers),
        },
        "modules_by_programme": [
            {"name": k, "count": v} for k, v in by_programme.most_common()
        ],
        "modules_by_year": [
            {"name": k, "count": v} for k, v in sorted(by_year.items())
        ],
        "postings_by_tier": [{"name": k, "count": v} for k, v in posting_tiers.most_common()],
        "pathways_by_tier": [{"name": k, "count": v} for k, v in pathway_tiers.most_common()],
        "top_employers": _top(employers, 10),
        "top_locations": _top(locations, 8),
        "top_skills_demanded": _top(demanded, 15),
        "skill_gap": gap_rows,
        "skill_coverage_rate": round(coverage_rate, 4),
    }
