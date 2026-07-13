"""Fetch curriculum pages into data/raw/curriculum/ - no copy-paste needed.

Give it the module-page URLs from the campus platform (or any site) and it
downloads each one and converts it to clean Markdown that the existing
curriculum parser ingests directly. PDFs are saved as-is (the parser reads
those too).

Login-protected pages (campus LMS): log in once in your browser, copy the
Cookie header (DevTools > Network > any request > Request Headers > cookie),
and pass it with --cookie. The script only accesses pages YOUR account can
already see - it just automates the copy-paste.

Usage:
    # public pages
    python scripts/fetch_curriculum.py https://site/module1 https://site/module2

    # many URLs from a file (one per line, '#' comments allowed)
    python scripts/fetch_curriculum.py --urls-file my_modules.txt

    # login-protected campus platform
    python scripts/fetch_curriculum.py --urls-file my_modules.txt \\
        --cookie "MoodleSession=abc123; other=xyz"

Afterwards:
    python scripts/prepare_training_data.py     # re-parse + rebuild everything
"""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path

import typer

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = typer.Typer(help=__doc__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DRONA-curriculum-fetch/1.0"
_STRIP_TAGS = ["script", "style", "nav", "header", "footer", "aside", "iframe",
               "noscript", "form", "button", "svg"]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return slug[:60] or "page"


def _html_to_markdown(html: str) -> tuple[str, str]:
    """Return (title, markdown) for an HTML page, stripped of site chrome."""
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "") or "untitled"
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    # Prefer the main-content region when the page marks one.
    main = (soup.find("main") or soup.find("article")
            or soup.find(attrs={"role": "main"}) or soup.body or soup)
    md = markdownify(str(main), heading_style="ATX", bullets="-")
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return title, md


@app.command()
def main(
    urls: list[str] = typer.Argument(None, help="Module page URLs"),
    urls_file: Path = typer.Option(None, "--urls-file", help="File with one URL per line"),
    cookie: str = typer.Option("", "--cookie", help="Cookie header for login-protected pages"),
    out_dir: Path = typer.Option(Path("data/raw/curriculum"), "--out-dir"),
    delay: float = typer.Option(1.0, "--delay", help="Seconds between requests (be polite)"),
    min_chars: int = typer.Option(200, "--min-chars",
                                  help="Warn if extracted text is shorter than this"),
) -> None:
    import httpx

    all_urls: list[str] = list(urls or [])
    if urls_file:
        all_urls += [ln.strip() for ln in urls_file.read_text(encoding="utf-8").splitlines()
                     if ln.strip() and not ln.strip().startswith("#")]
    if not all_urls:
        typer.secho("No URLs given. Pass URLs as arguments or --urls-file.", fg=typer.colors.RED)
        raise typer.Exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": _UA}
    if cookie:
        headers["Cookie"] = cookie

    saved, failed = [], []
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
        for i, url in enumerate(all_urls):
            try:
                r = client.get(url)
                r.raise_for_status()
                ctype = r.headers.get("content-type", "")
                if "pdf" in ctype or url.lower().endswith(".pdf"):
                    name = _slugify(Path(url).stem) + ".pdf"
                    (out_dir / name).write_bytes(r.content)
                else:
                    title, md = _html_to_markdown(r.text)
                    if "login" in title.lower() or len(md) < min_chars:
                        typer.secho(
                            f"  WARNING: {url} looks like a login page or is nearly empty "
                            f"({len(md)} chars) - is your --cookie still valid?",
                            fg=typer.colors.YELLOW)
                    name = _slugify(title) + ".md"
                    body = (f"<!-- source: {url} | fetched: {date.today().isoformat()} "
                            f"| via scripts/fetch_curriculum.py -->\n\n# {title}\n\n{md}\n")
                    (out_dir / name).write_text(body, encoding="utf-8")
                saved.append(name)
                typer.echo(f"  [{i + 1}/{len(all_urls)}] {url} -> {out_dir / name}")
            except Exception as exc:
                failed.append(url)
                typer.secho(f"  [{i + 1}/{len(all_urls)}] FAILED {url}: {exc}",
                            fg=typer.colors.RED)
            if i < len(all_urls) - 1:
                time.sleep(delay)

    typer.secho(f"\n{len(saved)} page(s) saved to {out_dir}; {len(failed)} failed.",
                fg=typer.colors.GREEN if not failed else typer.colors.YELLOW, bold=True)
    if failed:
        typer.echo("Failed URLs (check the login cookie / try the browser save-as-PDF route):")
        for u in failed:
            typer.echo(f"  {u}")
    typer.echo("\nNext: review the files, delete any placeholder *.md you are replacing, then")
    typer.echo("  python scripts/prepare_training_data.py")


if __name__ == "__main__":
    app()
