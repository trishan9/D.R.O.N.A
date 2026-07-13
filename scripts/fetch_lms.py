"""Sync YOUR OWN course content from the c4mpus learning platform into D.R.O.N.A.

The platform's content lives behind a login, so this is an **offline authenticated
sync**: you authenticate once with your own browser session, the content is
fetched and written into `data/raw/curriculum/`, and from then on the AI cites it
like any other curriculum source. Credentials never touch the advising request
path, and nothing is fetched at question time.

Only sync material your own account is entitled to see.

--------------------------------------------------------------------------------
USAGE - direct login (simplest)
--------------------------------------------------------------------------------
    python scripts/fetch_lms.py --login -u <student-id> -p <password>

This logs in via POST /verification/login, lists your enrolled modules
(/users/my-learnings), and for each module downloads the weekly lessons and
their full content (/lessons/<slug>/weekly/{public,private} + read-only bodies).
Omit -p to be prompted without echoing the password.

Alternatives:
    python scripts/fetch_lms.py --token "eyJhbGci..."          # existing token
    python scripts/fetch_lms.py --curl-file lms_request.txt    # replay a browser request
    python scripts/fetch_lms.py --login -u ID -p PW --modules mine.txt  # subset

Afterwards:
    python scripts/prepare_training_data.py --skip-onet
    python scripts/ingest_data.py
"""

from __future__ import annotations

import json
import re
import shlex
import sys
import time
from datetime import date
from pathlib import Path

import typer

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = typer.Typer(help=__doc__)

API = "https://api.c4mpus.com"


# ── cURL parsing ──────────────────────────────────────────────────────────────

def parse_curl(text: str) -> tuple[str, dict[str, str]]:
    """Extract (url, headers) from a DevTools 'Copy as cURL' blob."""
    cleaned = text.replace("\\\n", " ").replace("^\n", " ").replace("`\n", " ")
    try:
        tokens = shlex.split(cleaned)
    except ValueError:
        tokens = cleaned.split()

    url, headers = "", {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("-H", "--header") and i + 1 < len(tokens):
            raw = tokens[i + 1]
            if ":" in raw:
                k, v = raw.split(":", 1)
                headers[k.strip()] = v.strip()
            i += 2
            continue
        if t in ("-b", "--cookie") and i + 1 < len(tokens):
            headers["Cookie"] = tokens[i + 1]
            i += 2
            continue
        if t.startswith("http"):
            url = t
        i += 1
    return url, headers


def strip_html(raw: str) -> str:
    """HTML -> readable text (the API returns rich-text lesson bodies)."""
    if "<" not in raw:
        return raw.strip()
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw).strip()


# ── HTTP + the real c4mpus API chain ──────────────────────────────────────────
#
# Endpoints (discovered from the c4mpus SPA bundle):
#   POST /verification/login               {username, password} -> {token, user}
#   GET  /users/my-learnings               -> the student's enrolled modules
#   GET  /lessons/<slug>/weekly/public     -> week-grouped lessons (id + title)
#   GET  /lessons/<slug>/weekly/private    -> incl. private lessons/quizzes
#   GET  /lessons/read-only/<lessonId>     -> full lesson body (lessonContents, HTML)

LOGIN_ENDPOINT = f"{API}/verification/login"
LEARNINGS_ENDPOINT = f"{API}/users/my-learnings"
WEEKLY_ENDPOINT = f"{API}/lessons/{{slug}}/weekly/{{vis}}"
LESSON_ENDPOINT = f"{API}/lessons/read-only/{{lesson_id}}"


def _safe_name(slug: str) -> str:
    """Filesystem-safe stem (Windows forbids : ? * etc.)."""
    return re.sub(r"[^A-Za-z0-9]+", "_", slug).strip("_")


def _get(client, url: str, headers: dict):
    return client.get(url, headers=headers, timeout=60, follow_redirects=True)


def login(client, username: str, password: str, headers: dict) -> str:
    """POST /verification/login -> Bearer token (raises on failure)."""
    r = client.post(LOGIN_ENDPOINT, headers={**headers, "Content-Type": "application/json"},
                    json={"username": username, "password": password}, timeout=40)
    if r.status_code != 200:
        raise RuntimeError(f"login HTTP {r.status_code}: {r.text[:160]}")
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"login rejected: {data.get('message') or data}")
    tok = data.get("token") or (data.get("user") or {}).get("token")
    if isinstance(tok, dict):
        tok = tok.get("access_token") or tok.get("accessToken")
    if not tok:
        raise RuntimeError("login succeeded but no token in response")
    u = data.get("user", {})
    typer.secho(f"logged in as {u.get('firstname','?')} {u.get('lastname','')} "
                f"| {u.get('course','?')}", fg=typer.colors.GREEN)
    return tok


