# Data Card — Nepali Job Postings (manual collection)

- **Source:** Nepali job portals (MeroJob, JobsNepal, Internsathi, Kumari Jobs)
- **License / ToS:** **Scraping prohibited** (MeroJob ToS §3.E and equivalents).
  Data is **manually collected** by the student under fair, individual review.
- **Tier:** `nepal`
- **Collection method:** **MANUAL ONLY** — curated into a JSON template
  (`data/manual_collection/`) and loaded via
  `drona/data_pipeline/scrapers/manual_loader.py`
- **Target volume:** ~150–200 postings

## Contents used
Job title, company, location, required skills, experience, and (where stated)
salary range for Nepali computing roles.

## Why it's used
The single most important **Nepal-tier** evidence: real local roles, companies, and
skill demands. Directly grounds pathway recommendations in the student's actual
market (C4) and validates the bias-mitigation framing.

## Schema (`JobPosting` contract)
`posting_id, title, company, location, skills[], experience, salary_range?,
source, tier=nepal, is_synthetic=False`

## Collection ethics (critical)
- **No automated scraping** of any portal — ToS-compliant, see `../data_ethics.md` §3.
- Per-source scraper modules are **disabled stubs** documenting the prohibition.
- No PII about applicants is collected — only public posting content.

## Limitations
- Manual collection → modest volume and possible selection bias; documented as a
  limitation. Snapshot in time (postings expire). Quantity depends on student effort.
