# Data Card - ESCO v1.2.1

- **Source:** European Skills, Competences, Qualifications and Occupations (ESCO)
  v1.2.1 - https://esco.ec.europa.eu/
- **License:** CC BY 4.0 (European Commission)
- **Tier:** `regional` / `international`
- **Collection method:** API + CSV download fallback
- **Version / retrieved:** v1.2.1

## Contents used
Skill and occupation taxonomy with multilingual labels and a skill↔occupation
crosswalk. Used to enrich and cross-reference O\*NET skills and to normalise skill
strings.

## Why it's used
Standardised skill vocabulary improves retrieval matching between curriculum
`skills_developed` and job-posting requirements (C1), and offers a regional
(European) reference point distinct from the US-centric O\*NET.

## Schema (post-normalisation)
`concept_uri, preferred_label, alt_labels[], skill_type, broader[], tier=regional`

## Limitations
- European framing; not Nepal-specific (ranked below Nepal tier).
- Large taxonomy - only the subset relevant to computing occupations is ingested.

## Attribution
Contains ESCO data © European Union, CC BY 4.0.
