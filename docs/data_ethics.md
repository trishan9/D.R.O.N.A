# Data Ethics - D.R.O.N.A.

This document is the single reference for D.R.O.N.A.'s data-handling ethics: the
**PII policy**, the **licensing matrix** for every source, the **synthetic-data
labelling** rules, and the **scraping prohibitions**. It exists so that every data
decision is defensible at viva and reproducible by the next maintainer.

---

## 1. PII policy - zero collection

D.R.O.N.A. collects, stores, and uses **no personally identifiable information**.

| Principle | Implementation |
|---|---|
| No identity | The student profile is keyed by a random per-session UUID (`StudentProfile.session_id`), never a name, email, or student ID |
| No persistence | The profile lives only in memory for the session; the frontend keeps it in React state (no `localStorage`, no cookies) and the backend never writes it to disk/DB |
| No tracking | No analytics, no third-party calls in the request path, no logging of query text tied to identity |
| Session-scoped | `StudentProfile` and `AdvisingQuery` are discarded at session end |
| Contract-enforced | `StudentProfile` (`drona/contracts`) has `extra="forbid"` - no stray identity fields can be added accidentally |

This is a hard constraint, not a configuration. It satisfies the proposal's ethics
commitment and removes the need for an ethics-board data-handling review for the
Phase-1 system (the live *user study* with students is Phase 2 and **will** require
ethics approval).

---

## 2. Licensing matrix

Every dataset is used within its license. Tier is the D.R.O.N.A. provenance tier
(`DataTier`): retrieval prioritises **nepal** first.

| Dataset | Version | License | Tier | Collection method | Use in D.R.O.N.A. |
|---|---|---|---|---|---|
| O\*NET | 30.3 | CC BY 4.0 | international | Automated bulk download | Occupation → skill → pathway grounding |
| ESCO | v1.2.1 | CC BY 4.0 (EU) | regional/intl | API + CSV download | Skill taxonomy, occupation crosswalk |
| BLS OEWS | May 2025 | US public domain | international | Automated bulk download | Wage/role context (international tier) |
| NLFS Nepal | 2017/18 | Public (NSO Nepal) | nepal | PDF download + parse | Nepal labour-market context |
| Nepali job postings | n/a | **See §3** | nepal | **MANUAL collection only** | Local market evidence (Tier 1) |
| LinkedIn reports | published | report PDFs only | regional/intl | Manual download of public PDFs | Macro workforce context |
| Synthetic Q&A | n/a | MIT (ours) | synthetic | Generated (Phi-3.5 local / Gemini offline) | LoRA fine-tune + eval only |
| Softwarica curriculum | n/a | college materials (with permission) | nepal | Provided by student | Curriculum retrieval index |

CC BY 4.0 attribution for O\*NET and ESCO is recorded in each dataset's
[data card](./data_cards/) and surfaced in citations via the `source_id`.

---

## 3. Scraping prohibitions (hard "DO NOT")

The Nepali job portals' Terms of Service prohibit scraping. D.R.O.N.A. **never
scrapes them**:

- **MeroJob** - ToS §3.E explicitly prohibits automated collection.
- **JobsNepal, Internsathi, Kumari Jobs** - treated identically (no scraping).
- **LinkedIn** - never scraped; only published report **PDFs** are used.

Instead, the pipeline ships a **manual-collection JSON template**
(`data/manual_collection/`) and a loader (`drona/data_pipeline/scrapers/manual_loader.py`).
The student manually curates ~150–200 postings into the template; the loader
validates them against the `JobPosting` contract. The per-source scraper modules
exist as **documented, disabled stubs** that record this prohibition in code, so
the decision is visible and auditable - they do not perform live scraping.

---

## 4. Synthetic data - always labelled, never silently mixed

- Every synthetic record carries `is_synthetic=True` and `synthetic_anchor_ids`
  linking it to the real entries that inspired it (`JobPosting`, Q&A).
- Synthetic data is **never** mixed into the real retrieval tiers silently: it is
  tagged `DataTier.SYNTHETIC` and the UI/citations render it with a distinct
  "Synthetic" badge.
- Synthetic Q&A is used for **fine-tuning and evaluation only**, not as retrieval
  evidence presented to students as fact.
- Generation uses the **local** Phi-3.5 or the **offline** Gemini path - never the
  live advising request path (see §5).

---

## 5. Cloud-LLM boundary (C4 "local-only advising")

Gemini / Vertex AI are permitted **only offline** (synthetic data generation,
evaluation judging). They are **forbidden in the live advising request path**,
which is local-only (Ollama). This is enforced at startup: the FastAPI app raises
if `ALLOW_GEMINI_IN_REQUEST_PATH` is true (`drona/api/app.py`). Rationale:
data sovereignty, reproducibility, and no student query ever leaving the machine.

---

## 6. Bias & fairness

D.R.O.N.A. actively *mitigates* cognitive bias rather than amplifying it
(anti-anchoring multi-pathway output, counter-recommendations, transparent bias
flags). The bias detector is rule-based and falsifiable. Bias-mitigation metrics
are measured (`drona/evaluation/bias_mitigation.py`) and reported. Nepal-first
tiering is a deliberate fairness choice to counter the international-data
availability bias that would otherwise dominate an English-language corpus.

---

## 7. Auditability

- Every dataset → a [data card](./data_cards/) (provenance, license, limitations).
- Every trained model → a model card (`models/*/model_card.md`).
- Every architectural choice → a paper in [`research_papers.md`](./research_papers.md).
- The build ledger (`PROGRESS.md`) records decisions and their rationale.
