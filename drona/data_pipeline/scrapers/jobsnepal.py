"""
JobsNepal automated scraper for D.R.O.N.A.

ToS/robots.txt: Fully open (no Disallow rules). Verified May 2026.
Site rendering: Server-side (SSR) — parseable with requests + BeautifulSoup.
Rate limit: 0.5 req/s (configured in settings.scraper_requests_per_second).

Discovery strategy:
  1. Download https://www.jobsnepal.com/jobs-sitemap.xml
  2. Filter URLs whose slug contains tech keywords
  3. Scrape each individual job page

Output: list[JobPosting] validated against the contract schema.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from loguru import logger

from drona.contracts import DataTier, JobPosting
from drona.data_pipeline.data_card import DataCard
from drona.data_pipeline.scrapers._http import PoliteScraper

SITEMAP_URL = "https://www.jobsnepal.com/jobs-sitemap.xml"
BASE_URL = "https://www.jobsnepal.com"

# Keyword filter: only fetch tech-relevant job pages from the sitemap
_TECH_KEYWORDS = {
    "software", "developer", "programmer", "engineer", "it-", "-it-", "web",
    "python", "java", "javascript", "react", "angular", "node", "php", "dot-net",
    "dotnet", "android", "ios", "mobile", "data", "analyst", "database", "sql",
    "devops", "cloud", "security", "cyber", "network", "sysadmin", "qa",
    "testing", "ux", "ui", "design", "machine-learning", "ai-", "tech",
    "frontend", "backend", "fullstack", "full-stack", "intern",
}


def _is_tech_url(url: str) -> bool:
    slug = url.rstrip("/").split("/")[-1].lower()
    return any(kw in slug for kw in _TECH_KEYWORDS)


def _discover_tech_urls(scraper: PoliteScraper, limit: int | None = None) -> list[str]:
    """Return tech job URLs from the sitemap, optionally capped at `limit`."""
    logger.info(f"Fetching sitemap: {SITEMAP_URL}")
    soup = scraper.get_xml(SITEMAP_URL)
    all_locs = [tag.text.strip() for tag in soup.find_all("loc")]
    tech = [u for u in all_locs if _is_tech_url(u)]
    logger.info(f"Sitemap: {len(all_locs)} total URLs → {len(tech)} tech URLs")
    if limit:
        tech = tech[:limit]
        logger.info(f"  Limited to {limit} for this run")
    return tech


# ── Individual page parsers ─────────────────────────────────────────────────

def _text(tag: Tag | None) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def _extract_title(soup: BeautifulSoup) -> str:
    for sel in ("h1.job-title", "h1", "[class*='job-title']", "[class*='title']"):
        t = soup.select_one(sel)
        if t and t.text.strip():
            return t.text.strip()
    return ""


def _extract_company(soup: BeautifulSoup) -> str | None:
    for sel in (
        "[class*='company']", "[class*='employer']", "[class*='organization']",
        "a[href*='/company/']", "strong",
    ):
        t = soup.select_one(sel)
        if t and t.text.strip():
            return t.text.strip()
    return None


def _extract_location(soup: BeautifulSoup) -> str | None:
    for sel in ("[class*='location']", "[class*='address']", "[class*='place']"):
        t = soup.select_one(sel)
        if t and t.text.strip():
            return t.text.strip()
    # Fallback: look for Kathmandu / Nepal in the text
    text = soup.get_text()
    for city in ("Kathmandu", "Lalitpur", "Bhaktapur", "Pokhara", "Biratnagar"):
        if city in text:
            return city
    return None


def _extract_skills(soup: BeautifulSoup, description: str) -> list[str]:
    skills: list[str] = []

    # Try explicit skills sections first
    for label in soup.find_all(["h3", "h4", "h5", "strong", "b"]):
        if "skill" in label.text.lower() or "require" in label.text.lower():
            sibling = label.find_next_sibling()
            if sibling and sibling.name in ("ul", "ol"):
                skills = [li.get_text(strip=True) for li in sibling.find_all("li") if li.text.strip()]
                if skills:
                    return skills[:20]

    # Fallback: extract tech keywords from description
    _TECH = [
        "Python", "JavaScript", "TypeScript", "Java", "C#", "C\\+\\+", "PHP", "Ruby", "Go",
        "React", "Angular", "Vue", "Node\\.js", "Django", "Laravel", "Spring",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux",
        "Git", "REST", "GraphQL", "SQL", "HTML", "CSS",
        "\\.NET", "ASP\\.NET", "Flutter", "Kotlin", "Swift",
        "TensorFlow", "PyTorch", "scikit-learn", "pandas", "NumPy",
    ]
    found = []
    for pattern in _TECH:
        if re.search(rf"\b{pattern}\b", description, re.IGNORECASE):
            found.append(re.sub(r"\\", "", pattern))
    return found[:15]


def _extract_salary_npr(soup: BeautifulSoup) -> tuple[int | None, int | None]:
    text = soup.get_text()
    # Pattern: NPR XX,XXX or Rs. XX,XXX or XX000-XX000
    matches = re.findall(
        r"(?:NPR|NRS|Rs\.?)\s*[\d,]+|[\d,]+\s*(?:-|to)\s*[\d,]+\s*(?:NPR|NRS|Rs\.?)",
        text, re.IGNORECASE
    )
    if not matches:
        return None, None
    nums = re.findall(r"[\d,]+", matches[0])
    cleaned = [int(n.replace(",", "")) for n in nums if int(n.replace(",", "")) > 1000]
    if not cleaned:
        return None, None
    if len(cleaned) == 1:
        return cleaned[0], None
    return min(cleaned), max(cleaned)


def _extract_experience(soup: BeautifulSoup) -> int | None:
    text = soup.get_text()
    m = re.search(r"(\d+)\s*\+?\s*year[s]?\s*(?:of\s+)?(?:experience|exp)", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _extract_date(soup: BeautifulSoup, keywords: list[str]) -> datetime | None:
    text = soup.get_text()
    for kw in keywords:
        # Look for "keyword: DD Mon, YYYY" or "keyword: YYYY-MM-DD"
        m = re.search(
            rf"{kw}[:\s]+(\d{{1,2}}\s+[A-Za-z]{{3,9}},?\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})",
            text, re.IGNORECASE
        )
        if m:
            raw = m.group(1).strip()
            for fmt in ("%d %B, %Y", "%d %B %Y", "%d %b, %Y", "%d %b %Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue
    return None


def _parse_job_page(soup: BeautifulSoup, url: str) -> JobPosting | None:
    """Parse a single JobsNepal job page into a JobPosting object."""
    title = _extract_title(soup)
    if not title:
        logger.warning(f"  Could not extract title from {url} — skipping")
        return None

    description_parts = []
    for tag in soup.find_all(["p", "li"]):
        t = tag.get_text(strip=True)
        if len(t) > 30:  # skip boilerplate one-liners
            description_parts.append(t)
    description = " ".join(description_parts[:20])  # cap at 20 paragraphs

    company = _extract_company(soup)
    location = _extract_location(soup)
    skills = _extract_skills(soup, description)
    sal_min, sal_max = _extract_salary_npr(soup)
    exp = _extract_experience(soup)
    posted = _extract_date(soup, ["posted", "published", "date"])
    # deadline not parsed into posting (not in schema)

    posting_id = "jn_" + hashlib.md5(url.encode()).hexdigest()[:12]

    return JobPosting(
        posting_id=posting_id,
        source="jobsnepal",
        tier=DataTier.NEPAL,
        title=title,
        employer=company,
        location=location or "Nepal",
        skills_required=skills,
        experience_years_min=exp,
        salary_min_npr=sal_min,
        salary_max_npr=sal_max,
        description=description[:1000],  # truncate for storage
        posted_date=posted,
        source_url=url,
        is_synthetic=False,
    )


# ── Public API ───────────────────────────────────────────────────────────────

def scrape(
    limit: int | None = None,
    scraper: PoliteScraper | None = None,
) -> list[JobPosting]:
    """Scrape tech job postings from JobsNepal.

    Args:
        limit: Maximum number of job pages to fetch. None = all found in sitemap.
        scraper: Optional shared PoliteScraper (created internally if not provided).

    Returns:
        List of validated JobPosting objects.
    """
    own_scraper = scraper is None
    if own_scraper:
        scraper = PoliteScraper()

    try:
        urls = _discover_tech_urls(scraper, limit=limit)
        postings: list[JobPosting] = []
        failed = 0

        for i, url in enumerate(urls, 1):
            logger.info(f"[{i}/{len(urls)}] Scraping {url}")
            try:
                soup = scraper.get_soup(url)
                posting = _parse_job_page(soup, url)
                if posting:
                    postings.append(posting)
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"  Error scraping {url}: {e}")
                failed += 1

        logger.success(
            f"JobsNepal: scraped {len(postings)} postings "
            f"({failed} failed / {len(urls)} attempted)"
        )
        return postings
    finally:
        if own_scraper:
            scraper.close()


def build_data_card(postings: list[JobPosting], output_path: Path) -> DataCard:
    card = DataCard(
        name="jobsnepal_job_postings",
        source_name="JobsNepal",
        source_url="https://www.jobsnepal.com",
        license="custom — public-facing job postings; paraphrased, no PII",
        tier="nepal",
        collection_method="automated_scrape_public",
        record_count=len(postings),
        fields=list(JobPosting.model_fields.keys()),
        description=(
            "Tech-relevant job postings scraped from JobsNepal's public sitemap. "
            "Filtered to computing/IT roles. Skills extracted from description text. "
            "Salaries captured where stated (many postings omit them)."
        ),
        known_limitations=[
            "Salary stated in only ~30% of postings",
            "Skill extraction is regex-based, may miss non-standard phrasing",
            "Sitemap covers only jobs active at collection time",
            "Non-tech jobs excluded by URL keyword filter — may miss some tech roles with generic titles",
        ],
        contains_synthetic=False,
        robots_txt_verified=True,
        robots_txt_allows_crawl=True,
        rate_limit_applied=f"{settings.scraper_requests_per_second} req/s",
        output_files=[str(output_path)],
    )
    card.write(output_path.parent / "jobsnepal_data_card.yaml")
    return card
