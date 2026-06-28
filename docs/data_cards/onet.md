# Data Card - O\*NET 30.3

- **Source:** O\*NET Database 30.3 - https://www.onetcenter.org/database.html
- **License:** CC BY 4.0 (attribution: "O\*NET® is a trademark of USDOL/ETA")
- **Tier:** `international`
- **Collection method:** automated bulk download (`scripts/download_onet.py`)
- **Version / retrieved:** 30.3 text bundle

## Contents used
Occupation titles, descriptions, skills, abilities, knowledge, and work activities.
Normalised into `Occupation` / `SkillRequirement` contracts and embedded for the
career retrieval collection.

## Why it's used
Provides a comprehensive, well-maintained occupation→skill taxonomy to ground
pathway recommendations and bridge curriculum skills to roles (RAG evidence, C1).

## Schema (post-normalisation)
`occupation_id, title, description, skills[], related_titles[], tier=international`

## Limitations
- US-centric labour context - used only as international-tier evidence, ranked
  **below** Nepal-tier sources (C4).
- Occupation granularity may not map 1:1 to Nepali job titles.

## Attribution
This product uses O\*NET data (CC BY 4.0), USDOL/ETA. D.R.O.N.A. is not endorsed
by USDOL.