def list_my_modules(client, headers: dict) -> list[tuple[str, str]]:
    """GET /users/my-learnings -> [(slug, title), ...]."""
    r = _get(client, LEARNINGS_ENDPOINT, headers)
    r.raise_for_status()
    data = r.json()

    # Walk the module objects so slug<->title pairing is exact (order-independent).
    titles: dict[str, str] = {}
    slugs: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            s = node.get("moduleSlug")
            if isinstance(s, str):
                slugs.add(s)
                t = node.get("moduleTitle")
                if isinstance(t, str) and t.strip():
                    titles[s] = t.strip()
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return sorted((s, titles.get(s, s.replace("-", " ").title())) for s in slugs)


def _week_key(num) -> tuple[int, str]:
    """Sortable key for week values that arrive as int, "1", "Week 3", or None."""
    if num is None:
        return (9999, "")
    m = re.search(r"\d+", str(num))
    return (int(m.group()) if m else 9998, str(num))


def fetch_weekly(client, slug: str, headers: dict) -> dict:
    """Merge public + private weekly lesson listings for a module."""
    merged: dict = {}
    for vis in ("public", "private"):
        try:
            r = _get(client, WEEKLY_ENDPOINT.format(slug=slug, vis=vis), headers)
            if r.status_code != 200:
                continue
            for wk in r.json().get("lessons", []):
                num = wk.get("week")
                bucket = merged.setdefault(_week_key(num), {"week": num, "lessons": []})
                seen = {ls.get("_id") for ls in bucket["lessons"]}
                for ls in wk.get("lessons", []):
                    if ls.get("_id") not in seen and ls.get("lessonTitle"):
                        bucket["lessons"].append(ls)
        except Exception:
            continue
    return {"weeks": [merged[k] for k in sorted(merged)]}


def _file_links(html: str) -> list[str]:
    """Attached-document URLs inside lesson HTML (href/src), PDFs first.

    Much of the real teaching material is uploaded as PDF lab worksheets and
    lecture decks; images (.png/.jpg slide exports) are skipped - they'd need
    OCR, which is out of scope here.
    """
    urls = re.findall(r'(?:href|src)="([^"]+)"', html)
    out, seen = [], set()
    for u in urls:
        u = u.strip()
        low = u.lower()
        if not low.startswith("http"):
            continue
        if low.endswith(".pdf") and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _extract_pdf_text(client, url: str, headers: dict, max_pages: int = 40,
                      max_bytes: int = 15_000_000) -> str:
    """Download a PDF and pull its text (digitally-created PDFs only)."""
    import io

    from pypdf import PdfReader

    try:
        r = client.get(url, headers={"Authorization": headers.get("Authorization", ""),
                                     "User-Agent": headers.get("User-Agent", "")},
                       timeout=90, follow_redirects=True)
        if r.status_code != 200 or "pdf" not in r.headers.get("content-type", "").lower():
            return ""
        if len(r.content) > max_bytes:
            return ""
        reader = PdfReader(io.BytesIO(r.content))
        pages = [(p.extract_text() or "") for p in reader.pages[:max_pages]]
        text = re.sub(r"\n{2,}", "\n", "\n".join(pages)).strip()
        return text
    except Exception:
        return ""


def fetch_lesson_body(client, lesson_id: str, headers: dict,
                      with_files: bool = True, file_cap: int = 6) -> str:
    """GET /lessons/read-only/<id> -> inline text + extracted PDF attachments."""
    try:
        r = _get(client, LESSON_ENDPOINT.format(lesson_id=lesson_id), headers)
        if r.status_code != 200:
            return ""
        lesson = r.json().get("lesson", {})
        raw = str(lesson.get("lessonContents", ""))
        text = strip_html(raw)
        if with_files:
            for url in _file_links(raw)[:file_cap]:
                pdf_text = _extract_pdf_text(client, url, headers)
                if len(pdf_text) > 80:   # skip scanned/empty PDFs
                    name = re.sub(r".*/", "", url).split("_")[0]
                    text += f"\n\n[Attached document: {name}]\n{pdf_text}"
        return text
    except Exception:
        return ""


