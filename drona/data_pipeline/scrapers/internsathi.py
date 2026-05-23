"""
Internsathi scraper for D.R.O.N.A.

ToS/robots.txt (verified May 2026):
  - /all-opportunities: Disallowed ← do NOT use
  - /api/:             Disallowed ← do NOT use
  - Individual opportunity pages: Allowed
  - Sitemap:           https://internsathi.com/sitemap.xml → allowed

Strategy: use the sitemap (which is explicitly allowed) to discover
individual opportunity URLs, then scrape each page. Skip disallowed paths.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from loguru import logger

from drona.contracts import DataTier, JobPosting
from drona.data_pipeline.data_card import DataCard
from drona.data_pipeline.scrapers._http import PoliteScraper
from drona.utils.settings import settings

SITEMAP_URL = "https://internsathi.com/sitemap.xml"
BASE_URL = "https://internsathi.com"

# Disallowed paths per robots.txt — never request these
_DISALLOWED_PREFIXES = (
    "/dashboard/", "/api/", "/onboarding/", "/checkout/",
    "/verify/", "/login/", "/403", "/all-opportunities",
    "/private-internship", "/assessment/",
)

_TECH_KEYWORDS = {
    "software", "developer", "engineer", "web", "python", "java", "react",
    "angular", "node", "php", "data", "database", "it", "tech", "design",
    "ux", "ui", "devops", "cloud", "android", "ios", "ml", "ai", "intern",
    "programming", "frontend", "backend", "fullstack", "qa", "testing",
}


def _is_allowed(url: str) -> bool:
    path = url.replace(BASE_URL, "")
    return not any(path.startswith(p) for p in _DISALLOWED_PREFIXES)


def _is_tech_url(url: str) -> bool:
    slug = url.rstrip("/").split("/")[-1].lower()
    return any(kw in slug for kw in _TECH_KEYWORDS)


def _discover_opportunity_urls(scraper: PoliteScraper, limit: int | None = None) -> list[str]:
    logger.info(f"Fetching sitemap: {SITEMAP_URL}")
    soup = scraper.get_xml(SITEMAP_URL)
    all_locs = [tag.text.strip() for tag in soup.find_all("loc")]

    allowed = [u for u in all_locs if _is_allowed(u)]
    tech = [u for u in allowed if _is_tech_url(u)]

    logger.info(
        f"Sitemap: {len(all_locs)} total → {len(allowed)} allowed "
        f"→ {len(tech)} tech-relevant"
    )
    if limit:
        tech = tech[:limit]
    return tech


def _parse_page(soup: BeautifulSoup, url: str) -> JobPosting | None:
    # Title
    title = ""
    for sel in ("h1", "[class*='title']", "[class*='position']"):
        t = soup.select_one(sel)
        if t and t.text.strip():
            title = t.text.strip()
            break
    if not title:
        logger.warning(f"  No title found at {url}")
        return None

    # Company
    company = None
    for sel in ("[class*='company']", "[class*='organization']", "[class*='employer']"):
        t = soup.select_one(sel)
        if t and t.text.strip():
            company = t.text.strip()
            break

    # Location
    location = "Nepal"  # Internsathi is Nepal-focused
    for sel in ("[class*='location']", "[class*='address']"):
        t = soup.select_one(sel)
        if t and t.text.strip():
            location = t.text.strip()
            break

    # Description
    text_blocks = [
        p.get_text(strip=True) for p in soup.find_all(["p", "li"])
        if len(p.get_text(strip=True)) > 30
    ]
    description = " ".join(text_blocks[:15])

    # Skills
    skills: list[str] = []
    for label in soup.find_all(["strong", "b", "h4", "h5"]):
        if "skill" in label.text.lower():
            nxt = label.find_next_sibling()
            if nxt and nxt.name in ("ul", "ol"):
                skills = [li.get_text(strip=True) for li in nxt.find_all("li")][:15]
                break
    if not skills:
        _TECH = [
            "Python", "JavaScript", "Java", "PHP", "React", "Angular", "Node",
            "Django", "Laravel", "SQL", "Git", "HTML", "CSS", "Docker",
        ]
        for kw in _TECH:
            if re.search(rf"\b{kw}\b", description, re.IGNORECASE):
                skills.append(kw)
        skills = skills[:10]

    posting_id = "is_" + hashlib.md5(url.encode()).hexdigest()[:12]

    return JobPosting(
        posting_id=posting_id,
        source="internsathi",
        tier=DataTier.NEPAL,
        title=title,
        employer=company,
        location=location,
        skills_required=skills,
        description=description[:800],
        source_url=url,
        is_synthetic=False,
    )


def scrape(limit: int | None = None, scraper: PoliteScraper | None = None) -> list[JobPosting]:
    """Scrape tech internship/job postings from Internsathi.

    Args:
        limit: Cap on number of pages to scrape.
        scraper: Optional shared PoliteScraper.

    Returns:
        List of JobPosting objects (all NEPAL tier, internship-focused).
    """
    own = scraper is None
    if own:
        scraper = PoliteScraper()
    try:
        urls = _discover_opportunity_urls(scraper, limit=limit)
        postings: list[JobPosting] = []
        failed = 0

        for i, url in enumerate(urls, 1):
            logger.info(f"[{i}/{len(urls)}] {url}")
            try:
                soup = scraper.get_soup(url)
                p = _parse_page(soup, url)
                if p:
                    postings.append(p)
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"  Error at {url}: {e}")
                failed += 1

        logger.success(f"Internsathi: {len(postings)} scraped, {failed} failed")
        return postings
    finally:
        if own:
            scraper.close()


def build_data_card(postings: list[JobPosting], output_path: Path) -> DataCard:
    card = DataCard(
        name="internsathi_postings",
        source_name="Internsathi",
        source_url="https://internsathi.com",
        license="custom — public-facing; paraphrased",
        tier="nepal",
        collection_method="automated_scrape_public",
        record_count=len(postings),
        fields=list(JobPosting.model_fields.keys()),
        description=(
            "Tech internship and entry-level job postings from Internsathi, "
            "Nepal's primary internship platform. Discovered via sitemap "
            "(individual pages only; /all-opportunities was disallowed per robots.txt)."
        ),
        known_limitations=[
            "Internship-heavy — fewer full-time senior roles",
            "/all-opportunities disallowed; only sitemap-discoverable pages collected",
            "Salary rarely stated in internship postings",
        ],
        contains_synthetic=False,
        robots_txt_verified=True,
        robots_txt_allows_crawl=True,
        rate_limit_applied=f"{settings.scraper_requests_per_second} req/s",
        output_files=[str(output_path)],
    )
    card.write(output_path.parent / "internsathi_data_card.yaml")
    return card
