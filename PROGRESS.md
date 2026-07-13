# D.R.O.N.A. - Build Progress Ledger

> Cross-session handoff. Read this FIRST every session (see SESSION START
> PROTOCOL in `DRONA_BUILD_PROMPT.md`). Format defined in `PROGRESS_TEMPLATE.md`.

## Current State
- **Active phase:** Phase 8 - documentation (COMPLETE). **All phases 0–8 done.**
  440 tests pass, ruff clean (re-verified 2026-07-11). Colab pipeline
  (notebooks/colab/01-05, Qwen3-4B base) ready; user starts training next.
- **Active task:** 2026-06-27 - **end-to-end data + training bring-up on real
  hardware.** Populated the pipeline with placeholder curriculum/jobs + the REAL
  O*NET 30.3 dataset, ran the real dual-embedding ingest, generated the LoRA SFT
  dataset, trained the CPU behavior-cloning gesture baseline, and verified the
  sim + web app run. See the 2026-06-27 "What Shipped" entry. Remaining real-world
  work: swap placeholder curriculum/jobs for real ones (drop-in), run the GPU
  notebooks (LoRA nb09 / ACT nb07 / Diffusion nb08) on Colab T4, install Ollama +
  pull a model for live advising, and record the demo. Phase-2 unchanged.
- **2026-06-13:** migrated ROS2/sim docs from Ubuntu dual-boot → **WSL2 on
  Windows 11** (`docs/wsl_setup.md`).
- **Last commit:** see `git log -1` (Phase 8 commit)
- **Working tree:** managed per-phase; commit between phases.
- **User sequencing:** Phase 6 before Phase 5 at user's request; then 7, then 8.

## Reconciliation note (IMPORTANT for any future session)
This repo was originally built to a **lighter plan** than `DRONA_BUILD_PROMPT.md`
mandates (commits WS0–WS6 with a Streamlit dashboard, ChromaDB-only, no FastAPI /
LangGraph / Postgres / Pinecone / Next.js). On 2026-06-09 the user chose the
**EXTEND** strategy: keep the working, tested code as the foundation and add the
missing pieces to reach the prompt's spec. So the legacy `WS<n>` commit numbering
does **not** line up with the prompt's `Phase 0–8`. This ledger tracks the
**prompt's** phase numbering. Mapping of what already existed:

| Prompt phase | Pre-existing coverage (legacy WS) | Remaining gap |
|---|---|---|
| 0 Bootstrap | pyproject, .env.example, .gitignore, README, tests | ✅ filled: deps groups, docker-compose, Alembic, CI, PROGRESS.md, db pkg |
| 1 Data pipeline | contracts, O*NET loader, ChromaDB ingest, manual loader, DataTier | ESCO/BLS/NLFS ingest, synthetic gen, pgvector schema, Pinecone, data_cards |
| 2 Advising | retriever (BM25+dense RRF), bias_detector (6), prompt_builder, llm_client, engine | LangChain RAG chain, LangGraph graph, reranker, FastAPI+websocket, Qwen fallback |
| 3 LoRA | - | all (synthetic Q&A, gold set, LoRA notebook, ablation, model_card) |
| 4 LeRobot | demonstration, mujoco_env, act_policy, gesture_dispatcher, train_act.py | MuJoCo upper-body env, dataset conversion, ACT+Diffusion notebooks, SmolVLA, sim eval |
| 5 ROS2/sim | ros2_ws (msgs, srvs, 5 nodes, launch) | .action defs + action server, URDF, Isaac Sim, Gazebo Harmonic, rosbag, topics doc |
| 6 Frontend | Streamlit dashboard (legacy) | Next.js 14 + Tailwind + shadcn/ui + streaming + gamification |
| 7 Evaluation | metrics, queries, harness (C1–C4) | Ragas, citation verify, scipy stats harness, 11 runnable notebooks |
| 8 Docs | architecture/eval/hardware/ros2 setup | data_ethics, phase plans, sim setup, research_papers, viva_prep, cards |

## Phase Status
| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 0 | Repo bootstrap | ☑ | gap-fill done |
| 1 | Contracts + data pipeline | ☑ | ESCO/BLS/NLFS/synthetic + stores + cards done; backend wiring optional |
| 2 | Advising intelligence | ☑ | LangGraph orchestration + citation verify + Qwen fallback + FastAPI (REST+WS) |
| 3 | LoRA fine-tune | ☑ | Q&A gen + SFT format + gold curation + LoRA config + ablation + Colab notebook + model_card; training runs on Colab T4 |
| 4 | LeRobot policies | ☑ | LeRobot dataset conversion + sim eval (success/jerk) + Diffusion wrapper + SmolVLA seam + notebooks 07/08; training runs on Colab T4 |
| 5 | ROS2 + simulation | ☑ | ExecuteGesture.action + policy_node action server (feedback/cancel), drona_description humanoid URDF + RViz, Gazebo Harmonic + Isaac launch (+ standalone stage script), full-system launch (rviz + rosbag), docs (gazebo/isaac/topics-actions); colcon build needs Ubuntu+ROS2 |
| 6 | Frontend | ☑ | **v2 (2026-06-13): 10-page sidebar app** (Dashboard/Advisor/Pathways/Skills/Analytics/Robot/Profile/Achievements/Preferences/About), light+dark, robot web-twin + live rosbridge, localStorage store, analytics charts. Original chat/pathways/gamification components reused. build+typecheck green |
| 7 | Evaluation | ☑ | C1–C4 harness + Ragas harness (proxy fallback) + bias-MITIGATION metrics + scipy.stats comparison + citation-grounding eval; 11 canonical notebooks; 16 new tests (431 total pass) |
| 8 | Documentation | ☑ | architecture +mermaid; data_ethics; phase1/2 plans; research_papers; viva_prep; demo script; 7 data cards; 3 model cards; README docs index |

(☐ not started · ◐ in progress · ☑ complete)

## What Shipped (most recent first)
- 2026-07-13 (6) - **Real Nepali job postings (placeholders retired).** New
  `scripts/scrape_nepali_jobs.py` collects live tech jobs from **MeroJob**
  (public API api.merojob.com/api/v1/jobs - rich: skills + NRs salary + company)
  and **KumariJob** (server-rendered, schema.org JSON-LD), tech-filtered, mapped
  to JobPosting (nepal tier). Pulled **97 real postings** (MeroJob 69 +
  KumariJob 28, ~80 employers incl. Ncell, Code Mantra, ControlArc). **LinkedIn
  deliberately excluded** (ToS + ethics; placeholder file removed). Top Nepali
  tech firms (Leapfrog/CedarGate/Fusemachines/Cotiviti/Logpoint) have NO public
  ATS API (checked Greenhouse/Lever) and post on MeroJob anyway. Fixed:
  make_placeholder_data._write_jobs now skips when real posting files exist (the
  earlier guard was curriculum-only, so data-prep had resurrected 30 dummies).
  All placeholder job files purged. Postings now: 200 international (data_jobs) +
  97 real Nepal = 297 loaded; career collection 336 docs; C4 nepal_citation_ratio
  = **1.0** (target met). 441 tests pass, ruff clean. FINAL_STEPS 2.4 documents
  the scraper. DATA IS NOW FULLY REAL & TRAINING-READY.
