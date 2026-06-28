# Data Card - NLFS 2017/18 (Nepal Labour Force Survey)

- **Source:** Nepal Labour Force Survey 2017/18, National Statistics Office (NSO)
  Nepal - https://data.nsonepal.gov.np/
- **License:** Public (Government of Nepal open data)
- **Tier:** `nepal`
- **Collection method:** PDF download + parse (`pypdf`)
- **Version / retrieved:** 2017/18 report PDF

## Contents used
National employment structure, sector shares, youth/educated-workforce statistics,
and labour-market indicators relevant to computing graduates.

## Why it's used
Primary **Nepal-tier** macro context. Grounds advising in the real local labour
market rather than international assumptions (C4). Ranked first in retrieval.

## Schema (post-normalisation)
`indicator, value, unit, year, geography=Nepal, source=NLFS, tier=nepal`

## Limitations
- 2017/18 vintage - the most recent comprehensive NLFS at build time; flagged as
  dated where relevant. Sector tech detail is coarse.
- PDF parsing is table-structure dependent; parsed figures are spot-checked.

## Attribution
Source: NSO Nepal, NLFS 2017/18 (public).
