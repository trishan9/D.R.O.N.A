# Data Card - Softwarica Curriculum

- **Source:** Softwarica College of IT & E-Commerce - BSc (Hons) Computing module
  descriptors (3 modules minimum), provided by the student
- **License:** College materials, used with permission for this academic project
- **Tier:** `nepal`
- **Collection method:** student-provided PDFs/text at `data/raw/curriculum/`,
  parsed by `drona/data_pipeline/curriculum.py`
  (see `notebooks/02_curriculum_parsing.ipynb`)

## Contents used
Module code, title, year, credits, learning outcomes, skills developed, and
assessment summary.

## Why it's used
Defines what the student is actually learning, enabling D.R.O.N.A. to build
**curriculum→career bridges** ("how does the database module prepare me for a
backend role?") - the curriculum side of the dual index (C1).

## Schema (`CurriculumModule` contract)
`module_code, title, year, credits, is_core, learning_outcomes[],
skills_developed[], tier=nepal`

## Limitations
- Coverage limited to provided modules; advising is scoped to those.
- Module text quality depends on the source documents; the parser falls back to
  bundled seed modules if no files are present so downstream code still runs.

## Privacy
Contains no student PII - only programme/module descriptions.
