# Research Papers — Grounding for Every Design Choice

Each architectural decision in D.R.O.N.A. is grounded in a cited paper. This table
maps **paper → where it is used → why**. It is maintained as the system is built
(proposal requirement) and is the reference for the literature defence at viva.

---

## Core mapping

| # | Paper | Grounds (where in D.R.O.N.A.) | Why this choice |
|---|---|---|---|
| 1 | **Lewis et al. 2020**, "Retrieval-Augmented Generation for Knowledge-Intensive NLP", arXiv:2005.11401 | `drona/advising/engine.py`, `retriever.py`, citation-grounding `verify.py` | RAG grounds LLM output in retrieved evidence; the citation-verification stage operationalises RAG's faithfulness claim |
| 2 | **Decorte et al. 2025**, "JobBERT-v3", arXiv:2507.21609 | Career embedding model (`embeddings.py`, dual index) | Domain-specialised job embeddings separate career text better than general models (validated in `notebooks/03_embedding_quality.ipynb`) |
| 3 | **Tversky & Kahneman 1974**, "Judgment under Uncertainty: Heuristics and Biases", *Science* | `drona/advising/bias_detector.py` (six biases), bias-aware prompt | Defines the cognitive biases (availability, anchoring, confirmation, etc.) the system detects and counters |
| 4 | **Kahneman & Tversky 1979**, "Prospect Theory", *Econometrica* | Loss-aversion detection; frontend **reversibility tags** (`reversibility-viz.tsx`) | Students over-weight perceived losses; reversibility framing counters loss aversion in decision UI |
| 5 | **Zhao et al. 2023**, "Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware" (ACT), arXiv:2304.13705 | `drona/interaction/act_policy.py`, `notebooks/07_lerobot_act_training.ipynb` | ACT (action-chunking transformer) is the imitation-learning policy for smoother gestures than the keyframe baseline (C3) |
| 6 | **Chi et al. 2023**, "Diffusion Policy", arXiv:2303.04137 | `drona/interaction/diffusion_policy.py`, `notebooks/08_lerobot_diffusion_policy.ipynb` | Diffusion Policy is the C3 ablation comparison to ACT |
| 7 | **Capuano et al. 2025**, "Robot Learning: A Tutorial", arXiv:2510.12403 | LeRobot dataset/training conventions (`lerobot_dataset.py`) | Canonical reference for the LeRobot ACT/Diffusion stack and `LeRobotDataset` v2 format |
| 8 | **Mower et al. 2026**, "A robot operating system framework for using large language models in embodied AI", *Nature Machine Intelligence* | ROS2 LLM-in-the-loop architecture (`ros2_ws/`, `policy_node.py`) | Upgraded citation (replaces proposal's arXiv:2406.19741) for LLM↔ROS2 embodied integration |
| 9 | **Macenski et al. 2022**, "Robot Operating System 2", *Science Robotics* | ROS2 Humble node/action/topic design (`docs/ros2_topics_actions.md`) | Foundational justification for ROS2 as the deployment middleware |
| 10 | **Belpaeme et al. 2018**, "Social robots for education: A review", *Science Robotics* | Embodied advising rationale; gesture vocabulary (greet/nod/point/listen) | Evidence that social-robot embodiment improves educational engagement — the project's premise |
| 11 | **Iatrellis et al. 2024**, "Leveraging Generative AI for Sustainable Academic Advising", *Sustainability* 16(17):7829 | Advising-engine framing; sustainability/local-stack argument (C4) | Direct precedent for GenAI academic advising; supports the low-cost local-stack design |
| 12 | **Es et al. 2023**, "RAGAS: Automated Evaluation of RAG" | `drona/evaluation/ragas_harness.py` | Faithfulness / answer-relevancy / context-precision-recall metrics for RAG quality |

---

## Supporting methodology references

| Topic | Reference | Used by |
|---|---|---|
| Hybrid fusion (RRF) | Cormack et al. 2009, "Reciprocal Rank Fusion" | `retriever.py` hybrid fusion (C1) |
| Cross-encoder reranking | Nogueira & Cho 2019, "Passage Re-ranking with BERT" | `reranker.py` (bge-reranker-base) |
| NDCG / IR metrics | Manning et al., *Introduction to IR* §8.4 | `evaluation/metrics.py` |
| MRR | Voorhees, TREC-8 QA, 1999 | `evaluation/metrics.py` |
| Effect sizes | Cohen 1988 | `evaluation/stats.py` (Cohen's d) |
| Non-parametric tests | Mann & Whitney 1947; Wilcoxon 1945 | `evaluation/stats.py` |
| Welch's t-test | Welch 1947 | `evaluation/stats.py` |
| Motion smoothness (jerk) | Hogan 2009, "Revisiting the minimum-jerk hypothesis" | `evaluation/metrics.py` (C3 jerk) |
| QLoRA / PEFT | Dettmers et al. 2023, "QLoRA"; Hu et al. 2021, "LoRA" | `drona/finetune/`, `notebooks/09_*` |
| HRI study stats practice | Bartneck et al. 2020, *Human–Robot Interaction* | `evaluation/stats.py` design (small-N robustness) |

---

## How to extend

When you add a design decision, add a row here citing the paper that justifies it,
and reference this file from the code comment (e.g. `# see research_papers.md #5`).
A choice without a citation is a viva liability.