# Real Coventry codes end in CEM / COM / IAE. Match those strictly so random
# slug suffixes (e.g. "-lgfb2876-") are never mistaken for a module code.
_CODE_RE = r"\b(st[a]?\d{3,4}(?:cem|iae)|sp\d{4}c[o0]m)\b"


def _module_code(slug: str, title: str) -> str:
    """Coventry module code - from the title (reliable), else a UNIQUE fallback."""
    for src in (title, slug):
        m = re.search(_CODE_RE, src, re.I)
        if m:
            return m.group(1).upper()
    # No real code: use the FULL safe slug so similar modules never collide
    # (e.g. programming-and-algorithms vs programming-and-algorithms-1).
    return "MOD-" + _safe_name(slug).upper()


def module_to_markdown(slug: str, title: str, weekly: dict, bodies: dict,
                       programme: str, course: str) -> str:
    code = _module_code(slug, title)
    lines = [
        "<!-- REAL module content synced from the c4mpus learning platform",
        f"     endpoint: {WEEKLY_ENDPOINT.format(slug=slug, vis='public')}",
        f"     synced: {date.today().isoformat()} via scripts/fetch_lms.py (authenticated)",
        "     Authenticated content - keep in a PRIVATE repo if not publicly licensed. -->",
        "",
        f"Module Code: {code}",
        f"Module Title: {title}",
        f"Programme: {programme}",
        f"Course: {course}",
        "",
        "Module Description:",
    ]

    # description = the first substantial lesson body
    desc = next((b for b in bodies.values() if len(b) > 60), "")
    lines.append((desc[:600] + "...") if desc else
                 f"Weekly learning content for {title}.")
    lines.append("")
    lines.append("Weekly Learning Content:")

    skills: set[str] = set()
    for wk in weekly.get("weeks", []):
        lines.append(f"\n### Week {wk['week']}")
        for ls in wk["lessons"]:
            t = ls.get("lessonTitle", "").strip()
            if not t:
                continue
            lines.append(f"\n**{t}**")
            body = bodies.get(ls.get("_id"), "")
            if body:
                lines.append(body[:1500])
            for kw in _SKILL_HINTS:
                if kw.lower() in (t + " " + body).lower():
                    skills.add(kw)

    if skills:
        lines.append("\nSkills Developed:")
        lines.extend(f"- {s}" for s in sorted(skills))

    lines.append("")
    lines.append(f"This module is part of the {course} programme "
                 "(Softwarica College of IT & E-Commerce / Coventry University).")
    return "\n".join(lines) + "\n"


# Keyword hints so the parser's skills_developed field is populated from content.
_SKILL_HINTS = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "SQL", "NoSQL",
    "MongoDB", "MySQL", "HTML", "CSS", "React", "Angular", "Node.js", "Django",
    "Flask", "Git", "Docker", "Kubernetes", "AWS", "Machine Learning",
    "Deep Learning", "Neural Networks", "TensorFlow", "PyTorch", "Data Science",
    "Statistics", "Algorithms", "Data Structures", "Networking", "Linux",
    "Cryptography", "Penetration Testing", "Cybersecurity", "REST", "API",
    "Agile", "Testing", "UML", "OOP", "Kotlin", "Flutter", "Big Data", "Hadoop",
    "Spark", "NLP", "Computer Vision", "UX Design",
]


