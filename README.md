# D.R.O.N.A.
**Demonstration-learned Robotic Oracle for Nurturing Aspirations**

BSc Computing individual project — Softwarica College of IT & E-Commerce / Coventry University  
Author: Trisan Wagle

> **Start here if you are Trisan:** [`docs/STUDENT_RUNBOOK.md`](docs/STUDENT_RUNBOOK.md) —
> complete step-by-step guide: what data to collect, where to put files, which scripts
> to run in order, local vs Colab vs Ubuntu, time estimates, and what's left for you.

**Build status:** Phases 0–8 complete · `pytest` 431 pass · software ready · your data +
Colab training runs + demo recording remain.

---

## Overview

D.R.O.N.A. is a bias-aware robotic academic advising system designed for the Nepali
computing student context. It combines a 6-DOF robot arm with a Retrieval-Augmented
Generation (RAG) advising pipeline to help BSc Computing students explore career pathways
grounded in local (Nepal-tier) evidence.

The system makes four original research contributions:

| ID | Contribution | Key technique |
|----|-------------|---------------|
| C1 | Hybrid retrieval outperforms dense-only | BM25 + dense embeddings + Reciprocal Rank Fusion (RRF) |
| C2 | Cognitive-bias-aware advising | Rule-based bias detection → bias-flagged system prompt |
| C3 | Smoother robot gestures than keyframe baseline | LeRobot ACT imitation learning |
| C4 | Nepal-local open-source stack | Nepal-first citation tier ordering; no paid APIs |

---

## Architecture

```
drona/
├── contracts.py              # Pydantic inter-module contracts (ROS2-portable)
├── data_pipeline/            # WS1 — scrapers, O*NET loader, ChromaDB ingestor
│   ├── scrapers/             #   MeroJob, Merojob manual loader, O*NET XML
│   └── ingest.py             #   dual-collection ChromaDB indexer
├── advising/                 # WS2 — RAG + bias-aware LLM engine
│   ├── retriever.py          #   hybrid BM25+dense RRF retriever
│   ├── bias_detector.py      #   rule-based 6-type cognitive bias detector
│   ├── prompt_builder.py     #   bias-aware system prompt construction
│   ├── llm_client.py         #   Ollama/Phi-3.5 JSON generation client
│   └── engine.py             #   AdvisingEngine: 4-stage advise() pipeline
├── interaction/              # WS3 — robot gesture policy
│   ├── demonstration.py      #   DemonstrationDataset, keyframe interpolation
│   ├── mujoco_env.py         #   StubEnv / MuJoCoEnv (graceful fallback)
│   ├── act_policy.py         #   KeyframePolicy + LeRobotACTPolicy + PolicyRouter
│   └── gesture_dispatcher.py #   GestureDispatcher: execute() → InteractionActionResult
├── perception/               # WS4 — engagement detection
│   └── mediapipe_detector.py #   MediaPipeDetector / StubDetector (EMA smoothing)
├── orchestrator/             # WS4 — session lifecycle
│   ├── session_machine.py    #   5-state FSM + SessionContext
│   └── orchestrator.py       #   Orchestrator.tick() main loop
├── dashboard/                # WS5 — Streamlit UI (anti-anchoring layout)
│   ├── session_bridge.py     #   SessionBridge wraps AdvisingEngine for Streamlit
│   ├── components.py         #   pure formatting helpers (fully testable)
│   └── app.py                #   Streamlit app entry point
├── evaluation/               # WS6 — evaluation harness
│   ├── queries.py            #   synthetic labelled query bank (C1–C4)
│   ├── metrics.py            #   pure metric functions (NDCG, MRR, F1, jerk…)
│   └── harness.py            #   EvaluationHarness.run_all() → EvaluationReport
└── utils/
    ├── settings.py           #   Pydantic-settings config (reads .env)
    └── logging.py            #   Loguru setup
scripts/
├── ingest_data.py            # Index all data into ChromaDB
└── run_evaluation.py         # Run C1–C4 evaluation and save JSON report
tests/                        # 305 tests — no network, no GPU required
```

---

## Hardware requirements

| Component | Minimum | Used in |
|-----------|---------|---------|
| GPU | NVIDIA GTX 1650 4 GB | ACT training (optional) |
| RAM | 8 GB | All stages |
| Storage | 10 GB free | Embeddings + ChromaDB |
| OS | Windows 10/11 or Linux | Tested on Windows 11 |

All inference runs locally. No paid APIs. No internet required after setup.

---

## Setup

### 1. Install dependencies

```bash
pip install -e ".[dev,dashboard]"
```

For robot/MuJoCo support (optional):

```bash
pip install mujoco
# LeRobot must be installed from source:
# https://github.com/huggingface/lerobot
```

For perception (optional):

```bash
pip install mediapipe opencv-python
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set OLLAMA_MODEL and DATA_* paths
```

### 3. Start Ollama (for LLM advising)

```bash
ollama pull phi3.5:3.8b-mini-instruct-q4_K_M
ollama serve
```

### 4. Index data

```bash
# Add Nepali job data to data/manual_collection/ first (see data/manual_collection/README.md)
python scripts/ingest_data.py
```

---

## Running

### Dashboard (recommended)

```bash
streamlit run drona/dashboard/app.py
```

### Evaluation harness

```bash
# C2 (bias detection) + C3 (gesture smoothness) — no external deps needed
python scripts/run_evaluation.py

# All contributions (needs ChromaDB populated and Ollama running)
python scripts/run_evaluation.py --all --llm

# Specific contributions
python scripts/run_evaluation.py --c2 --c3
```

Results are saved as JSON to `data/evaluation/report_<timestamp>.json`.

### Web frontend (Next.js 14 — multi-page platform)

