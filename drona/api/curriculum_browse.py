"""
Module-level curriculum listing for the dashboard's curriculum explorer.

WHAT THIS DELIBERATELY DOES NOT RETURN
--------------------------------------
``CurriculumModule.content`` holds the full lesson/PDF body text pulled from the
authenticated Softwarica LMS. That material is not ours to redistribute, so it
never leaves the backend: this endpoint returns module METADATA (code, title,
programme, year, credits, skills, outcomes) plus a *derived* indicator of how
much lecture text backs each module, which is what the explorer actually needs.

The indicator matters for the thesis: it shows which modules the RAG index has
deep content for and which are only known from the public catalogue, so a reader
can see the retrieval corpus is uneven rather than assuming uniform coverage.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger

_ROOT = Path(__file__).resolve().parents[2]
_MODULES = _ROOT / "data" / "processed" / "curriculum_modules.json"


def _depth_band(n_chars: int) -> str:
    """Coarse band for how much lecture text backs a module."""
    if n_chars == 0:
        return "catalogue only"
    if n_chars < 5_000:
        return "light"
    if n_chars < 25_000:
        return "moderate"
    return "deep"


@lru_cache(maxsize=1)
def curriculum_modules() -> dict[str, Any]:
    """Every ingested module as safe metadata, plus explorer facets."""
    if not _MODULES.exists():
        logger.warning(f"/curriculum/modules: {_MODULES.name} not found - run the ingest")
        return {"available": False, "modules": []}
    try:
        raw = json.loads(_MODULES.read_text(encoding="utf-8"))
        modules = raw if isinstance(raw, list) else raw.get("items", [])
    except Exception as exc:  # noqa: BLE001 - explorer must not break the API
        logger.warning(f"/curriculum/modules: could not read modules: {exc}")
        return {"available": False, "modules": []}

    rows: list[dict[str, Any]] = []
    for m in modules:
        # `content` is authenticated LMS lecture text: measured, never returned.
        n_chars = len(m.get("content") or "")
        rows.append({
            "module_code": m.get("module_code", ""),
            "title": m.get("title", ""),
            "programme": m.get("programme", "software_engineering"),
            "year": m.get("year", 1),
            "semester": m.get("semester"),
            "credits": m.get("credits"),
            "is_core": bool(m.get("is_core", True)),
            "skills": list(m.get("skills_developed") or []),
            "learning_outcomes": list(m.get("learning_outcomes") or []),
            "prerequisites": list(m.get("prerequisites") or []),
            # Derived only - never the text itself.
            "content_chars": n_chars,
            "content_depth": _depth_band(n_chars),
            "has_lms_content": n_chars > 0,
        })

    rows.sort(key=lambda r: (r["programme"], r["year"], r["module_code"]))

    programmes = sorted({r["programme"] for r in rows})
    years = sorted({r["year"] for r in rows})
    n_with_content = sum(1 for r in rows if r["has_lms_content"])
    total_credits = sum(r["credits"] or 0 for r in rows)

    return {
        "available": True,
        "modules": rows,
        "facets": {"programmes": programmes, "years": years},
        "totals": {
            "modules": len(rows),
            "programmes": len(programmes),
            "with_lms_content": n_with_content,
            "catalogue_only": len(rows) - n_with_content,
            "total_credits": total_credits,
            "distinct_skills": len({s for r in rows for s in r["skills"]}),
        },
    }