@app.command()
def main(
    username: str = typer.Option("", "--username", "-u",
                                 help="Campus login (student ID); prompts if omitted with --login"),
    password: str = typer.Option("", "--password", "-p", help="Campus password"),
    do_login: bool = typer.Option(False, "--login",
                                  help="Log in with --username/--password to get a fresh token"),
    token: str = typer.Option("", "--token", help="Existing Bearer token (skip login)"),
    curl_file: Path = typer.Option(None, "--curl-file",
                                   help="DevTools 'Copy as cURL' blob (alternative to login)"),
    modules: Path = typer.Option(None, "--modules",
                                 help="Only these module slugs (one per line); default = all enrolled"),
    programme: str = typer.Option("software_engineering", "--programme",
                                  help="software_engineering | ethical_hacking | csai"),
    out_dir: Path = typer.Option(Path("data/raw/curriculum"), "--out-dir"),
    delay: float = typer.Option(0.3, "--delay", help="Seconds between requests"),
    max_lessons: int = typer.Option(120, "--max-lessons",
                                    help="Safety cap on lesson-body fetches PER MODULE"),
    with_files: bool = typer.Option(True, "--with-files/--no-files",
                                    help="Download linked PDFs and fold their text in "
                                         "(much real content lives in PDF worksheets/decks)"),
) -> None:
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://c4mpus.com",
        "Referer": "https://c4mpus.com/",
    }
    course = "BSc (Hons) Computing"

    with httpx.Client() as client:
        # 1. authenticate
        if curl_file:
            _, curl_headers = parse_curl(curl_file.read_text(encoding="utf-8"))
            headers.update(curl_headers)
            typer.echo(f"replaying {len(curl_headers)} header(s) from {curl_file}")
        elif do_login or (username and password):
            if not username:
                username = typer.prompt("Campus username (student ID)")
            if not password:
                password = typer.prompt("Campus password", hide_input=True)
            tok = login(client, username, password, headers)
            headers["Authorization"] = f"Bearer {tok}"
        elif token:
            headers["Authorization"] = f"Bearer {token.removeprefix('Bearer ').strip()}"
        else:
            typer.secho("No credentials. Use --login -u <id> -p <pw>, or --token, "
                        "or --curl-file.", fg=typer.colors.RED)
            raise typer.Exit(1)

        # label from JWT claims when available (public claims only, no verification)
        auth = headers.get("Authorization", "")
        if auth.count(".") >= 2:
            try:
                import base64

                part = auth.split()[-1].split(".")[1]
                claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
                course = claims.get("course", course)
            except Exception:
                pass

        # 2. module list
        wanted = None
        if modules and modules.exists():
            wanted = {ln.strip() for ln in modules.read_text(encoding="utf-8").splitlines()
                      if ln.strip() and not ln.startswith("#")}
        typer.echo("listing enrolled modules ...")
        catalogue = list_my_modules(client, headers)
        if wanted:
            catalogue = [(s, t) for s, t in catalogue if s in wanted]
        if not catalogue:
            typer.secho("no modules found for this account", fg=typer.colors.RED)
            raise typer.Exit(1)
        typer.echo(f"{len(catalogue)} module(s) to sync\n")

        # 3. per module: weekly listing -> lesson bodies -> markdown
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_dir = ROOT / "data" / "raw" / "lms_raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        ok, failed, lessons_fetched = 0, [], 0
        for i, (slug, title) in enumerate(catalogue):
            try:
                weekly = fetch_weekly(client, slug, headers)
                bodies: dict[str, str] = {}
                per_module = 0   # fairness cap so one huge module can't starve the rest
                for wk in weekly.get("weeks", []):
                    for ls in wk["lessons"]:
                        lid = ls.get("_id")
                        if lid and per_module < max_lessons:
                            body = fetch_lesson_body(client, lid, headers,
                                                     with_files=with_files)
                            if body:
                                bodies[lid] = body
                                lessons_fetched += 1
                                per_module += 1
                                time.sleep(delay)
                md = module_to_markdown(slug, title, weekly, bodies, programme, course)
                path = out_dir / f"lms_{_safe_name(slug)}.md"
                path.write_text(md, encoding="utf-8")
                (raw_dir / f"{_safe_name(slug)}.json").write_text(
                    json.dumps({"title": title, "weekly": weekly, "bodies": bodies},
                               ensure_ascii=False, indent=2), encoding="utf-8")
                n_les = sum(len(w["lessons"]) for w in weekly.get("weeks", []))
                ok += 1
                typer.echo(f"  [{i+1}/{len(catalogue)}] {slug}  "
                           f"({len(weekly.get('weeks', []))} weeks, {n_les} lessons, "
                           f"{len(md):,} chars)")
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    typer.secho("  401 - session expired; re-run --login for a fresh token.",
                                fg=typer.colors.RED)
                    raise typer.Exit(1) from exc
                failed.append(slug)
            except Exception as exc:
                failed.append(slug)
                typer.secho(f"  [{i+1}/{len(catalogue)}] FAILED {slug}: {exc}",
                            fg=typer.colors.RED)

    typer.secho(f"\n{ok} module(s) synced ({lessons_fetched} lesson bodies) -> {out_dir}",
                fg=typer.colors.GREEN, bold=True)
    if failed:
        typer.echo(f"failed: {', '.join(failed)}")
    typer.echo("\nNext:\n  python scripts/prepare_training_data.py --skip-onet"
               "\n  python scripts/ingest_data.py")
    typer.secho("\nNote: authenticated course material. data/raw/ is gitignored - "
                "only force-add into a PRIVATE repo.", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
