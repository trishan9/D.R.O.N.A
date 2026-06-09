# D.R.O.N.A. — Build Progress Ledger

> Cross-session handoff. Read this FIRST every session (see SESSION START
> PROTOCOL in `DRONA_BUILD_PROMPT.md`). Format defined in `PROGRESS_TEMPLATE.md`.

## Current State
- **Active phase:** Phase 5 — ROS2 + simulation (action server, URDF, Gazebo/Isaac launch, full launch, rosbag, docs done)
- **Active task:** Phase 5 complete (code/launch/docs; needs Ubuntu+ROS2 to colcon-build & run). Next: Phase 7, then Phase 8.
- **Last commit:** see `git log -1` (Phase 5 commit)
- **Working tree:** managed per-phase; commit between phases.
- **User sequencing:** Phase 6 was built before Phase 5 at the user's request; both now done.

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
| 0 | Repo bootstrap | ☑ | gap-fill done |
| 1 | Contracts + data pipeline | ☑ | ESCO/BLS/NLFS/synthetic + stores + cards done; backend wiring optional |
| 2 | Advising intelligence | ☑ | LangGraph orchestration + citation verify + Qwen fallback + FastAPI (REST+WS) |
| 3 | LoRA fine-tune | ☑ | Q&A gen + SFT format + gold curation + LoRA config + ablation + Colab notebook + model_card; training runs on Colab T4 |
| 4 | LeRobot policies | ☑ | LeRobot dataset conversion + sim eval (success/jerk) + Diffusion wrapper + SmolVLA seam + notebooks 07/08; training runs on Colab T4 |
| 5 | ROS2 + simulation | ☑ | ExecuteGesture.action + policy_node action server (feedback/cancel), drona_description humanoid URDF + RViz, Gazebo Harmonic + Isaac launch (+ standalone stage script), full-system launch (rviz + rosbag), docs (gazebo/isaac/topics-actions); colcon build needs Ubuntu+ROS2 |
| 6 | Frontend | ☑ | Next.js 14 App Router + Tailwind + shadcn/ui: WS streaming chat, profile builder (no PII), multi-pathway + comparison + citation drill-down, anti-bias gamification (diversity/badges/skill-map/counter-rec/reversibility), bias flags; build+typecheck green |
| 7 | Evaluation | ◐ | C1–C4 harness exists; need Ragas + stats |
| 8 | Documentation | ◐ | partial docs exist |

(☐ not started · ◐ in progress · ☑ complete)

## What Shipped (most recent first)
- 2026-06-09 — Phase 5 ROS2 + simulation — `drona_msgs/action/ExecuteGesture.action`
  (goal/result/feedback; wired into CMakeLists + package.xml with action_msgs).
  `drona_ros/policy_node.py` — ROS2 **ActionServer** wrapping the LeRobot/keyframe
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
- 2026-06-09 — Phase 6 Next.js frontend — `frontend/` Next.js 14 App Router +
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
- 2026-06-09 — Phase 4 LeRobot policies — `drona/interaction/lerobot_dataset.py`
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
- 2026-06-09 — Phase 3 LoRA fine-tune — `drona/finetune/`: `qa_generator.py`
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
- 2026-06-09 — Phase 2 advising intelligence — `drona/advising/verify.py`
  (transparent citation-grounding check → downgrades/strips ungrounded pathways).
  Qwen2.5-3B multilingual fallback in `LLMClient` (local, tries primary→fallback,
  bounded retries). `drona/advising/graph.py` — LangGraph StateGraph
  (detect_bias→retrieve→generate→verify→format, conditional retry on parse
  failure, refusal on thin coverage) wrapping the EXISTING tested components +
  `.advise()`/`.stream()`; node fns unit-testable without LangGraph. FastAPI app
  `drona/api/` (REST `POST /advise`, `GET /health`, websocket `/ws/advise`
  node-by-node streaming via thread→asyncio queue, CORS, lifespan guard that
  hard-asserts Gemini stays OUT of the request path). `scripts/run_api.py`.
  +22 tests (376 total green); LangGraph + FastAPI paths covered (importorskip on
  [dev]-only). **Verify:** `pytest tests/test_ws2b_phase2.py -q`;
  `pip install -e ".[backend]"` then `python scripts/run_api.py` → open `/docs`.
- 2026-06-09 — Phase 1 ingestion — Added source loaders: `esco.py` (ESCO v1.2.1
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
- Phase 7 (evaluation harness) is next, then Phase 8 (docs). Phases 5 and 6 done.
- Phase 5 caveat: code/launch/URDF/docs are written and Python-syntax-clean, but
  `colcon build` + runtime need Ubuntu 22.04 + ROS2 Humble (and Gazebo Harmonic /
  Isaac for sim). Cannot be built on this Windows dev box. `policy_node` is the
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
  `demonstration.py`, `gesture_dispatcher.py`, `visualizer.py` — unused imports,
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
