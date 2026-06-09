# D.R.O.N.A. — Build Progress Ledger

> Cross-session handoff. Read this FIRST every session (see SESSION START
> PROTOCOL in `DRONA_BUILD_PROMPT.md`). Format defined in `PROGRESS_TEMPLATE.md`.

## Current State
- **Active phase:** Phase 0 — Repo bootstrap (closing out gaps under EXTEND strategy)
- **Active task:** Phase 0 gap-fill complete; next is Phase 1 (ESCO/BLS/NLFS ingestion, pgvector schema, synthetic generator).
- **Last commit:** see `git log -1` (Phase 0 gap-fill commit)
- **Working tree:** managed per-phase; commit between phases.

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
| 3 LoRA | — | all (synthetic Q&A, gold set, LoRA notebook, ablation, model_card) |
| 4 LeRobot | demonstration, mujoco_env, act_policy, gesture_dispatcher, train_act.py | MuJoCo upper-body env, dataset conversion, ACT+Diffusion notebooks, SmolVLA, sim eval |
| 5 ROS2/sim | ros2_ws (msgs, srvs, 5 nodes, launch) | .action defs + action server, URDF, Isaac Sim, Gazebo Harmonic, rosbag, topics doc |
| 6 Frontend | Streamlit dashboard (legacy) | Next.js 14 + Tailwind + shadcn/ui + streaming + gamification |
| 7 Evaluation | metrics, queries, harness (C1–C4) | Ragas, citation verify, scipy stats harness, 11 runnable notebooks |
| 8 Docs | architecture/eval/hardware/ros2 setup | data_ethics, phase plans, sim setup, research_papers, viva_prep, cards |

## Phase Status
| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 0 | Repo bootstrap | ◐ | gap-fill done (this commit); see below |
| 1 | Contracts + data pipeline | ◐ | contracts + O*NET + Chroma exist; extending |
| 2 | Advising intelligence | ◐ | core RAG/bias exist; need LangGraph + FastAPI |
| 3 | LoRA fine-tune | ☐ | |
| 4 | LeRobot policies | ◐ | ACT scaffolding exists; need notebooks + Diffusion + SmolVLA |
| 5 | ROS2 + simulation | ◐ | ros2_ws exists; need actions + sim |
| 6 | Frontend | ◐ | Streamlit legacy; need Next.js |
| 7 | Evaluation | ◐ | C1–C4 harness exists; need Ragas + stats |
| 8 | Documentation | ◐ | partial docs exist |

(☐ not started · ◐ in progress · ☑ complete)

## What Shipped (most recent first)
- 2026-06-09 — Phase 0 gap-fill — Added: optional dep groups (backend/db/genai/eval)
  in `pyproject.toml`; expanded `.env.example` + `settings.py` with Gemini (offline-
  only, guarded), Vertex (flagged off), Pinecone, Postgres DSN, FastAPI config;
  `docker-compose.yml` (pgvector/pg16 + optional Ollama); `drona/db/` SQLAlchemy
  models + session for pgvector; Alembic scaffold + `0001_initial` migration
  (extension + 3 tables + HNSW cosine indexes); GitHub Actions CI; this ledger.
  **Verify:** `pip install -e ".[dev]"` then `pytest -q` (existing suite green);
  `python -c "import drona.utils.settings as s; print(s.settings.vector_backend)"`.

## Open Blockers
- **Curriculum PDFs not yet provided** — needed at `data/raw/curriculum/` for
  Phase 1 curriculum parsing. Pipeline will be built to load from there; runs on
  whatever is present.
- **Nepali job postings not yet collected** — manual JSON collection (~150–200).
  A template loader will accept them when ready; ToS forbids scraping.

## User-Provided Context
- 2026-06-09 — Strategy = **EXTEND** (keep working code, add missing pieces).
- 2026-06-09 — **API keys are available** (Gemini / Vertex / Pinecone). Wired into
  `.env.example` + `settings.py`. Gemini/Vertex remain OUT of the live request path.
- 2026-06-09 — Curriculum PDFs and Nepali job data **not ready yet** → build
  pipelines + templates/stubs; fill with real data later.

## Decision Log
- 2026-06-09 — Keep ChromaDB as default `VECTOR_BACKEND`; add pgvector + Pinecone
  as selectable backends. Rationale: student hardware (GTX 1650 4GB, 16GB RAM)
  runs Chroma with zero infra; Postgres/Pinecone demonstrate production scale.
- 2026-06-09 — pgvector dims fixed: curriculum 384 (bge-small-en-v1.5),
  career 1024 (JobBERT-v3). HNSW + cosine (encoders trained for cosine).
- 2026-06-09 — Gemini guarded by `allow_gemini_in_request_path=False`; offline-only
  use preserves the proposal's "local-only advising" novelty claim (C4).
- 2026-06-09 — Upgrade Mower et al. citation to the Nature Machine Intelligence
  2026 version per prompt; to be recorded in `docs/research_papers.md` (Phase 8).

## Notes for Next Session
- Phase 1 first: build ESCO v1.2.1 + BLS OEWS + NLFS PDF ingestion scripts under
  `drona/data_pipeline/`, each with `--help` + path args + Pydantic-validated
  output + a `data/cards/<dataset>_data_card.md`. Then the synthetic generator
  (local Phi-3.5 primary, Gemini optional/offline). Then a pgvector ingest path
  parallel to the existing Chroma `ingest.py`.
- The career embedding model in `.env.example` currently says JobBERT-**v2**
  (legacy) but the prompt mandates **v3** (Decorte et al. 2025, arXiv:2507.21609).
  Reconcile to v3 when touching the embedding pipeline; `CAREER_EMBED_DIM=1024`
  is already set for v3.
- Do NOT run Alembic in CI (no Postgres there). It runs against docker-compose.