A full sidebar-navigated app (Dashboard · Advisor · Pathways · Skills · Analytics ·
Robot Control · Profile · Achievements · Preferences · About) with light/dark
theming. The Robot Control page is an in-browser 6-DOF gesture twin that can also
drive the **live** ROS2 robot via rosbridge. See [`frontend/README.md`](frontend/README.md).

```bash
cd frontend && npm install && npm run dev   # http://localhost:3000
# Requires the API running: python scripts/run_api.py
# Optional live robot (in WSL2): ros2 launch drona_bringup drona_system.launch.py rosbridge:=true
```

### Robot simulation (ROS2 Humble — run in WSL2 on Windows)

No Ubuntu dual-boot needed: ROS2 + Gazebo run inside **WSL2 (Ubuntu 22.04)** and
WSLg shows the windows on your Windows desktop. One-time setup: [`docs/wsl_setup.md`](docs/wsl_setup.md).
Then, **inside the WSL Ubuntu shell**:

```bash
cd ros2_ws && colcon build --symlink-install && source install/setup.bash
ros2 launch drona_bringup drona_system.launch.py use_rviz:=true
```

### Tests

```bash
pytest                                   # full suite (431 pass, 1 skipped), no network/GPU
pytest tests/test_ws7_phase7_eval.py -v  # evaluation harness only
```

---

## Documentation

| Doc | What it covers |
|---|---|
| **[`docs/STUDENT_RUNBOOK.md`](docs/STUDENT_RUNBOOK.md)** | **Your operational guide** — data, scripts, Colab, ROS2, timeline |
| **[`docs/COLAB_TRAINING_GUIDE.md`](docs/COLAB_TRAINING_GUIDE.md)** | **Train the GPU models on Colab/Kaggle**, bring checkpoints back, finalize + simulate |
| [`docs/architecture.md`](docs/architecture.md) | System design + **mermaid** diagrams |
| [`docs/phase1_plan.md`](docs/phase1_plan.md) / [`docs/phase2_plan.md`](docs/phase2_plan.md) | Delivered scope vs deferred (hardware + study) |
| [`docs/data_ethics.md`](docs/data_ethics.md) | PII policy, licensing matrix, scraping prohibitions |
| [`docs/data_cards/`](docs/data_cards/) | One data card per dataset |
| [`models/*/model_card.md`](models/) | One model card per trained model |
| [`docs/research_papers.md`](docs/research_papers.md) | Paper → design-choice grounding |
| [`docs/ros2_topics_actions.md`](docs/ros2_topics_actions.md) | Every ROS2 topic / action / service |
| [`docs/wsl_setup.md`](docs/wsl_setup.md) | **Run ROS2 + Gazebo on Windows via WSL2** (no dual-boot) |
| [`docs/sim_setup_gazebo.md`](docs/sim_setup_gazebo.md) / [`docs/sim_setup_isaac.md`](docs/sim_setup_isaac.md) | Simulator setup |
| [`docs/viva_prep.md`](docs/viva_prep.md) | Anticipated examiner questions + answers |
| [`docs/demo_video_script.md`](docs/demo_video_script.md) | Shot-by-shot demo script |
| [`PROGRESS.md`](PROGRESS.md) | Live build ledger |

---

## Data sources and ethics

Full licensing matrix, PII policy, and scraping prohibitions: [`docs/data_ethics.md`](docs/data_ethics.md).

| Source | Type | License / access |
|--------|------|-----------------|
| Softwarica curriculum PDFs | Curriculum | Institution-provided |
| O*NET 28.3 | Occupation data | Public domain (US DOL) |
| Nepal job portals (MeroJob) | Career postings | Manual collection — robots.txt checked |
| Synthetic evaluation queries | Eval only | Generated; labelled as `tier=synthetic` |

**Data policy:**
- Zero PII collected, stored, or used at any layer
- Synthetic data is labelled at the schema level (`DataTier.SYNTHETIC`)
- LinkedIn data is never used (ToS prohibition)
- All sources are open-access or manually collected with ToS verification

---

## Research contributions — evaluation summary

Run `python scripts/run_evaluation.py --all` after indexing data to reproduce all numbers.

**C1 — Hybrid retrieval:** NDCG@5 and MRR across 10 labelled queries; hybrid vs dense-only.

**C2 — Bias detection:** Precision / Recall / F1 per bias type and macro-average across
17 labelled queries (14 biased, 3 clean). Bias types: availability heuristic, anchoring,
confirmation bias, Dunning–Kruger effect, loss aversion, consistency bias.

**C3 — Gesture smoothness:** Mean absolute jerk (rad/s³) and path length for KeyframePolicy
baseline. ACT-trained policies are compared against these numbers post-training.

**C4 — Nepal stack:** Nepal citation ratio for local-preference queries; target ≥ 40%.
Generation latency (mean, p95) for full pipeline and retrieval-only.

---

## Project timeline

| Week | Work stream | Status |
|------|-------------|--------|
| 1 | WS1 — data pipeline | Complete |
| 1–2 | WS2 — advising intelligence (C1, C2) | Complete |
| 2 | WS3 — robot interaction / ACT (C3) | Complete |
| 3 | WS4 — orchestrator + perception | Complete |
| 3 | WS5 — Streamlit dashboard | Complete |
| 4 | WS6 — evaluation harness | Complete |

---

## Acknowledgements

- [LeRobot](https://github.com/huggingface/lerobot) — ACT policy implementation
- [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) — curriculum embeddings
- [TechWolf/JobBERT-v2](https://huggingface.co/TechWolf/JobBERT-v2) — career embeddings
- [Ollama](https://ollama.com/) — local LLM serving
- O*NET Resource Center (US Department of Labor) — occupation data
