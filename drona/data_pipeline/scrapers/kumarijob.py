"""
KumariJob scraper for D.R.O.N.A.

ToS/robots.txt (verified May 2026):
  - /search: explicitly Allow'd
  - /jobseeker*: Disallowed (jobseeker profiles - not postings)
  - /admin/, /api/: Disallowed
  - Job posting pages (e.g. /jobs/XXXX): no Disallow - allowed

Strategy:
  1. Use the /search endpoint (Allow'd) with tech keywords to get job listing pages
  2. Extract job detail page links
  3. Scrape individual job pages

Note: KumariJob uses a different URL: https://kumarijob.com/
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from bs4 import BeautifulSoup
from loguru import logger

from drona.contracts import DataTier, JobPosting
from drona.data_pipeline.data_card import DataCard
from drona.data_pipeline.scrapers._http import PoliteScraper
from drona.utils.settings import settings

BASE_URL = "https://kumarijob.com"
SEARCH_URL = "https://kumarijob.com/search"

_TECH_SEARCH_TERMS = [
    "software developer", "web developer", "python", "javascript", "java",
    "react", "angular", "node.js", "php developer", "data analyst",
    "devops", "qa engineer", "android developer", "mobile developer",
    "IT officer", "network engineer",
]

_DISALLOWED_PREFIXES = (
    "/jobseeker", "/admin/", "/api/", "/new-assets/", "/images/", "/public/assets/",
)


def _is_allowed(url: str) -> bool:
    path = url.replace(BASE_URL, "").split("?")[0]
    return not any(path.startswith(p) for p in _DISALLOWED_PREFIXES)


def _discover_job_urls(scraper: PoliteScraper, max_per_term: int = 10) -> list[str]:
    """Use the /search endpoint to discover job detail URLs."""
    all_urls: set[str] = set()

    for term in _TECH_SEARCH_TERMS:
        try:
            params = {"q": term}
            logger.info(f"  Searching KumariJob: '{term}'")
            soup = scraper.get_soup(SEARCH_URL, params=params)

            # Look for job links - typically anchors with job slugs
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.startswith("http"):
                    href = BASE_URL + href
                # Job pages tend to have numeric IDs or /job/ in path
                if ("kumarijob.com" in href and _is_allowed(href)
                        and re.search(r"/jobs?/|/vacancy/|\d{4,}", href)):
                    all_urls.add(href)
                if len(all_urls) >= max_per_term * len(_TECH_SEARCH_TERMS):
                    break
        except Exception as e:
            logger.warning(f"  KumariJob search failed for '{term}': {e}")

    logger.info(f"KumariJob: discovered {len(all_urls)} unique job URLs")
    return list(all_urls)


def _parse_page(soup: BeautifulSoup, url: str) -> JobPosting | None:
    # Title
    title = ""
    for sel in ("h1", "[class*='title']", "[class*='job-title']"):
        t = soup.select_one(sel)
        if t and t.text.strip():
            title = t.text.strip()
            break
    if not title:
        return None

    # Company
    company = None
    for sel in ("[class*='company']", "[class*='employer']", "[class*='organization']"):
        t = soup.select_one(sel)
        if t and t.text.strip():
            company = t.text.strip()
            break

    # Description
    paras = [p.get_text(strip=True) for p in soup.find_all(["p", "li"]) if len(p.get_text(strip=True)) > 25]
    description = " ".join(paras[:15])

    # Skills (keyword extraction)
    tech_kw = [
        "Python", "JavaScript", "Java", "PHP", "React", "Angular",
        "SQL", "Git", "HTML", "CSS", "Docker", "Node.js", "Linux", "AWS",
    ]
    skills = [kw for kw in tech_kw if re.search(rf"\b{re.escape(kw)}\b", description, re.IGNORECASE)]

    # Salary
    sal_text = soup.get_text()
    sal_matches = re.findall(r"(?:NPR|NRS|Rs\.?)\s*[\d,]+", sal_text, re.IGNORECASE)
    sal_nums = []
    for m in sal_matches[:2]:
        n = re.search(r"[\d,]+", m)
        if n:
            v = int(n.group().replace(",", ""))
            if v > 1000:
                sal_nums.append(v)
    sal_min = min(sal_nums) if sal_nums else None
    sal_max = max(sal_nums) if len(sal_nums) > 1 else None

    exp_m = re.search(r"(\d+)\s*\+?\s*year", sal_text, re.IGNORECASE)
    exp = int(exp_m.group(1)) if exp_m else None

    posting_id = "kj_" + hashlib.md5(url.encode()).hexdigest()[:12]

    return JobPosting(
        posting_id=posting_id,
        source="kumarijob",
        tier=DataTier.NEPAL,
        title=title,
        employer=company,
        location="Nepal",
        skills_required=skills[:12],
        experience_years_min=exp,
        salary_min_npr=sal_min,
        salary_max_npr=sal_max,
        description=description[:800],
        source_url=url,
        is_synthetic=False,
    )


def scrape(limit: int | None = None, scraper: PoliteScraper | None = None) -> list[JobPosting]:
    own = scraper is None
    if own:
        scraper = PoliteScraper()
    try:
        urls = _discover_job_urls(scraper)
        if limit:
            urls = urls[:limit]

        postings: list[JobPosting] = []
        failed = 0
        for i, url in enumerate(urls, 1):
            logger.info(f"[{i}/{len(urls)}] KumariJob: {url}")
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

        logger.success(f"KumariJob: {len(postings)} scraped, {failed} failed")
        return postings
    finally:
        if own:
            scraper.close()


def build_data_card(postings: list[JobPosting], output_path: Path) -> DataCard:
    card = DataCard(
        name="kumarijob_postings",
        source_name="KumariJob",
        source_url="https://kumarijob.com",
        license="custom - public-facing; paraphrased",
        tier="nepal",
        collection_method="automated_scrape_public",
        record_count=len(postings),
        fields=list(JobPosting.model_fields.keys()),
        description=(
            "Tech job postings from KumariJob discovered via the /search endpoint "
            "(explicitly Allow'd in robots.txt). Individual job pages scraped for details."
        ),
        known_limitations=[
            "Search-based discovery may miss postings with non-standard titles",
            "Salary stated in minority of postings",
            "JS-partial rendering may cause some fields to be empty",
        ],
        contains_synthetic=False,
        robots_txt_verified=True,
        robots_txt_allows_crawl=True,
        rate_limit_applied=f"{settings.scraper_requests_per_second} req/s",
        output_files=[str(output_path)],
    )
    card.write(output_path.parent / "kumarijob_data_card.yaml")
    return card
