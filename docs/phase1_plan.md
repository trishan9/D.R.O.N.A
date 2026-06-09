# Phase 1 Plan — Core System (this deliverable)

Phase 1 is the **complete, runnable software system** delivered for the BSc final
project. Everything except the physical robot-hardware swap and the live student
user study is in scope.

## Objectives (mapped to research contributions)

| Objective | Contribution | Status |
|---|---|---|
| Hybrid retrieval over Nepal-first knowledge base | C1 | ☑ |
| Cognitive-bias-aware advising | C2 | ☑ |
| Smoother robot gestures via imitation learning (sim) | C3 | ☑ |
| Local, open-source, Nepal-grounded stack | C4 | ☑ |

## Architecture (Phase 1)

- **In-process Python library** (`drona/`) holds all business logic, behind Pydantic
  contracts that are designed to be ROS2-portable (so Phase 2 is a transport swap,
  not a rewrite).
- **FastAPI** exposes REST + websocket advising endpoints (local-only LLM path).
- **Next.js 14** frontend provides the anti-bias advising dashboard.
- **ROS2 Humble** packages + **Gazebo/Isaac** simulation provide the embodied layer,
  validated in simulation (no physical arm required for Phase 1).

## Workstreams delivered

| WS | Scope | Key artefacts |
|---|---|---|
| WS0 | Repo bootstrap | `pyproject.toml`, `docker-compose.yml`, Alembic, CI, `.env.example`, `PROGRESS.md` |
| WS1 | Contracts + data pipeline | `contracts.py`, O\*NET/ESCO/BLS/NLFS loaders, manual JSON loader, synthetic generator, three-tier provenance, ChromaDB/pgvector/Pinecone |
| WS2 | Advising intelligence | dual-embedding index, hybrid retrieval + reranker, bias detector, LangGraph orchestration, Ollama client, FastAPI websocket |
| WS3 | LoRA fine-tune | synthetic Q&A gen, gold set, LoRA config + Colab notebook, base-vs-LoRA ablation |
| WS4 | LeRobot policies | `LeRobotDataset` conversion, ACT + Diffusion wrappers, SmolVLA, `sim_eval` |
| WS5 | ROS2 + simulation | `ExecuteGesture.action`, `policy_node` action server, URDF, Gazebo/Isaac launch, rosbag |
| WS6 | Next.js frontend | profile builder, streaming chat, pathway cards, anti-bias gamification |
| WS7 | Evaluation | C1–C4 harness, Ragas harness, bias-mitigation metrics, scipy.stats, citation eval, 11 notebooks |
| WS8 | Documentation | architecture (+mermaid), data ethics, data/model cards, viva prep, demo script |

## Hardware reality (Phase 1)

- Student laptop: Ubuntu 22.04 dual-boot, GTX 1650 4 GB VRAM, 16 GB RAM.
- Anything > 4 GB VRAM (LoRA/ACT/Diffusion training) runs in a **Colab T4 notebook**.
- Serving LLM: Ollama with Phi-3.5-mini Q4_K_M (fits in 4 GB); Qwen2.5-3B fallback.
- Simulation: **Gazebo Harmonic** is the low-VRAM default; Isaac Sim is documented
  for an ≥8 GB GPU or cloud.

## Definition of done (Phase 1)

- Every module runnable + tested (pytest green).
- Every output validates against a Pydantic contract.
- Every dataset has a data card; every trained model has a model card.
- Full system launchable: `docker compose up`, `python scripts/run_api.py`,
  `cd frontend && npm run dev`, `ros2 launch drona_bringup drona_system.launch.py`.
- Evaluation harness produces a JSON report for the thesis appendix.

## Explicitly deferred to Phase 2

See [`phase2_plan.md`](./phase2_plan.md): physical SO-100 arm, live student user
study, multilingual Nepali code-switch in production.
