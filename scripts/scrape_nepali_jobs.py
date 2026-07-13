"""Collect REAL Nepali tech job postings from the MeroJob public API.

MeroJob (merojob.com) is Nepal's largest job portal; its robots.txt permits
crawling (`Disallow:` empty) and it exposes a public JSON API at
`api.merojob.com/api/v1/jobs/`. We query it for computing/tech roles across a
set of search terms, map each posting to the JobPosting schema (Nepal tier),
and write them to data/manual_collection/merojob/ - replacing the placeholder
set. Only public listing fields are stored; no personal data.

LinkedIn is deliberately NOT used (ToS prohibition; project ethics policy).

Usage:
    python scripts/scrape_nepali_jobs.py
    python scripts/scrape_nepali_jobs.py --min-jobs 40

Afterwards:
    python scripts/prepare_training_data.py --skip-onet
    python scripts/ingest_data.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import typer

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = typer.Typer(help=__doc__)

MEROJOB_API = "https://api.merojob.com/api/v1/jobs/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://merojob.com/",
}

# Tech search terms - catch computing roles even when categorised generically.
TECH_TERMS = [
    "developer", "software", "engineer", "python", "java", "javascript",
    "php", "react", "node", "flutter", "android", "data", "analyst",
    "network", "security", "devops", "qa", "tester", "database", "cloud",
    "system", "IT", "web", "frontend", "backend", "full stack", "AI",
    "machine learning", "cyber",
]

# Keep only genuinely tech postings (category or skills signal).
TECH_SIGNALS = re.compile(
    r"\b(develop|software|program|engineer|python|java|javascript|php|react|"
    r"node|flutter|android|ios|kotlin|data|analyst|network|security|devops|"
    r"qa|tester|database|sql|cloud|aws|azure|system admin|web|frontend|"
    r"backend|full.?stack|machine learning|\bAI\b|cyber|it support|"
    r"information technology|telecommunication)\b", re.I)


def _strip_html(html: str) -> str:
    if not html or "<" not in html:
        return (html or "").strip()
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html).strip()


def _exp_years(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)", str(text))
    return int(m.group(1)) if m else None


def _is_tech(j: dict) -> bool:
    cats = " ".join(str(x) for x in (j.get("categories") or []))
    skills = " ".join(str(x) for x in (j.get("skills") or []))
    blob = f"{j.get('title','')} {cats} {skills}"
    return bool(TECH_SIGNALS.search(blob))


def _to_posting(j: dict) -> dict:
    client = j.get("client") or {}
    sal = j.get("offered_salary") or {}
    locs = j.get("job_locations") or []
    loc = ""
    if locs:
        loc = _strip_html(locs[0].get("address") or locs[0].get("name") or "")
    smin = sal.get("minimum") if not j.get("hide_salary") else None
    smax = sal.get("maximum") if not j.get("hide_salary") else None
    desc = _strip_html((j.get("job_summary") or "")
                       or (j.get("description") or "") + " " + (j.get("specification") or ""))
    return {
        "posting_id": f"me_{j.get('id')}",
        "source": "merojob",
        "tier": "nepal",
        "title": (j.get("title") or "").strip()[:150],
        "employer": (client.get("client_name") or "").strip()[:100] or None,
        "location": loc[:100] or "Nepal",
        "skills_required": [s for s in (j.get("skills") or []) if s][:20],
        "skills_preferred": [],
        "experience_years_min": _exp_years(j.get("experience_required")),
        "salary_min_npr": int(smin) if smin else None,
        "salary_max_npr": int(smax) if smax else None,
        "description": desc[:900] or f"{j.get('title','')} at {client.get('client_name','')}.",
        "posted_date": (j.get("posted_date") + "T00:00:00") if j.get("posted_date") else None,
        "collected_date": datetime.now().isoformat(timespec="seconds"),
        "source_url": "https://merojob.com" + (j.get("absolute_url") or ""),
        "is_synthetic": False,
    }


KUMARIJOB = "https://www.kumarijob.com"
KUMARI_TERMS = ["developer", "software", "engineer", "data", "network",
                "security", "IT", "qa", "devops", "system"]


def _fetch_kumarijob(client, delay: float) -> list[dict]:
    """Real postings from KumariJob via its schema.org JSON-LD (server-rendered)."""
    from bs4 import BeautifulSoup

    job_urls: set[str] = set()
    for term in KUMARI_TERMS:
        try:
            r = client.get(f"{KUMARIJOB}/search", headers={"User-Agent": HEADERS["User-Agent"]},
                           params={"keywords": term}, timeout=30)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=True):
                h = a["href"]
                # job detail: /<company>/<numeric-id>-<slug>
                if re.search(r"/[a-z0-9-]+/\d{4,}-[a-z0-9-]+$", h):
                    job_urls.add(h if h.startswith("http") else KUMARIJOB + h)
        except Exception:
            continue
        time.sleep(delay)

    postings: list[dict] = []
    for url in job_urls:
        try:
            r = client.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            tag = soup.find("script", type="application/ld+json")
            if not tag:
                continue
            ld = json.loads(tag.string)
            if ld.get("@type") != "JobPosting":
                continue
            org = (ld.get("hiringOrganization") or {}).get("name")
            addr = ((ld.get("jobLocation") or {}).get("address") or {})
            loc = _strip_html(addr.get("streetAddress") or addr.get("addressLocality") or "Nepal")
            jid = re.search(r"/(\d{4,})-", url)
            postings.append({
                "posting_id": f"ku_{jid.group(1) if jid else abs(hash(url)) % 10**6}",
                "source": "kumarijobs",
                "tier": "nepal",
                "title": _strip_html(ld.get("title"))[:150],
                "employer": (_strip_html(org)[:100] or None),
                "location": loc[:100] or "Nepal",
                "skills_required": [],   # JSON-LD carries no discrete skills list
                "skills_preferred": [],
                "experience_years_min": _exp_years(ld.get("experienceRequirements")),
                "salary_min_npr": None,
                "salary_max_npr": None,
                "description": _strip_html(ld.get("description"))[:900],
                "posted_date": (ld.get("datePosted") + "T00:00:00") if ld.get("datePosted") else None,
                "collected_date": datetime.now().isoformat(timespec="seconds"),
                "source_url": url,
                "is_synthetic": False,
            })
        except Exception:
            continue
        time.sleep(delay)
    return postings


def _fetch_merojob(client, min_jobs: int, delay: float) -> dict[int, dict]:
    """Return {job_id: raw_job} for tech roles, deduped across search terms."""
    found: dict[int, dict] = {}

    def harvest(params: dict):
        url = MEROJOB_API
        first = True
        pages = 0
        while url and pages < 6:
            r = client.get(url, headers=HEADERS, params=params if first else None, timeout=30)
            first = False
            if r.status_code != 200:
                break
            data = r.json()
            for j in data.get("results", []):
                jid = j.get("id")
                if jid and jid not in found and j.get("is_published") and _is_tech(j):
                    found[jid] = j
            url = data.get("next")
            pages += 1
            time.sleep(delay)

    # 1) full listing, filtered to tech
    harvest({"page_size": 100})
    # 2) targeted tech searches to catch anything missed
    for term in TECH_TERMS:
        if len(found) >= min_jobs * 3:
            break
        harvest({"q": term, "page_size": 50})
        time.sleep(delay)
    return found


@app.command()
def main(
    min_jobs: int = typer.Option(30, "--min-jobs", help="Warn if fewer real jobs than this"),
    delay: float = typer.Option(0.5, "--delay"),
    out_dir: Path = typer.Option(Path("data/manual_collection/merojob"), "--out-dir"),
) -> None:
    import httpx

    from drona.data_pipeline.scrapers import manual_loader
    base = out_dir.parent

    total = 0
    with httpx.Client(timeout=40, follow_redirects=True) as client:
        # MeroJob (rich API: skills + salary)
        typer.echo("collecting real Nepali tech jobs from MeroJob API ...")
        merojob = [_to_posting(j) for j in _fetch_merojob(client, min_jobs, delay).values()]
        _write_source(base / "merojob", "merojob_real_postings.json",
                      "merojob_placeholder_postings.json", merojob, manual_loader)
        total += len(merojob)

        # KumariJob (schema.org JSON-LD)
        typer.echo("collecting real Nepali tech jobs from KumariJob ...")
        kumari = _fetch_kumarijob(client, delay)
        _write_source(base / "kumarijobs", "kumarijob_real_postings.json",
                      "kumarijob_placeholder_postings.json", kumari, manual_loader)
        total += len(kumari)

    # retire remaining placeholder files from the other portals
    for portal in ("jobsnepal", "internsathi", "linkedin"):
        for ph in (base / portal).glob("*placeholder*.json"):
            ph.unlink()
            typer.echo(f"  removed {ph.name} (placeholder)")

    typer.secho(f"\n{total} REAL Nepali tech postings collected (MeroJob {len(merojob)} + "
                f"KumariJob {len(kumari)}).", fg=typer.colors.GREEN, bold=True)
    if total < min_jobs:
        typer.secho(f"Note: {total} tech jobs live right now (Nepal's tech market is small "
                    "on any given day). Re-run later to accumulate more.",
                    fg=typer.colors.YELLOW)
    typer.echo("\nNext:\n  python scripts/prepare_training_data.py --skip-onet"
               "\n  python scripts/ingest_data.py")


def _write_source(sdir, out_name, placeholder_name, postings, manual_loader):
    sdir.mkdir(parents=True, exist_ok=True)
    out_file = sdir / out_name
    out_file.write_text(json.dumps(postings, ensure_ascii=False, indent=2), encoding="utf-8")
    loaded = manual_loader.load_file(out_file)
    ph = sdir / placeholder_name
    if ph.exists():
        ph.unlink()
    employers = sorted({p["employer"] for p in postings if p.get("employer")})
    with_sal = sum(1 for p in postings if p.get("salary_min_npr"))
    typer.echo(f"  {len(postings)} postings ({len(loaded)} schema-valid, {with_sal} w/ salary, "
               f"{len(employers)} employers) -> {out_file}")


if __name__ == "__main__":
    app()
