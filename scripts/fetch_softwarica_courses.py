"""Fetch official Softwarica programme data (overview, entry requirements,
careers, FEE STRUCTURE, module structure) from the public course API and write
programme-guide docs the advisor can cite.

Source: https://ftp.softwarica.edu.np/api/courses/<slug>  (public, no auth).
This is the data behind the softwarica.edu.np course pages' tabs (Overview,
Modules, Fee Structure, Career Opportunities, ...), which are JS-rendered and
so not visible to a plain page fetch.

Usage:
    python scripts/fetch_softwarica_courses.py
    python scripts/fetch_softwarica_courses.py --out-dir data/raw/curriculum

Afterwards:
    python scripts/prepare_training_data.py --skip-onet
    python scripts/ingest_data.py
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import typer

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = typer.Typer(help=__doc__)

API = "https://ftp.softwarica.edu.np/api"

# course slug -> DRONA programme tag
PROGRAMME_BY_SLUG = {
    "bsc-hons-software-engineering": "software_engineering",
    "bsc-hons-computing": "software_engineering",
    "bsc-hons-ethical-hacking-and-cybersecurity": "ethical_hacking",
    "bsc-hons-computer-science-with-artificial-intelligence": "csai",
}
# Master's / other courses have no bachelor programme tag; default them here.
DEFAULT_PROGRAMME = "software_engineering"

CODE_BY_PROGRAMME = {
    "software_engineering": "INFO-SE",
    "ethical_hacking": "INFO-EHC",
    "csai": "INFO-CSAI",
}


def _clean(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _module_lines(modules: dict) -> list[str]:
    """Flatten the year/semester module tree into 'Year N Sem M: title (credits)'."""
    out: list[str] = []
    if not isinstance(modules, dict):
        return out
    for _ykey, ydata in sorted(modules.items()):
        if not isinstance(ydata, dict):
            continue
        year = ydata.get("year", "?")
        for sem in ("semester1", "semester2"):
            items = ydata.get(sem) or []
            names = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                title = _clean(it.get("title") or it.get("name") or it.get("moduleTitle"))
                cr = it.get("credits")
                if title:
                    names.append(f"{title}" + (f" ({cr} cr)" if cr else ""))
            if names:
                s = sem[-1]
                out.append(f"Year {year} Semester {s}: " + "; ".join(names))
    return out


def _fee_lines(fee_structure: list) -> list[str]:
    out: list[str] = []
    for f in fee_structure or []:
        if not isinstance(f, dict):
            continue
        part = _clean(f.get("particular"))
        y = [_clean(f.get(k)) for k in ("firstYear", "secondYear", "thirdYear", "fourthYear")]
        y = [x for x in y if x and x not in ("-", "N/A")]
        if part and y:
            out.append(f"{part}: " + " | ".join(y))
    return out


def _course_to_md(d: dict) -> tuple[str, str, str]:
    """Return (programme, code, markdown) for one course record."""
    slug = _clean(d.get("slug"))
    programme = PROGRAMME_BY_SLUG.get(slug, DEFAULT_PROGRAMME)
    title = _clean(d.get("title")) or slug
    code = CODE_BY_PROGRAMME.get(programme, "INFO") + ("-MSC" if d.get("level") == "Masters" else "")

    careers = [_clean(c.get("title")) for c in (d.get("careerOpportunities") or [])
               if isinstance(c, dict) and _clean(c.get("title"))]
    careers = sorted(set(careers), key=careers.index)  # dedupe, keep order
    highlights = [_clean(h.get("title")) for h in (d.get("degreeHighlights") or [])
                  if isinstance(h, dict) and _clean(h.get("title"))]

    parts = [
        f"<!-- Official programme data from {API}/courses/{slug}",
        f"     (the softwarica.edu.np course-page tabs). Synced {date.today().isoformat()}",
        "     via scripts/fetch_softwarica_courses.py. -->",
        "",
        f"Module Code: {code}",
        f"Module Title: {title} - Programme Guide",
        f"Programme: {programme}",
        "",
        "Module Description:",
        _clean(d.get("overview")) or _clean(d.get("shortDescription")),
        "",
        f"Duration: {_clean(d.get('duration'))} | Credits: {_clean(d.get('credits'))} "
        f"| Intake: {_clean(d.get('intake'))} | Level: {_clean(d.get('level'))}",
    ]
    if highlights:
        parts += ["", "Degree highlights: " + "; ".join(highlights)]
    if careers:
        parts += ["", "Career opportunities: " + ", ".join(careers) + "."]
    elig = _clean(d.get("admissionEligibility"))
    eng = _clean(d.get("englishRequirement"))
    if elig or eng:
        parts += ["", "Admission eligibility: " + elig]
        if eng:
            parts.append("English requirement: " + eng)
    fees = _fee_lines(d.get("feeStructure"))
    if fees:
        parts += ["", "Fee structure (NPR unless stated; per year):"]
        parts += [f"- {ln}" for ln in fees]
    mods = _module_lines(d.get("modules"))
    if mods:
        parts += ["", "Programme structure (official modules):"]
        parts += [f"- {ln}" for ln in mods]
    why = _clean(d.get("whyCoventry"))
    if why:
        parts += ["", "Why Coventry University: " + why[:600]]
    parts += ["", "Offered by Softwarica College of IT & E-Commerce, Kathmandu, Nepal, "
              "in collaboration with Coventry University, UK."]
    return programme, code, "\n".join(parts) + "\n"


@app.command()
def main(
    out_dir: Path = typer.Option(Path("data/raw/curriculum"), "--out-dir"),
    slugs: str = typer.Option("", "--slugs", help="Comma list; default = all active courses"),
) -> None:
    import httpx

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
               "Accept": "application/json"}
    out_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=40, follow_redirects=True) as c:
        if slugs:
            wanted = [s.strip() for s in slugs.split(",") if s.strip()]
        else:
            r = c.get(f"{API}/courses", headers=headers)
            r.raise_for_status()
            data = r.json().get("data", [])
            wanted = [_clean(x.get("slug")) for x in data
                      if isinstance(x, dict) and x.get("slug") and not x.get("isDeleted")]
        typer.echo(f"{len(wanted)} course(s) to fetch")

        ok = 0
        for slug in wanted:
            try:
                r = c.get(f"{API}/courses/{slug}", headers=headers)
                if r.status_code != 200:
                    typer.secho(f"  {slug}: HTTP {r.status_code}", fg=typer.colors.YELLOW)
                    continue
                d = r.json().get("data")
                if not d:
                    continue
                programme, code, md = _course_to_md(d)
                path = out_dir / f"_guide_{re.sub(r'[^a-z0-9]+', '_', slug)}.md"
                path.write_text(md, encoding="utf-8")
                n_fee = len(d.get("feeStructure") or [])
                n_car = len(d.get("careerOpportunities") or [])
                ok += 1
                typer.echo(f"  {slug} -> {path.name} [{programme}] "
                           f"({n_car} careers, {n_fee} fee rows, {len(md):,} chars)")
            except Exception as exc:
                typer.secho(f"  {slug}: FAILED {exc}", fg=typer.colors.RED)

    # Remove the earlier brochure-derived guides (superseded by this API data).
    for legacy in ("_guide_csai.md", "_guide_software_engineering.md",
                   "_guide_ethical_hacking.md"):
        p = out_dir / legacy
        if p.exists():
            p.unlink()
            typer.echo(f"  removed superseded {legacy}")

    typer.secho(f"\n{ok} programme guide(s) written -> {out_dir}",
                fg=typer.colors.GREEN, bold=True)
    typer.echo("\nNext:\n  python scripts/prepare_training_data.py --skip-onet"
               "\n  python scripts/ingest_data.py")


if __name__ == "__main__":
    app()
