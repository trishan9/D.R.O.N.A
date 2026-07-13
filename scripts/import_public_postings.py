"""Import a popular public job-postings dataset as INTERNATIONAL-tier evidence.

Converts postings from a Hugging Face dataset (default: **lukebarousse/data_jobs**,
the widely used 2023+ data/tech postings corpus, ~785k rows) or any Kaggle-style
CSV into the JobPosting schema under data/manual_collection/, so they flow
through the EXISTING pipeline (manual loader -> ingest -> career collection)
with zero code changes elsewhere.

Why international tier, and why capped: DRONA's contribution C4 is Nepal-FIRST
advising. International postings add breadth for generic queries ("data
scientist requirements") and honest global context, but must not drown the
Nepal-tier evidence - retrieval already boosts tiers (TIER_NEPAL_BOOST=1.5 vs
INTERNATIONAL=1.0), and the default --limit keeps the index balanced.
Salaries are deliberately NOT converted USD->NPR (that would fabricate local
figures); the USD figure is kept as text context in the description.

LinkedIn-sourced rows are dropped (project ethics policy: no LinkedIn data).

Usage:
    python scripts/import_public_postings.py                       # HF data_jobs, 200 rows
    python scripts/import_public_postings.py --limit 400 --keyword engineer
    python scripts/import_public_postings.py --csv my_kaggle_file.csv \\
        --col-title title --col-company company --col-skills skills

Afterwards:
    python scripts/prepare_training_data.py --skip-onet
    python scripts/ingest_data.py
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import date
from pathlib import Path

import typer

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = typer.Typer(help=__doc__)

HF_DEFAULT = "lukebarousse/data_jobs"


def _parse_skills(value) -> list[str]:
    """data_jobs stores skills as a list or a stringified list; handle both."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(s) for s in value][:20]
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return [str(s) for s in parsed][:20]
        except (ValueError, SyntaxError):
            pass
        return [s.strip() for s in value.split(",") if s.strip()][:20]
    return []


def _rows_from_hf(dataset: str, need: int, keyword: str, require_skills: bool):
    try:
        import datasets  # noqa: F401
    except ImportError as exc:
        raise typer.Exit(
            "the 'datasets' package is required for the HF path: pip install datasets"
        ) from exc
    import datasets as hfds

    stream = hfds.load_dataset(dataset, split="train", streaming=True)
    for row in stream:
        title = str(row.get("job_title") or "")
        if keyword and keyword.lower() not in title.lower():
            continue
        via = str(row.get("job_via") or "")
        if "linkedin" in via.lower():        # ethics policy: never LinkedIn data
            continue
        skills = _parse_skills(row.get("job_skills"))
        if require_skills and not skills:
            continue
        yield {
            "title": title,
            "employer": str(row.get("company_name") or "unknown"),
            "location": ", ".join(x for x in [row.get("job_location"),
                                              row.get("job_country")] if x),
            "skills": skills,
            "schedule": row.get("job_schedule_type"),
            "via": via,
            "posted": str(row.get("job_posted_date") or "") or None,
            "salary_usd_year": row.get("salary_year_avg"),
        }
        need -= 1
        if need <= 0:
            return


def _rows_from_csv(path: Path, need: int, keyword: str, require_skills: bool, cols: dict):
    import pandas as pd

    df = pd.read_csv(path)
    missing = [c for c in (cols["title"], cols["company"]) if c not in df.columns]
    if missing:
        raise typer.Exit(f"CSV lacks column(s) {missing}. Available: {list(df.columns)}")
    for _, r in df.iterrows():
        title = str(r.get(cols["title"]) or "")
        if not title or (keyword and keyword.lower() not in title.lower()):
            continue
        skills = _parse_skills(r.get(cols["skills"])) if cols["skills"] in df.columns else []
        if require_skills and not skills:
            continue
        yield {
            "title": title,
            "employer": str(r.get(cols["company"]) or "unknown"),
            "location": str(r.get(cols["location"]) or "") if cols["location"] in df.columns else "",
            "skills": skills,
            "schedule": None,
            "via": f"csv:{path.name}",
            "posted": None,
            "salary_usd_year": None,
            "description_raw": (str(r.get(cols["description"]))[:500]
                                if cols["description"] in df.columns else None),
        }
        need -= 1
        if need <= 0:
            return


