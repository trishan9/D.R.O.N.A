# Data Card - `onet_career_pathways`

**Source:** O*NET 30.3 Database ([link](https://www.onetcenter.org/database.html))
**License:** CC BY 4.0
**Provenance tier:** `international`
**Collection method:** `automated_bulk_download`  **Collected:** 2026-06-28  **By:** Trisan Wagle
**Records:** 39
**Version:** 30.3  **Created:** 2026-06-28

## Description
Computing and technology occupations (SOC 15-xxxx + CIS Managers) parsed from O*NET 30.3. Includes titles, descriptions, skill profiles, and technology skill examples. Used as international-tier anchor for career pathway recommendations.

## Fields
- pathway_id
- title
- tier
- onet_soc_code
- esco_code
- description
- typical_skills
- typical_education
- local_salary_range_npr
- international_salary_range_usd
- related_softwarica_modules
- sample_employers_nepal

## Known limitations
- US labour market only - salaries not included (US context)
- SOC taxonomy may not perfectly map to Nepal job market titles
- Technology skills list is indicative, not exhaustive

## Synthetic content
- contains_synthetic: **False**
- synthetic_fraction: n/a

## Collection ethics
- robots.txt verified: True
- robots.txt allows crawl: True
- rate limit applied: N/A (single bulk download)

## Outputs
- C:\Users\trish\Documents\Developer\D.R.O.N.A\data\processed\onet_career_pathways.parquet

## Notes
Downloaded from https://www.onetcenter.org/dl_files/database/db_30_3_text.zip. Zip SHA256: 7758ec966fd91895
