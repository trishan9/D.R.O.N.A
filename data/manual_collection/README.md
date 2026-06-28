# Manual Job Posting Collection - Template

You collect job postings **manually** (as a normal user reading the site) and paste them into JSON files using this schema. This protects you legally: no automated scraping, no ToS violation, no anti-bot games.

## How to collect

1. Visit a Nepali job portal (MeroJob, JobsNepal, Internsathi, Kumari Jobs).
2. Search for tech-relevant terms: "developer", "python", "javascript", "data analyst", "QA", "designer", "cybersecurity", "intern".
3. Open a posting that looks like a typical entry-level / junior role suitable for a new graduate.
4. Copy the key fields into a new JSON entry in the appropriate file under `data/manual_collection/<source>/`.
5. Note the URL and date so the provenance is traceable.

## Target sample sizes (per source)

| Source | Target | Why |
|---|---|---|
| MeroJob | 50 | Largest Nepali tech job board |
| JobsNepal | 40 | Strong tech coverage |
| Internsathi | 30 | Internship-focused, matches our target users |
| Kumari Jobs | 30 | Diversity of employer base |
| LinkedIn (manual, no scraping) | 30 | International + Nepal-aware roles |
| **Total** | **~180** | Enough for meaningful retrieval and salary range stats |

Time estimate: **2-3 minutes per posting × 180 = ~6-9 hours total**, spread across 3-4 days.

## JSON template per posting

Create a file like `data/manual_collection/merojob/postings_001-050.json` containing a list:

```json
[
  {
    "posting_id": "mj_2026_001",
    "source": "merojob",
    "tier": "nepal",
    "title": "Junior Python Developer",
    "employer": "Leapfrog Technology",
    "location": "Kathmandu",
    "skills_required": ["Python", "Django", "REST APIs", "PostgreSQL"],
    "skills_preferred": ["Docker", "AWS"],
    "experience_years_min": 0,
    "salary_min_npr": 30000,
    "salary_max_npr": 50000,
    "description": "Looking for a junior developer to join our team building web applications for international clients. Fresh graduates welcome. Will work in a team of 5 engineers.",
    "posted_date": "2026-05-10T00:00:00",
    "source_url": "https://merojob.com/example-url-here",
    "is_synthetic": false
  },
  {
    "posting_id": "mj_2026_002",
    "source": "merojob",
    "tier": "nepal",
    "title": "Frontend Developer Intern",
    ...
  }
]
```

## Field guidance

- **posting_id**: `<source_prefix>_<year>_<sequence>`. Prefixes: `mj` (merojob), `jn` (jobsnepal), `is` (internsathi), `kj` (kumarijobs), `li` (linkedin_manual).
- **salary_min_npr / salary_max_npr**: leave as `null` if not stated. Don't guess.
- **skills_required / skills_preferred**: use the exact terms in the posting where possible. Don't normalize yet - the pipeline does that.
- **description**: 2-4 sentences capturing role essence. Don't copy the full posting - that's potentially infringing. Paraphrase or extract the critical 2-3 sentences.
- **source_url**: critical for provenance. If you forget this, the entry is academically less defensible.
- **is_synthetic**: always `false` for manually collected entries. Synthetic entries are generated separately by the pipeline.

## What NOT to collect

- Postings that require login to view (those aren't truly public)
- Postings with personal contact info (phone numbers, personal emails) - strip these
- Postings that look like spam, scams, or MLM
- Duplicates across portals (note in `description` if the same role appears on multiple sites)

## Why this matters for your thesis

This manual dataset is a **named research artifact**: *"Curated open dataset of Nepali computing job postings, sampled May 2026."*. It can be:
- Cited in your thesis as a contribution (Section: Datasets)
- Released alongside the thesis (with portal sites' permission, or in anonymized form)
- Used as a benchmark by future researchers

You're not just collecting data - you're *creating* a dataset that didn't exist before in machine-readable form. That's a real contribution. Document it carefully.
