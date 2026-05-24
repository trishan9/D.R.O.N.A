# D.R.O.N.A.
**Demonstration-learned Robotic Oracle for Nurturing Aspirations**

BSc Computing individual project — Softwarica College of IT & E-Commerce / Coventry University  
Author: Trisan Wagle

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

### Tests

```bash
pytest                          # 305 tests, ~7 seconds, no network/GPU
pytest tests/test_ws6_evaluation.py -v   # evaluation harness only
```

---

## Data sources and ethics

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