- 2026-07-13 (5) - **Official course-API data incl. REAL FEES.** The
  softwarica.edu.np course pages are Next.js SPAs; found their public backend
  `https://ftp.softwarica.edu.np/api/courses/<slug>` (no auth) from the JS
  bundle. New `scripts/fetch_softwarica_courses.py` pulls all 4 courses (3 BSc
  + MSc Data Science) and writes `_guide_<slug>.md` per course with the FULL
  tab data the brochure lacked: **fee structure** (per-year + grand total, e.g.
  EHC NPR 13,92,400), **careerOpportunities** (real titles - EHC: SOC, Red
  Team, VAPT, Threat Hunting, Cyber Forensics...), admissionEligibility, IELTS
  requirement, degreeHighlights, and official module list w/ credits. Replaced
  the earlier brochure-derived _guide_* files (the API is authoritative +
  richer). Curriculum index -> 2337 docs. Verified: fee/career/admission/MSc
  queries surface the INFO-* guides (INFO-EHC_c1 #1 for fee query, INFO-EHC_c0
  #1 for careers, INFO-SE-MSC for the master's). Hit a transient chromadb
  "hnsw segment reader: Nothing found on disk" after an interrupted write - a
  clean rm+re-ingest fixed it (documented). 441 tests pass, ruff clean.
- 2026-07-13 (4) - **Institutional/programme reference data from the official
  prospectus.** The LMS sync gave deep module CONTENT but no
  institutional/programme-level context. Added 4 reference docs to
  data/raw/curriculum/ built from the Softwarica 2025/26 Programme Prospectus:
  `_guide_{csai,software_engineering,ethical_hacking}.md` (INFO-CSAI/SE/EHC:
  programme overview, 2025/26 structure, **career outcomes**, **entry
  requirements**, intake/duration/credits, all programme-tagged) and
  `_college_softwarica.md` (INFO-SOFTWARICA: college overview, Coventry
  partnership + rankings, MSc Data Science & Computational Intelligence,
  student experience/Tech X/immersion, achievements, contact). They flow
  through the normal parser -> chunk -> embed path (curriculum 2315 -> **2328
  docs**). Verified retrieval: entry-req -> INFO-SE/CSAI, EHC careers ->
  INFO-EHC, Coventry rank -> INFO-SOFTWARICA, MSc/achievements -> INFO-SOFTWARICA.
  The live softwarica.edu.np/courses/* pages are JS-rendered SPA shells (plain
  fetch yields no course data), so the brochure text was the source. FEE
  STRUCTURE gap: not in the prospectus ("available on request") and not
  publicly fetchable - noted in INFO-SOFTWARICA; user can add real fees later.
  441 tests pass, ruff clean.
- 2026-07-13 (3) - **All 3 programmes' real LMS content ingested.**
  Ran fetch_lms.py for the Ethical Hacking (acct 230215, Yubin Shrestha, 32
  modules / 1899 lessons) and CS-AI (acct 240226, Dikshanta Chapagain, 40
  modules / 1049 lessons) accounts with --programme ethical_hacking / csai,
  PDFs folded in. Removed the 51 shallow public-page EHC*/CSA* files (real LMS
  content supersedes them). Curriculum now 79 module files (some shared across
  accounts): by programme csai=40, ethical_hacking=24, software_engineering=15
  (Computing-exclusive; shared foundational/English modules carry the tag of
  whichever account synced last - acceptable, retrieval isn't programme-filtered).
  Fixed 2 bugs: (1) _extract_programme now recognizes the canonical slugs
  ("csai","ethical_hacking") the script writes, not just human aliases - it was
  defaulting everything to software_engineering; (2) ingest.add_curriculum_modules
  dedupes cross-account shared module_codes (8 of them), keeping the richest copy.
  ChromaDB rebuilt: curriculum **2315 documents** (was 123 pre-content-chunking).
  Verified per-programme deep retrieval: EHC forensics -> ST4060CEM chunks,
  exploit-dev -> ST6048CEM; CSAI neural nets -> ST5000CEM, agents -> ST6058CEM;
  SE tidyverse -> ST5014CEM. 441 tests pass, ruff clean.
  PRIVACY: 3 students' accounts used with their credentials; authenticated
  material stays in gitignored data/raw/ (PRIVATE repo only); account owners
  advised to rotate passwords shared in chat.
- 2026-07-13 (2) - **LMS PDF content captured + deep content now embedded.**
  Found two gaps in the first LMS sync: (1) linked PDFs (lab worksheets,
  lecture decks) were NOT downloaded - only inline lesson text + PDF filenames
  were kept; (2) even the inline weekly content wasn't reaching the embeddings
  because the ingestor only embedded a 1000-char description per module.
  Fix 1 - fetch_lms.py now downloads linked PDFs (schoolworkspro/c4mpus
  /uploads/files/*.pdf, auth'd) and folds pypdf-extracted text into each lesson
  (`--with-files` default; 6 files/lesson, 40 pages, 15MB caps; images/OCR out
  of scope). Re-synced all 33 Computing modules -> curriculum content grew to
  ~1.53M chars (e.g. "Introduction to Big Data" lesson 33 -> 3782 chars).
  Fix 2 - added `CurriculumModule.content` (full body), parser populates it,
  and `Ingestor.add_curriculum_modules` now CHUNKS it (_chunk_content:
  ~1400-char overlapping chunks, 40/module cap) into per-module embedding docs
  (`curriculum_<code>_c<N>`). Curriculum collection 123 -> **1197 documents**.
  Verified PDF-ONLY content is now retrievable: "volume velocity variety big
  data" -> ST5014CEM_c34/c21 (Big Data lecture PDF), "tidyverse dplyr" ->
  ST5014CEM lab-worksheet chunks, "normal form ER diagram" -> ST4005CEM chunks.
  441 tests pass, ruff clean.
- 2026-07-13 - **Real LMS content extracted end-to-end (c4mpus, authenticated).**
  Reverse-engineered the college LMS API from its SPA bundle
  (POST /verification/login -> GET /users/my-learnings -> GET
  /lessons/<slug>/weekly/{public,private} -> GET /lessons/read-only/<id>).
  Rewrote `scripts/fetch_lms.py` to do the whole chain from a plain login
  (`--login -u <id> -p <pw>`); the earlier bare-token approach was dead (that
  token 401'd - stale). RAN IT: logged in as the student, pulled **all 33
  enrolled BSc-Computing modules, ~1393 real lesson bodies** (actual lecture
  text, definitions, lab worksheets) into data/raw/curriculum/lms_*.md
  (Programme: software_engineering) + raw cache data/raw/lms_raw/. Removed the
  23 redundant public-page SWC* files (the LMS files are the real deep version
  of the same programme). Curriculum now: software_engineering=33 (LMS, rich),
  ethical_hacking=27 + csai=24 (public page) = 84 modules, all unique codes.
  ChromaDB rebuilt: 123 curriculum chunks / 269 career. Retrieval verified on
  real content (EDA -> ST4005CEM/CSA223; pen-testing -> EHC212/SC-001; neural
  nets -> CSA314). Bugs fixed along the way: _week_key (mixed str/int/None
  week values), per-module lesson cap (was global 400, truncated later
  modules), _safe_name (Windows forbids ':' in GETS slugs), title/code
  extraction (walk JSON for slug<->title; strict CEM/COM/IAE code regex +
  unique MOD- fallback), and the curriculum parser now trusts an explicit
  "Module Code:" header before scanning body text (LMS lecture text contains
  incidental code-like strings). 441 tests pass, ruff clean.
  PRIVACY: authenticated material; data/raw/* gitignored (force-add to a
  PRIVATE repo only). Student's pasted password was NOT used beyond this login
  and they were advised to rotate it.
- 2026-07-13 - **c4mpus LMS sync tooling (`scripts/fetch_lms.py`).**
  The college's weekly learning content sits behind api.c4mpus.com
  (`GET /weeks/<module-slug>`, Bearer JWT). The token the student supplied was
  REJECTED (401, identical response with and without the Authorization header
  -> session rotated/invalidated or bound to something extra), so the script is
  built around **replaying the real browser request**: `--curl-file` parses a
  DevTools "Copy as cURL" blob and reuses every header (auth, cookies, custom),
  which survives whatever the API actually requires. Also: `--discover` probes
  7 candidate module-list endpoints, `--modules` takes explicit slugs, JWT
  claims are read (unverified, public claims only) to label course/programme.
  Response schema is undocumented, so `harvest()` walks the JSON tree
  defensively pulling title/content/link fields -> one
  `data/raw/curriculum/lms_<slug>.md` per module (weeks + lessons + resource
  links, HTML stripped, `Programme:` header so it flows into the existing
  parser/ingest) plus raw JSON kept in `data/raw/lms_raw/` for re-parsing
  without re-fetching. Verified offline: cURL parsing (incl. `-b` cookies) and
  JSON->markdown conversion both tested against realistic payloads; ruff clean;
  441 tests pass. data/raw/* is gitignored - authenticated material must only be
  force-added into a PRIVATE repo. Procedure documented in FINAL_STEPS 2.3.
  SECURITY: the student pasted their campus password into chat - it was NOT
  used (token-only), and they were advised to rotate it.
- 2026-07-12 (2) - **Multi-programme platform + notebooks consolidation.**
  NOTEBOOKS: the 11 legacy deep-dive notebooks deleted; the staged pipeline
  moved up from notebooks/colab/ to **notebooks/01-05** (single suite); every
  doc reference updated (COLAB guide sections 1-3 consolidated into one
  notebook-04 walkthrough; RUN_EVERYTHING 5.2-5.4 collapsed; checklists fixed).
  PROGRAMMES: real module data extracted for ALL Softwarica bachelor
  programmes from official pages (Wayback: EHC snapshot 2023-09-28, CSAI
  2025-02-26) -> **74 real modules** (SE/Computing 23, Ethical Hacking 27
  incl. skills-development tests, CSAI 24). `programme` field threaded
  end-to-end: CurriculumModule + StudentProfile contracts -> curriculum
  parser ("Programme:" header) -> ingest metadata -> AdviseRequest ->
  prompt_builder ("Enrolled programme: ..." line) -> frontend (Programme
  selector in profile-builder, typed PROGRAMME_LABELS, request carries it).
  make_placeholder_data now NEVER writes dummies next to real curriculum
  (guard added after placeholders resurrected themselves in a rebuild).
  ChromaDB rebuilt from scratch (stale placeholder docs purged): curriculum
  113 chunks / career 269. Verified: EHC query -> EHC212/EHC112/EHC312 top
  hits; CSAI query -> CSA314/CSA312/CSA211; C4 nepal ratio 0.93 (target met);
  programme string reaches the LLM prompt; 441 tests pass; frontend
  typechecks. LMS: authenticated-sync design documented in FINAL_STEPS 2.3
  (fetch_curriculum --cookie; credentials never in the request path).
- 2026-07-12 - **Real Softwarica curriculum + dashboard ML analytics.**
  REAL CURRICULUM: extracted the full official BSc (Hons) Computing module
  list from softwarica.edu.np/course/computing (live site is a JS shell -
  used the Wayback snapshot 2025-02-14, fetched with browser headers) ->
  **23 real module files** (Y1-Y3 both semesters, credits, descriptions,
  tools, 4 specialization tracks; SWC*** project-local codes since Coventry
  codes are not public) replacing the 10 placeholders; pipeline rebuilt,
  curriculum collection 50 -> 73 docs. data/raw is gitignored - user must
  `git add -f data/raw/curriculum`. DASHBOARD: new `GET /evaluation` API
  endpoint serving reports/evaluation_report.json + sft_metrics.json;
  Analytics page now fetches it - C1/C2 charts switch from "Reference shape"
  to "Thesis run (measured)" with real numbers (hybrid NDCG@5 0.763,
  macro-F1 0.861), new section with C3 policy comparison, LLM base-vs-tuned
  loss chart, and the model-selection verdict list. nb01 gained a 6.1 cell
  importing the data_jobs postings when missing. Verified: 441 tests (new
  /evaluation test), ruff clean, frontend typecheck + build green, endpoint
  live-checked with real report data.
- 2026-07-11 (6) - **BLS OEWS integrated end-to-end (real data, live).**
  Downloaded the May 2025 national wage table (browser headers required -
  plain curl gets 403; oesm25nat.zip -> national_M2025_dl.xlsx in
  data/raw/bls/, gitignored). `prepare_training_data.py` now applies the
  enrichment automatically BEFORE the JSON export (first patch landed after
  the write - fixed); nb01's BLS cell now auto-downloads (May 2025 -> May 2024
  fallback). Result: **38/39 pathways carry real USD wage bands** in
  onet_career_pathways.json (e.g. Computer Systems Analysts 67,340-167,710);
  SFT regenerated against enriched pathways; the previously-empty EDA salary
  chart now renders. NLFS auto-download attempted: NSO server timed out
  (loader degrades gracefully; retry later). ESCO remains the one
  manual-download optional (interactive portal form).
- 2026-07-11 (5) - **Real-data tooling + popular public dataset integrated.**
  NEW `scripts/fetch_curriculum.py`: URL list (+ optional browser Cookie header
  for the login-protected campus LMS) -> clean Markdown/PDF into
  data/raw/curriculum/ (markdownify; strips site chrome; login-page detection).
  NEW `scripts/import_public_postings.py`: HF datasets (streaming) or Kaggle
  CSV -> JobPosting JSON under data/manual_collection/<source>/ at tier
  INTERNATIONAL; schema-validated through manual_loader; LinkedIn rows dropped;
  USD never converted to NPR. RAN IT: 200 postings from lukebarousse/data_jobs
  (~785k-row popular tech-postings corpus; schema verified live) now at
  data/manual_collection/data_jobs/ - career collection 79 -> 279 docs after
  re-ingest. C4 re-checked: nepal_citation_ratio 0.567 -> **0.45, target >=0.40
  still met** (margin thinner with placeholder Nepal data; rises when real
  Nepali postings land; tune with --limit). FINAL_STEPS 2.3 + new 2.5 document
  both tools. 440 tests pass, ruff clean.
- 2026-07-11 (4) - **Model upgrades before the first Colab training run.**
  Advising LLM: default base model upgraded Phi-3.5-mini -> **Qwen3-4B-Instruct-2507**
  (Apache-2.0, strongest ~4B open instruct, non-thinking = clean JSON);
  `DronaLoraConfig.target_modules` -> **"all-linear"** (QLoRA-paper best
  practice, architecture-agnostic - Phi/Llama swap is now one line; explicit
  lists kept in ARCH_TARGET_MODULES); adapter output dir renamed
  `models/phi35-lora-advising` -> **`models/advising-lora`** (all docs/notebooks
  synced). NEW **transformers serving backend** (`drona/advising/hf_client.py`):
  serves base + LoRA adapter directly from HF weights (no GGUF conversion),
  same interface as LLMClient, selected via `LLM_BACKEND=transformers`
  (settings + .env{,.example}); `make_llm_client()` factory wired into
  engine + graph. Guidance encoded everywhere: CPU -> ollama (llama.cpp faster),
  GPU -> transformers (no quant loss, adapter as-is). Ollama defaults:
  primary `qwen3:4b-instruct-2507-q4_K_M`, fallback qwen2.5:3b (NOTE: exact
  Ollama tag unverified offline - .env lists alternates). Reranker upgraded
  bge-reranker-base -> **bge-reranker-v2-m3** (better + multilingual; ~2x CPU
  latency, fine since rerank runs once/query; first run downloads ~2.2GB).
  nb04: BASE_MODEL selector cell, generic titles, export targets use
  cfg.output_dir; nb09 synced (superseded note). model_card derives from
  DronaLoraConfig; tests updated (440 pass). Embeddings deliberately NOT
  changed (bge-small + JobBERT-v2 keep their validated ablation; JobBERT-v3 =
  future, needs re-index). Verified: 440 tests, ruff clean, config smoke OK,
  both notebooks compile.
- 2026-07-11 (3) - **Final end-to-end audit + FINAL_STEPS.md.**
  Audit verdicts: LangGraph orchestration KEPT (explicit 5-node state machine
  detect_bias->retrieve->generate->verify->format with bounded retry routing,
  lazy imports + imperative AdvisingEngine fallback - right-sized, no migration
  warranted); RAG already best-practice two-stage (hybrid BM25+dual-dense+RRF ->
  bge-reranker-base cross-encoder -> grounding verification node) - no changes
  needed. Fixed a REAL latent bug: jobsnepal.py data-card builder referenced
  undefined `settings` (NameError on that path) - import added. Completed the
  long-deferred ruff housekeeping pass: `ruff check drona scripts tests` is now
  fully clean (was 153 findings; safe fixes + manual renames; full suite green
  after). pyproject gained `export` (onnx+onnxruntime) and `deploy`
  (onnxruntime-only, robot-side) extras. Notebook 04 now installs onnx and runs
  scripts/export_policies.py as step B.1b so the Colab artifact zip carries the
  deployment ONNX. NEW: **FINAL_STEPS.md** - the complete sequential
  blank-machine-to-robot guide (accounts, dataset matrix auto/manual/collect
  with links, Windows env, Colab training, Ollama/RAG/web, WSL2+ROS2+Gazebo
  install & launch with verify steps, Isaac, validation checklist, debugging
  table, hardware deployment) - linked from the README top. Verified: 439
  tests pass, ruff fully clean, live retrieval smoke test OK.
- 2026-07-11 (2) - **ROS2 deployment-readiness pass (`ros2_ws/` + drona.interaction).**
  Models now ship in deployment formats: `scripts/export_policies.py` exports every
  trained BC gesture to ONNX (opset 17) + TorchScript with a verified-parity
  manifest (max|delta| <= 3.2e-07); new `drona/interaction/exported_policy.py`
  (OnnxBCPolicy, onnxruntime-only inference); `PolicyRouter` tiering is now
  ACT -> ONNX -> torch BC -> keyframe (policy_node/gesture_node get it free).
  Simulation-first: URDF gained camera_link + REP-103 optical frame and
  xacro-gated gz camera sensor + per-joint gz PID controllers; new
  `worlds/drona_advising.sdf` (Sensors system + desk + student figure); Gazebo
  launch now uses the custom world, spawns the robot on the desk, bridges
  camera + per-joint commands, runs use_sim_time, and drives the gz model via
  the new `gz_joint_relay` node so gestures physically play out in sim.
  Perception gained an `image_topic` mode (consumes the simulated/remote
  camera through the same MediaPipe path; `open_camera` flag added to
  MediaPipeDetector/make_detector). New `diagnostics_node` publishes
  per-stream liveness on /diagnostics (wired into system/gazebo/hardware
  launches + rosbag capture). Config fixes: params/hardware yaml now cover
  policy + diagnostics nodes; hardware launch rebuilt (TF + policy action
  server + diagnostics + rviz/rosbridge args, arm_port actually wired through
  to SO100ArmInterface in both gesture/policy nodes; gesture_node owns the
  serial port - policy_node use_hardware=false in hardware.yaml to prevent
  double-driving). Docs: new `ros2_ws/README.md` (architecture, sim-first
  workflow, deployment checklist), topics doc updated. Verified: 439 tests
  pass (8 new deployment tests), xacro/SDF/YAML/py_compile all green, ONNX
  tier exercised live in sim-eval (100% success).
- 2026-07-11 - **Colab A100 staged notebook pipeline (`notebooks/colab/01-05`).**
  Five clean, self-bootstrapping notebooks: 01 data cleaning & preprocessing
  (O*NET 30.3 + optional ESCO/BLS/NLFS + curriculum + jobs; validation, dedupe,
  IQR outlier flags, encoding, SFT + demos build, artifacts + cleaning report),
  02 EDA (distributions, missingness, correlations, class balance,
  curriculum-vs-market alignment, trajectory/jerk EDA), 03 feature engineering
  (dual embeddings bge+JobBERT, PCA/t-SNE, similarity structure, dual-vs-single
  ablation - JobBERT separation 0.123 vs bge 0.080 - BM25, ChromaDB ingest),
  04 model training (A100 bf16 LoRA w/ QLoRA fallback + TF32 + learning curves +
  optional LR sweep + BC/ACT/Diffusion + TensorBoard + one-zip export),
  05 evaluation (C1 3-way retrieval ablation + top_k sweep, C2 per-type P/R/F1 +
  confusion matrices + error listing, C3 policy comparison + paired stats +
  trajectory overlay, C4 citation gauge, base-vs-LoRA, verdict table ->
  `reports/final_comparison.csv` + `reports/evaluation_report.json`).
  Notebooks 01/02/03/05 executed end-to-end locally (CPU) as verification;
  figures land in `reports/figures/` (gitignored). Shared CVD-safe plot style.
  Docs: `notebooks/README.md` (new), COLAB guide + RUN_EVERYTHING + README
  updated (A100-first, O*NET version fixed 28.3->30.3, ESCO/BLS/NLFS listed);
  `matplotlib` added to the `[eval]` extra. 431 tests + frontend build re-verified.
- 2026-06-27 - **Real data + training bring-up (CPU/Windows).** Brought the whole
  pipeline to life on the student's box and fixed several real bugs found by
  actually running it.
  - **Placeholder data** (clearly marked, drop-in replaceable): 10 Softwarica
    BSc-Computing module docs (`data/raw/curriculum/*.md` + one real `.pdf` to
    exercise the pypdf path) and 40 Nepali tech job postings across
    merojob/jobsnepal/internsathi/kumarijobs/linkedin
    (`data/manual_collection/*/`). `data/raw/*` is gitignored by design, so the
    curriculum lives locally; the manual-collection JSONs are tracked.
  - **Real public dataset:** ran `scripts/download_onet.py` → **O*NET 30.3**
    (CC BY 4.0). Adapted `onet.py` to the 30.3 schema (renamed files:
    Essential/Software Skills, Education + Education Categories lookup) with a
    legacy-filename fallback → **39** computing CareerPathways.
  - **Real dual-embedding ingest:** `scripts/ingest_data.py` → ChromaDB
    **curriculum=50 / career=79** docs (bge-small-en-v1.5 + JobBERT). Verified
    hybrid retrieval returns sensible Nepal-first results for ML / cybersecurity /
    frontend queries. Fixed two ingest bugs: chromadb ≥1.x rejects `get(ids=[])`
    (guard added) and parquet NaN optionals were dropping ALL pathways
    (NaN→None coercion in `_load_career_pathways_parquet`).
  - **LoRA training data:** `scripts/generate_qa.py` → **450 train / 50 val** SFT
    examples + 50 gold-review pairs, grounded in the real pathways (bias-balanced
    across 7 classes). Ready for nb09 on Colab T4.
  - **Trained a model (CPU):** new `drona/interaction/bc_policy.py`
    (phase-conditioned behavior-cloning `BasePolicy`) + `scripts/train_bc_gesture.py`.
    Generated 150 demonstration episodes (5000 frames) and trained 6 per-gesture
    MLPs to val-MSE ≈ 1e-6. Sim-eval vs keyframe baseline: BC is **smoother**
    (mean jerk 0.0002 vs 0.0005 - the C3 win) and hits 4/6 gestures; it undershoots
    the two high-amplitude gestures (greet/farewell) - the textbook BC
    regression-to-mean limit that motivates ACT's action chunking. Checkpoints +
    `bc_training_report.json` under `data/checkpoints/bc/` (gitignored).
  - **Sim demo fixed + verified:** `scripts/run_simulation.py` had drifted from the
    current APIs - repaired `GestureDispatcher`/`PolicyRouter` construction, the
    perception import, and the `SessionMachine.context` → `.state`/`session_summary()`
    refactor; rewired the session loop to walk greet→listen→advise→farewell
    deterministically. Headless full-session run is green (run with `PYTHONUTF8=1`
    on Windows to avoid the cp1252 console crash on box-drawing chars).
  - **Web app verified:** `frontend` typecheck clean, `next build` green (13 routes),
    prod server serves 200 on /, /advisor, /pathways, /robot, /analytics, /skills,
    /about.
  - **ROS2 verified:** all 18 nodes/launch py_compile clean; msgs/srv/action present
    (`colcon build` still needs WSL2 + ROS2 Humble - `docs/wsl_setup.md`).
  - **Gated externally:** live LLM advising needs Ollama (pkg installed, server/binary
    not) - `ollama serve` + pull a model. GPU trainings (LoRA/ACT/Diffusion) run on
    Colab T4. **Verify:** `pytest -q` → 431 passed, 1 skipped.

- 2026-06-13 - **Frontend v2: multi-page platform + robot web-twin + NVIDIA/WSL
  sim clarity.** Rebuilt `frontend/` from a single dashboard into a 10-page
  sidebar-navigated app (DataCamp-style modern-minimal, light+dark via
  next-themes). New app shell (`components/layout/`: sidebar, topbar, user menu,
  mobile sheet). Pages under `app/(app)/`: Dashboard, Advisor (real WS streaming),
  Pathways, Skills, Analytics, **Robot Control**, Profile, Achievements,
  Preferences, About. New libs: `store.tsx` (localStorage session store - profile/
  response/exploration/history/prefs, zero PII), `robot.ts` (1:1 TS port of
  `demonstration.py` keyframes + FK), `rosbridge.ts` (dependency-free rosbridge v2
  client), `analytics.ts` (live + clearly-labelled reference metrics), `nav.ts`.
  Robot page = faithful animated 6-DOF twin (real gesture keyframes), joint
  telemetry, session FSM, engagement gauge, full-session autoplay, AND **live ROS2**
  mode: subscribes `/drona/joint_states`, calls `/drona/execute_gesture`. Added
  `rosbridge:=true` arg to `drona_system.launch.py` + `docs/wsl_setup.md` §9.
  Clarified Isaac Sim story (`sim_setup_isaac.md`): WSL2 is supported but Isaac
  needs an **RTX** GPU - the GTX 1650 is GTX (no RTX cores) → cloud-only; Gazebo +
  web twin are the local embodied demo. Added shadcn primitives (avatar,
  dropdown-menu, switch, select, scroll-area, sheet, skeleton); deps next-themes +
  5 radix pkgs. Reused all existing components (chat/pathways/gamification).
  **Verify:** `cd frontend && npm run build` (✓ 11 routes) + `npm run typecheck`
  (✓ clean); runtime SSR 200 on all routes.
- 2026-06-13 - **WSL2 migration** (student dropped Ubuntu dual-boot; now Windows 11
  + WSL only). New `docs/wsl_setup.md` (WSL2 install, WSLg GUI, NVIDIA WSL GPU,
  `/mnt/c` vs native repo, ROS2 Humble + Gazebo Harmonic install, build/run, GL
  software-fallback troubleshooting, usbipd-win for Phase-2 USB arm). Re-pointed
  every "Ubuntu dual-boot" reference to WSL2: `STUDENT_RUNBOOK.md` (env matrix
  column, Part A6, Part G, timeline wk5, checklist, related-docs), `README.md`
  (sim section + docs index), `ros2_setup.md` (WSL2 promoted to primary path),
  `sim_setup_gazebo.md` (platform note + WSL GL troubleshooting rows),
  `phase1_plan.md`, `hardware_setup.md`, and the `drona_gazebo.launch.py` docstring.
  No ROS2 *code* change needed - Humble runs unchanged inside WSL2; only setup/docs
  differ. Also committed prior session's polish (STUDENT_RUNBOOK, README/verify_env
  edits, PROGRESS_TEMPLATE removal). **Verify:** `pytest -q` → 431 passed, 1
  skipped (re-confirmed this session); docs render; ROS2 build is a WSL step.
- 2026-06-09 - Student operational guide + final polish - `docs/STUDENT_RUNBOOK.md`
  (complete runbook: data collection paths, script order, local/Colab/Ubuntu matrix,
  time estimates, master timeline, troubleshooting, viva checklist). Added
  `data/raw/curriculum/`, `data/raw/esco/`, `data/checkpoints/` gitkeeps.
  Updated `README.md` (prominent runbook link + build status), `verify_env.py`
  (current phase messaging). Confirmed canonical 11 notebooks only.
- 2026-06-09 - Phase 8 documentation (PROJECT COMPLETE) - `docs/data_ethics.md`
  (PII policy + full licensing matrix + scraping prohibitions + cloud-LLM boundary);
  `docs/phase1_plan.md` + `docs/phase2_plan.md` (delivered vs deferred); 
  `docs/research_papers.md` (paper → design-choice mapping, 12 core + supporting);
  `docs/viva_prep.md` (20 anticipated examiner Q&A grouped by theme);
  `docs/demo_video_script.md` (shot-by-shot demo storyboard + commands); 4 **mermaid**
  diagrams added to `docs/architecture.md` (system context, advising pipeline,
  provenance tiers, sim-to-real seam); `docs/data_cards/` with 7 per-dataset cards
  + index; `models/act-gesture-policy/model_card.md` + 
  `models/diffusion-gesture-policy/model_card.md` (phi35-lora card already existed);
  README documentation index + Running updates (Next.js + ROS2). **Verify:** all docs
  render; `rg "```mermaid" docs/architecture.md` → 4.
- 2026-06-09 - Phase 7 evaluation harness - new `drona/evaluation/` modules:
  `bias_mitigation.py` (pathway diversity, hedge frequency, counter-recommendation
  rate, refusal rate, tier-citation distribution, nepal-first rate, bias-flag
  coverage - the response-level *mitigation* metrics, distinct from detection
  P/R/F1); `stats.py` (scipy.stats comparison harness: Welch t, Mann-Whitney U,
  Cohen's d, rank-biserial, bootstrap 95% CI, Shapiro normality, paired
  t/Wilcoxon - for robot-vs-traditional and ACT-vs-keyframe); `ragas_harness.py`
  (Ragas when installed + offline judge, else a transparent lexical proxy clearly
  labelled as such); `citation_eval.py` (aggregate grounding / hallucination rate
  over response sets, reusing `advising.verify`). Exported via `evaluation/__init__`.
  Notebooks reconciled to the canonical **11** (created 02_curriculum_parsing,
  03_embedding_quality, 04_retrieval_ablations, 05_bias_detection_eval,
  06_llm_response_quality, 10_end_to_end_eval, 11_sim_to_real_handoff; removed 4
  non-canonical duplicates). All notebooks degrade gracefully (no ChromaDB/Ollama/
  GPU needed to run). **Verify:** `pytest tests/test_ws7_phase7_eval.py` (16 pass;
  431 total) ; `python scripts/run_evaluation.py --c2 --c3`.
- 2026-06-09 - Phase 5 ROS2 + simulation - `drona_msgs/action/ExecuteGesture.action`
  (goal/result/feedback; wired into CMakeLists + package.xml with action_msgs).
  `drona_ros/policy_node.py` - ROS2 **ActionServer** wrapping the LeRobot/keyframe
  PolicyRouter with per-frame feedback (progress/joint_positions), cancellation,
  and /drona/joint_states streaming (entry point added). New `drona_description`
  package: humanoid upper-body URDF (`drona_humanoid.urdf.xacro`, joints =
  JOINT_NAMES j0..j5), RViz config, `display.launch.py` (gui sliders or live
  joint stream). `drona_bringup` launches: `drona_gazebo.launch.py` (Gazebo
  Harmonic + ros_gz bridge + spawn), `drona_isaac.launch.py` (ROS2 side,
  use_sim_time) + `isaac/drona_isaac_stage.py` (standalone Isaac stage builder,
  URDF import + ROS2-bridge OmniGraph), `drona_system.launch.py` (full stack +
  optional RViz + optional rosbag record of all topics). Docs:
  `sim_setup_gazebo.md`, `sim_setup_isaac.md` (≥8GB VRAM note + cloud-GPU recipe),
  `ros2_topics_actions.md` (full topic/service/action graph). All new launch/node
  Python `py_compile`-clean. **Verify (Ubuntu+ROS2 Humble):** `cd ros2_ws &&
  colcon build --symlink-install`; `ros2 launch drona_bringup drona_system.launch.py
  use_rviz:=true`; `ros2 action send_goal /drona/execute_gesture_action
  drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback`.
- 2026-06-09 - Phase 6 Next.js frontend - `frontend/` Next.js 14 App Router +
  TypeScript + Tailwind + shadcn/ui (new-york). `lib/types.ts` mirrors the Pydantic
  contracts; `lib/api.ts` REST + WS client (derives ws:// from API URL; advising
  path stays local-only); `lib/gamification.ts` pure anti-bias logic (diversity
  score, badges, skill-tree, counter-rec selection, reversibility classification).
  Components: streaming `ChatPanel` (WS `/ws/advise` node-by-node progress →
  result/refusal), `ProfileBuilder` (session-scoped, no PII, no persistence,
  self-rated skill sliders), `PathwayCard` + `PathwayComparison` (head-to-head)
  + `CitationDrilldown` (tier-coloured excerpts), gamification (`DiversityMeter`
  recharts donut, `ExplorationBadges`, `SkillTree`, `CounterRecommendationPanel`,
  `ReversibilityViz`), `BiasFlags`, `HealthStatus` (live backend poll). 12 shadcn
  primitives. **Verify:** `cd frontend && npm install && npm run build`
  (passes; Next 14.2.35) + `npm run typecheck` (green); `npm run dev` against
  `python scripts/run_api.py`.
- 2026-06-09 - Phase 4 LeRobot policies - `drona/interaction/lerobot_dataset.py`
  (pure `to_lerobot_records` + `LEROBOT_FEATURES` spec + lazy `build_lerobot_dataset`
  via `LeRobotDataset.create`; gesture label = per-frame `task`/instruction, 20 FPS),
  `sim_eval.py` (backend/policy-agnostic harness: success rate = reached-apex +
  returned-to-rest, gesture quality = mean jerk + path length; `compare_policies`
  for keyframe-vs-ACT C3 claim; pure with KeyframePolicy+StubEnv → keyframe baseline
  scores 100% success), `diffusion_policy.py` (LeRobot Diffusion Policy wrapper +
  keyframe fallback, C3 ablation), `smolvla.py` (pre-trained SmolVLA inference seam,
  instruction→gesture keyword map, transparent KeyframePolicy fallback when LeRobot
  absent). `notebooks/07_lerobot_act_training.ipynb` + `08_lerobot_diffusion_policy.ipynb`
  (Colab T4, LeRobot CLI training + three-way eval). +20 tests (415 total green, 1
  skipped). **Verify:** `pytest tests/test_ws4_phase4_lerobot.py -q`;
  `python -c "from drona.interaction.sim_eval import evaluate_keyframe_baseline as e; print(e().success_rate)"`.
- 2026-06-09 - Phase 3 LoRA fine-tune - `drona/finetune/`: `qa_generator.py`
  (deterministic, grounded, bias-balanced synthetic advising Q&A → gold JSON
  answers; anchored + labelled), `dataset.py` (chat SFT formatting via the
  production prompt_builder + train/val split + JSONL), `gold_set.py` (stratified
  ~50 human-review file + approved-only loader), `lora_config.py`
  (Colab-T4 QLoRA dataclass + lazy PEFT/BnB/TrainingArgs builders),
  `ablation.py` (transparent base+RAG vs LoRA+RAG metrics, backend-agnostic),
  `model_card.py` (ModelCard generator). `scripts/generate_qa.py` CLI;
  `notebooks/09_lora_finetune_phi35.ipynb` (Colab T4, 14 cells);
  `models/phi35-lora-advising/model_card.md` (+ yaml). pyproject `finetune` extra
  (transformers/peft/trl/accelerate; bitsandbytes=Colab-only).
  +19 tests (395 total green, 1 skipped=peft). **Verify:**
  `pytest tests/test_ws3_finetune.py -q`;
  `python scripts/generate_qa.py --pathways <pathways.json> --n 500`.
- 2026-06-09 - Phase 2 advising intelligence - `drona/advising/verify.py`
  (transparent citation-grounding check → downgrades/strips ungrounded pathways).
  Qwen2.5-3B multilingual fallback in `LLMClient` (local, tries primary→fallback,
  bounded retries). `drona/advising/graph.py` - LangGraph StateGraph
  (detect_bias→retrieve→generate→verify→format, conditional retry on parse
  failure, refusal on thin coverage) wrapping the EXISTING tested components +
  `.advise()`/`.stream()`; node fns unit-testable without LangGraph. FastAPI app
  `drona/api/` (REST `POST /advise`, `GET /health`, websocket `/ws/advise`
  node-by-node streaming via thread→asyncio queue, CORS, lifespan guard that
  hard-asserts Gemini stays OUT of the request path). `scripts/run_api.py`.
  +22 tests (376 total green); LangGraph + FastAPI paths covered (importorskip on
  [dev]-only). **Verify:** `pytest tests/test_ws2b_phase2.py -q`;
  `pip install -e ".[backend]"` then `python scripts/run_api.py` → open `/docs`.
- 2026-06-09 - Phase 1 ingestion - Added source loaders: `esco.py` (ESCO v1.2.1
  CSV bulk + API fallback, ICT filter), `bls.py` (OEWS wage bands + pathway
  enrichment), `nlfs.py` (Nepal LFS PDF → citable LabourSnippets), `synthetic.py`
  (deterministic rule-based + optional local-LLM/offline-Gemini, always labelled
  & anchored). Added `pgvector_store.py` + `pinecone_store.py` (lazy-import upsert
  paths mirroring the Chroma ingestor). `DataCard` now emits Markdown alongside
  YAML (prompt's `data_card.md`). Manual-collection source subdirs + `_template.json`.
  CLI `scripts/ingest_sources.py` (esco/bls/nlfs/synthetic, all `--help` + paths).
  +20 offline tests (354 total green). **Verify:** `pytest -q`;
  `python scripts/ingest_sources.py --help`;
  `python scripts/ingest_sources.py synthetic --jobs data/manual_collection/_template.json --n 2 --out /tmp/s.json`.
- 2026-06-09 - Phase 0 gap-fill - Added: optional dep groups (backend/db/genai/eval)
  in `pyproject.toml`; expanded `.env.example` + `settings.py` with Gemini (offline-
  only, guarded), Vertex (flagged off), Pinecone, Postgres DSN, FastAPI config;
  `docker-compose.yml` (pgvector/pg16 + optional Ollama); `drona/db/` SQLAlchemy
  models + session for pgvector; Alembic scaffold + `0001_initial` migration
  (extension + 3 tables + HNSW cosine indexes); GitHub Actions CI; this ledger.
  **Verify:** `pip install -e ".[dev]"` then `pytest -q` (existing suite green);
  `python -c "import drona.utils.settings as s; print(s.settings.vector_backend)"`.

## Open Blockers (student action - see `docs/STUDENT_RUNBOOK.md`)
- **Curriculum / jobs are PLACEHOLDERS (2026-06-27)** - the pipeline is fully
  populated and run with dummy data so everything works end-to-end. Replace
  `data/raw/curriculum/*.md|pdf` (10 dummy Softwarica modules) and
  `data/manual_collection/*/*_placeholder_postings.json` (40 dummy Nepali jobs)
  with the real materials, then re-run `python scripts/scrape_jobs.py --source manual`
  + `python scripts/download_onet.py` + `python scripts/ingest_data.py`. O*NET 30.3
  is already downloaded and ingested (real). Curriculum/jobs are drop-in.
- **Live LLM advising needs Ollama** - `ollama` python pkg is installed but the
  server/binary is not. Install Ollama, `ollama serve`, and pull a model
  (e.g. `qwen2.5:3b`); retrieval (C1) already works without it.
- **Colab training runs not yet executed** - LoRA (nb 09, SFT data ready),
  ACT (nb 07), Diffusion (nb 08); copy checkpoints to `data/checkpoints/`. A CPU
  behavior-cloning baseline IS trained (`scripts/train_bc_gesture.py`).
- **ROS2/Gazebo demo not yet recorded** - runs in **WSL2 (Ubuntu 22.04) on
  Windows 11**; no dual-boot needed. ROS2 not yet installed in WSL. See
  `docs/wsl_setup.md`.
- **Demo video not yet recorded** - script at `docs/demo_video_script.md`.
- **Windows note:** run CLI scripts with `PYTHONUTF8=1` (Python 3.14 isn't UTF-8
  mode by default; the consoles use cp1252 and crash on box-drawing output).

## User-Provided Context
- 2026-06-09 - Strategy = **EXTEND** (keep working code, add missing pieces).
- 2026-06-09 - **API keys are available** (Gemini / Vertex / Pinecone). Wired into
  `.env.example` + `settings.py`. Gemini/Vertex remain OUT of the live request path.
- 2026-06-09 - Curriculum PDFs and Nepali job data **not ready yet** → build
  pipelines + templates/stubs; fill with real data later.

## Decision Log
- 2026-06-09 - Keep ChromaDB as default `VECTOR_BACKEND`; add pgvector + Pinecone
  as selectable backends. Rationale: student hardware (GTX 1650 4GB, 16GB RAM)
  runs Chroma with zero infra; Postgres/Pinecone demonstrate production scale.
- 2026-06-09 - pgvector dims fixed: curriculum 384 (bge-small-en-v1.5),
  career 1024 (JobBERT-v3). HNSW + cosine (encoders trained for cosine).
- 2026-06-09 - Gemini guarded by `allow_gemini_in_request_path=False`; offline-only
  use preserves the proposal's "local-only advising" novelty claim (C4).
- 2026-06-09 - Upgrade Mower et al. citation to the Nature Machine Intelligence
  2026 version per prompt; to be recorded in `docs/research_papers.md` (Phase 8).

## Notes for Next Session
- **All 8 phases complete.** The next session is for: viva rehearsal, recording the
  demo (see `docs/demo_video_script.md`), populating real numbers (ingest data +
  Ollama + a Colab T4 training run), or starting Phase-2 hardware work.
- Phase 7 caveat: notebooks are runnable but most need data/models for *real*
  outputs (ChromaDB via ingest, Ollama for LLM cells, a Colab T4 for 07/08/09).
  They run end-to-end with graceful skips on this box. Ragas isn't installed, so
  `ragas_harness` uses the labelled lexical-proxy backend by default.
- The live user study (robot vs traditional advising) is Phase 2 per the proposal;
  `stats.compare_conditions` is the ready-to-use harness for when that data exists.
- Phase 5 caveat: code/launch/URDF/docs are written and Python-syntax-clean, but
  `colcon build` + runtime need Ubuntu 22.04 + ROS2 Humble (and Gazebo Harmonic /
  Isaac for sim). The student has **no Ubuntu dual-boot** - this builds/runs in
  **WSL2 (Ubuntu 22.04)** on their Windows 11 box; WSLg renders Gazebo/RViz.
  Setup guide added: `docs/wsl_setup.md`. `policy_node` is the
  new action server; the older `gesture_node` (service) is kept for back-compat.
  URDF joint names == `drona.interaction.demonstration.JOINT_NAMES` so the joint
  stream drives RViz/Gazebo/Isaac unchanged. New pkg `drona_description` is
  ament_cmake (installs urdf/launch/rviz share dirs).
- Phase 6 done: `frontend/` is a standalone Next.js app (own package.json,
  node_modules gitignored). It expects the FastAPI backend at
  `NEXT_PUBLIC_DRONA_API_URL` (default http://localhost:8000). The legacy
  Streamlit dashboard (`drona/dashboard/`) still exists; the Next.js app is the
  prompt-spec frontend. Keep `lib/types.ts` in sync with `drona/contracts` +
  `drona/api/schemas.py` if contracts change. Anti-bias UI logic is pure in
  `frontend/lib/gamification.ts` (could add JS unit tests later).
- Phase 4 done: all new policy I/O uses the shared `BasePolicy` interface so
  `sim_eval.compare_policies` scores keyframe/ACT/Diffusion/SmolVLA identically.
  ACT/Diffusion train on Colab T4 (notebooks 07/08) via the LeRobot CLI on the
  `LeRobotDataset` built from keyframe-seed demos; checkpoints drop into
  `data/checkpoints/<gesture>/` for `PolicyRouter` to auto-load. SmolVLA is a
  forward-looking VLA seam (no training) that falls back to keyframes today.
- Pre-existing ruff lints in legacy interaction files (`act_policy.py`,
  `demonstration.py`, `gesture_dispatcher.py`, `visualizer.py` - unused imports,
  E702 semicolons) are NOT from Phase 4; left untouched to avoid scope creep.
  The 4 new Phase-4 modules are lint-clean. Consider a `ruff --fix` housekeeping
  pass on the interaction package later.
- Phase 3 training runs on Colab T4 via notebook 09; the repo holds all data-prep,
  config, ablation, and the model card. Re-run `scripts/generate_qa.py` once real
  pathway anchors exist in `data/processed/`.
- Phase 2 is wired through `AdvisingGraph` (LangGraph). The older imperative
  `AdvisingEngine` still exists and is used as the API fallback if LangGraph is
  missing; keep both green. `[backend]` extras are installed in the dev env
  (fastapi, langgraph, langchain-core, sse-starlette); CI still runs [dev] only,
  so backend/graph tests importorskip there.
- Optional Phase 1 leftovers (non-blocking): wire `VECTOR_BACKEND` selector into
  `scripts/ingest_data.py` so it routes to chroma/pgvector/pinecone; add salary
  columns to CareerPathwayORM if pgvector pathway wages are wanted.
- The career embedding model in `.env.example` currently says JobBERT-**v2**
  (legacy) but the prompt mandates **v3** (Decorte et al. 2025, arXiv:2507.21609).
  Reconcile to v3 when touching the embedding pipeline; `CAREER_EMBED_DIM=1024`
  is already set for v3.
- Do NOT run Alembic in CI (no Postgres there). It runs against docker-compose.