@app.command()
def main(
    hf_dataset: str = typer.Option(HF_DEFAULT, "--hf-dataset",
                                   help="Hugging Face dataset id (streaming; no full download)"),
    csv: Path = typer.Option(None, "--csv", help="Import a local Kaggle-style CSV instead"),
    limit: int = typer.Option(200, "--limit",
                              help="Max postings (keeps the Nepal-first index balanced)"),
    keyword: str = typer.Option("", "--keyword", help="Only titles containing this word"),
    require_skills: bool = typer.Option(True, "--require-skills/--no-require-skills",
                                        help="Skip rows without a skills list"),
    col_title: str = typer.Option("job_title", "--col-title"),
    col_company: str = typer.Option("company_name", "--col-company"),
    col_location: str = typer.Option("job_location", "--col-location"),
    col_skills: str = typer.Option("job_skills", "--col-skills"),
    col_description: str = typer.Option("description", "--col-description"),
    out_dir: Path = typer.Option(None, "--out-dir",
                                 help="Default: data/manual_collection/<source>/"),
) -> None:
    source = "csv_import" if csv else hf_dataset.split("/")[-1].replace("-", "_")
    cols = {"title": col_title, "company": col_company, "location": col_location,
            "skills": col_skills, "description": col_description}

    typer.echo(f"reading up to {limit} postings from "
               f"{'CSV ' + str(csv) if csv else 'HF ' + hf_dataset} ...")
    raw = list(_rows_from_csv(csv, limit * 3, keyword, require_skills, cols) if csv
               else _rows_from_hf(hf_dataset, limit * 3, keyword, require_skills))

    # Dedupe (title, employer), then cap.
    seen: set[tuple[str, str]] = set()
    postings = []
    for i, r in enumerate(raw):
        key = (r["title"].lower().strip(), r["employer"].lower().strip())
        if key in seen:
            continue
        seen.add(key)
        desc_bits = [f"{r['title']} at {r['employer']}"]
        if r["location"]:
            desc_bits.append(f"({r['location']})")
        if r.get("schedule"):
            desc_bits.append(f"- {r['schedule']}")
        if r.get("via"):
            desc_bits.append(f"- listed {r['via']}")
        if r.get("salary_usd_year"):
            desc_bits.append(f"- advertised salary ~USD {int(r['salary_usd_year']):,}/yr "
                             "(international figure, not Nepal-attainable)")
        if r.get("skills"):
            desc_bits.append(". Skills: " + ", ".join(r["skills"]) + ".")
        if r.get("description_raw"):
            desc_bits.append(" " + r["description_raw"])
        postings.append({
            "posting_id": f"intl_{source}_{i:05d}",
            "source": source,
            "tier": "international",
            "title": r["title"][:120],
            "employer": r["employer"][:80],
            "location": r["location"][:80] or None,
            "skills_required": r["skills"],
            "skills_preferred": [],
            "experience_years_min": None,
            "salary_min_npr": None,          # USD is never converted to NPR
            "salary_max_npr": None,
            "description": " ".join(desc_bits)[:900],
            "posted_date": r.get("posted"),
            "source_url": f"https://huggingface.co/datasets/{hf_dataset}" if not csv else str(csv),
            "is_synthetic": False,
        })
        if len(postings) >= limit:
            break

    if not postings:
        typer.secho("no postings matched - relax --keyword / --no-require-skills",
                    fg=typer.colors.RED)
        raise typer.Exit(1)

    out = out_dir or (ROOT / "data" / "manual_collection" / source)
    out.mkdir(parents=True, exist_ok=True)
    out_file = out / "international_postings.json"
    out_file.write_text(json.dumps(postings, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "README.md").write_text(
        f"# International postings - {source}\n\n"
        f"- Imported {len(postings)} postings on {date.today().isoformat()} via "
        f"`scripts/import_public_postings.py`.\n"
        f"- Source: {'local CSV ' + str(csv) if csv else 'https://huggingface.co/datasets/' + hf_dataset}\n"
        f"- Tier: **international** (retrieval boosts Nepal-tier above these; C4).\n"
        f"- Salaries kept in USD inside descriptions only - never converted to NPR.\n"
        f"- LinkedIn-sourced rows excluded (project ethics policy).\n",
        encoding="utf-8")

    # Validate through the real loader so schema errors surface NOW, not at ingest.
    from drona.data_pipeline.scrapers import manual_loader
    loaded = manual_loader.load_file(out_file)
    typer.secho(f"\n{len(postings)} postings written -> {out_file}", fg=typer.colors.GREEN,
                bold=True)
    typer.echo(f"schema validation: {len(loaded)}/{len(postings)} load as JobPosting")
    typer.echo("\nNext:  python scripts/prepare_training_data.py --skip-onet"
               "\n       python scripts/ingest_data.py")


if __name__ == "__main__":
    app()
