# D.R.O.N.A. — Complete System Reference

**D**emonstration-learned **R**obotic **O**racle for **N**urturing **A**spirations —
a bias-aware robotic academic advisor for Softwarica College, Kathmandu.

This is the single reference for the dissertation: every model, every dataset,
every evaluation metric (with measured results), and every AI/ML and robotics
concept the system uses. Numbers here are read from the actual artefacts in
`reports/` and `data/`, not estimates.

---

## 1. System architecture — three tiers

```
 TIER 1: EDGE                TIER 2: ROBOT                  TIER 3: BRAIN
 Raspberry Pi + USB cam      dev box / robot SBC            Colab T4 / any GPU
 ───────────────────────     ────────────────────────       ───────────────────
 perception_node             orchestrator_node (FSM)        FastAPI /advise
 MediaPipe BlazeFace         gesture_node / policy_node     hybrid RAG + rerank
 → /drona/engagement         approach_node → /cmd_vel       bias detection
                             speech_node  → TTS             Qwen3-4B + LoRA (EN)
                             Gazebo Harmonic or hardware    Himalaya Gemma (NE)
        │                            │                              │
        └──────── ROS 2 DDS ─────────┴────────── HTTPS /advise ─────┘
```

The split exists because the three workloads have incompatible resource
profiles: perception needs a camera, embodiment needs low-latency control, and
the brain needs a GPU. See `docs/distributed_deployment.md`.

---

## 2. Models — what, where, why

### 2.1 Language models (the advising brain)

| Model | Role | Why this one |
|---|---|---|
| **Qwen3-4B-Instruct-2507** + **LoRA adapter** | Primary/English advising | Strongest ~4B open instruct model, Apache-2.0, runs at Q4 on modest hardware. Fine-tuned on the Softwarica goal×bias corpus. |
| **himalaya-gemma-4-e2b-it (GGUF `:Q4_K_M`)** | Nepali advising | Nepali-specialised. **Must** use the Q4 quant — the bf16 (9.3 GB) crashes on a <10 GB GPU (Gemma-3n `GGML_SCHED` assert). It is a **reasoning model**: `think=False` is mandatory or it returns empty. |
| **Qwen2.5-3B-Instruct** | Fallback | Lighter, multilingual; backstops Nepali when Gemma is absent. |

**Fine-tuning:** LoRA (PEFT), r=16, α=32, all-linear target modules, bf16 on A100.
Adapter at `models/advising-lora` (~132 MB). Serving: `transformers` (adapter
loaded directly, no GGUF conversion) or `ollama` (GGUF, faster on CPU).

### 2.2 Retrieval models

| Model | Role |
|---|---|
| **BAAI/bge-small-en-v1.5** | Curriculum embeddings (dense) |
| **TechWolf/JobBERT-v2** | Career/job-posting embeddings (domain-specific) |
| **BAAI/bge-reranker-v2-m3** | Cross-encoder reranking (multilingual, top-20 → top-5) |
| **BM25 (rank-bm25)** | Lexical retrieval, fused with dense via RRF |

### 2.3 Perception

| Model | Role |
|---|---|
| **MediaPipe BlazeFace short-range** (Tasks API) | Face detection → engagement. ~230 KB, CPU, ~5 ms/frame. |

> Modern MediaPipe removed the legacy `mp.solutions` API; the system uses the
> **Tasks API** (`vision.FaceDetector`). `numpy<2` is mandatory (ROS 2 Jazzy ships
> numpy 1.26 and MediaPipe's deps are built against 1.x).

### 2.4 Gesture / motor policies (tiered fallback)

`PolicyRouter` tries each tier and falls back, so the robot always moves:

| Tier | Policy | Notes |
|---|---|---|
| 1 | **SmolVLA** (LoRA-tuned) | Vision-language-action; needs a checkpoint |
| 2 | **ACT** (Action Chunking Transformer) | State-only and camera variants |
| 3 | **Diffusion Policy** | Trained in notebook 06 |
| 4 | **ONNX BC** / **Torch BC** | Behaviour cloning MLP, exported to ONNX for edge |
| 5 | **KeyframePolicy** (minimum-jerk) | Always available, zero dependencies |

Six gestures: `greet`, `nod`, `point`, `listen`, `idle`, `farewell`.

### 2.5 Speech (TTS)

`espeak-ng` (offline) · **Piper** (offline neural) · **ElevenLabs
`eleven_multilingual_v2`** (natural, English **and** Nepali) · `log` fallback.

---

## 3. Datasets — sources, sizes, tiers

Everything is tiered `nepal | regional | international | synthetic` so the
advisor can prefer local evidence (contribution C4).

| Dataset | Size (measured) | Source | Use |
|---|---|---|---|
| **Softwarica curriculum** | **87 modules** → **2,348 chunks** in ChromaDB | College LMS (authenticated scrape) + public handbooks | Grounding for module/pathway advice |
| **O\*NET career pathways** | **39 pathways** | O\*NET 30.3 database | Career taxonomy, skills, education levels |
| **Job postings** | **297 postings** → **336 career docs** | Nepali job boards + HuggingFace international set | Local + international market evidence |
| **ESCO** | skills taxonomy | EU ESCO | Skill normalisation / crosswalk |
| **BLS** | salary bands | US Bureau of Labor Statistics | International salary context |
| **SFT corpus** | **639 unique QA pairs** | Generated (`drona/finetune/qa_generator.py`) | LoRA fine-tuning: goal × bias cross-product |
| **Gesture demonstrations** | 6 gestures × episodes | Teleop/keyframe recordings → LeRobot format | Imitation learning (BC/ACT/Diffusion/SmolVLA) |
| **Evaluation ground truth** | **36 queries / 70 module labels** | Hand-labelled | C1 retrieval evaluation |

> **Privacy/ethics:** LMS lecture content is authenticated material and is
> **git-ignored** (never pushed to the public repo). No LinkedIn scraping (ToS).
> No student PII: profiles are session-scoped random UUIDs, never persisted.

---

## 4. Evaluation — metrics, how to measure, measured results

Run everything: `python -m drona.evaluation.harness` → `reports/evaluation_report.json`.

### C1 — Retrieval quality (hybrid RAG)

**Metrics:** NDCG@5, MRR, Recall@5, Precision@5, scored at **module level**
against hand-labelled ground truth (not the system's own output — that would be
circular).

**Measured (36 queries, 70 labels):**

| System | NDCG@5 | MRR | Recall@5 | Precision@5 |
|---|---|---|---|---|
| BM25 only | 0.871 | 0.854 | 0.813 | 0.272 |
| Dense only | 0.909 | 0.869 | 0.909 | 0.328 |
| **Hybrid (RRF)** | **0.941** | **0.935** | 0.884 | 0.311 |

**Claim:** hybrid fusion beats either retriever alone on ranking quality
(NDCG +0.07 over BM25, +0.03 over dense; MRR +0.066 over dense).

### C2 — Cognitive bias detection

**Metrics:** per-bias-type Precision / Recall / F1 + **macro-F1**, plus a
false-positive guard on neutral queries.

**Measured (16 queries: 13 biased, 3 clean):**

| Bias type | Precision | Recall | F1 |
|---|---|---|---|
| availability_heuristic | 1.000 | 1.000 | 1.000 |
| anchoring | 1.000 | 1.000 | 1.000 |
| confirmation | 1.000 | 1.000 | 1.000 |
| dunning_kruger | 1.000 | 1.000 | 1.000 |
| loss_aversion | 1.000 | 1.000 | 1.000 |
| consistency | 1.000 | 1.000 | 1.000 |
| **Macro** | **1.000** | **1.000** | **1.000** |

Reached by widening patterns to how students *actually* phrase things — hedged
under-confidence ("I'm **probably** not smart enough"), narrowing ("**focus only
on** AI"), numeric salary anchors ("earning **Rs 80,000**"), and appeals to
consensus ("**Everyone says** cloud is the future"). Earlier iterations scored
macro-F1 0.86 (anchoring R=0.50, confirmation R=0.33).

**Demo:** `python scripts/demo_bias_detection.py` → 6/6 types fire, **0 false
positives** on the neutral control.

> Precision 1.000 matters as much as recall here: falsely accusing a student of a
> cognitive bias would be worse than missing one.

### C3 — Gesture quality (imitation learning)

**Metrics:** success rate (reached apex **and** returned to rest), **jerk**
(smoothness, lower is better) on both the *achieved* trajectory and the
*commanded* signal, joint-space path length, apex error.

**Measured (keyframe baseline, all 6 gestures within spec):**

| Gesture | Frames | Jerk (rad/s³) | Path (rad) |
|---|---|---|---|
| greet | 38 | 23.24 | 2.036 |
| nod | 24 | 10.72 | 0.249 |
| point | 38 | 5.86 | 1.001 |
| listen | 43 | 2.57 | 0.465 |
| farewell | 37 | 27.12 | 2.235 |
| idle | 20 | 0.00 | 0.000 |
| **Mean** | — | **11.59** | **0.998** |

BC vs keyframe: **100 % success** for both; BC is **13 % smoother on command
jerk** (the motor-relevant signal).

> **Honesty note:** the stub environment low-pass filters both policies, so a
> per-step BC policy cannot beat a deterministic replay on *achieved* jerk. The
> defensible claim is on **command jerk** (motor stress), which is what was
> reported.

### C4 — Local-first, zero-cost

**Metrics:** Nepal citation ratio (share of citations from Nepali sources for
locally-framed queries); no paid API dependency.

**Measured:** **Nepal citation ratio = 100 %** (target ≥ 40 %) ✅.
Retrieval latency: **mean 242 ms, p95 437 ms**. All models are open-weight and
run locally or on your own GPU — **no paid inference API**.

### LLM fine-tuning

**Metric:** validation cross-entropy loss.
**Measured:** base **2.259** → LoRA **0.121** (`reports/sft_metrics.json`).

### Robot reaction latency

**Metrics:** perception→decision, decision→motion, motion→actuation, and total.
**Measured** (`reports/latency_sim.json`, 5 trials + warm-up):

| Stage | Mean | p95 |
|---|---|---|
| perception → decision | **6.9 ms** | 13.0 ms |
| decision → motion | **1.7 ms** | 3.9 ms |
| full reaction (cold) | ~737 ms | — (one-time policy load) |

**Interpretation:** orchestration is *not* the bottleneck; user-perceived latency
is dominated by LLM generation — which is precisely why the brain was moved to a GPU.

### Locomotion (mobile base)

**Metrics:** distance closed toward the student, stop accuracy at conversation
range, fail-safe on student loss.
**Measured:** drove **+1.826 m** toward a 3 m student, **stopped at 0.90 m**,
**halted** when the student left.

### Reproduce every claim

| Claim | Command |
|---|---|
| All four contributions | `python -m drona.evaluation.harness` |
| Bias detection | `python scripts/demo_bias_detection.py` |
| Sim boots + robot spawns | `bash scripts/smoke_test_sim.sh` |
| Arm tracks commanded pose | `bash scripts/test_gesture_motion.sh` |
| Engagement → greeting → motion | `bash scripts/test_interaction_loop.sh` |
| Ask → brain → spoken answer | `bash scripts/test_advising_loop.sh` |
| Robot drives to student | `bash scripts/test_locomotion.sh` |
| Reaction latency | `bash scripts/run_latency_benchmark.sh 5` |
| Pi edge perception | `bash scripts/test_edge_launch.sh` |
| Remote brain degrades safely | `pytest tests/test_remote_advisor.py` |
| Bilingual routing | `pytest tests/test_bilingual_advising.py` |

---

## 5. AI / ML concepts used

**Retrieval & grounding**
- **RAG** (Retrieval-Augmented Generation) — answers grounded in retrieved evidence
- **Hybrid retrieval** — BM25 (lexical) + dense (semantic), fused by
  **Reciprocal Rank Fusion (RRF)**
- **Bi-encoder embeddings** + **vector search** (ChromaDB, cosine)
- **Cross-encoder reranking** — top-20 → top-5 (re-orders only; never gates)
- **Domain-specific embeddings** — JobBERT for careers vs general BGE for curriculum
- **Cross-lingual RAG** — *translate-retrieve-generate*: a Nepali query is
  translated to English for retrieval over an English-embedded index, then the
  answer is generated in Nepali
- **Context-window budgeting** — retrieved context trimmed per language so
  prompt + answer fit the model window (Devanagari is ~1.7 chars/token vs ~3.1)
- **Coverage gating** — refuse rather than hallucinate when retrieval is thin

**Model adaptation & serving**
- **Supervised fine-tuning (SFT)** on an instruction corpus
- **LoRA / PEFT** (r=16, α=32, all-linear); **QLoRA** option
- **Quantisation** — GGUF Q4_K_M for CPU/edge serving
- **Structured generation** — strict JSON schema for parseable, typed output
- **Reasoning-model control** — `think=False` to suppress chain-of-thought when
  a structured answer is required
- **Language detection & model routing** — Devanagari-ratio detection → per-language backend
- **Graceful degradation** — every tier falls back rather than failing

**Interaction intelligence**
- **Rule-based cognitive-bias detection** (6 types) with mitigation instructions
  injected into the prompt — the core novelty
- **Goal-conditioned advising** — employment / postgrad / startup / research /
  freelance / undecided
- **Temporal smoothing** — EMA on detection confidence + debounced state
  transitions so the FSM sees stable states

**Imitation learning (robot motion)**
- **Behaviour Cloning (BC)** from demonstrations
- **ACT** — Action Chunking Transformer (predicts action sequences)
- **Diffusion Policy** — denoising-based action generation
- **Vision-Language-Action (SmolVLA)** with LoRA fine-tuning
- **ONNX export** for edge inference

---

## 6. Robotics concepts used

**Middleware & architecture**
- **ROS 2 Jazzy** — nodes, topics, services, **actions**, parameters, launch files
- **DDS discovery** across machines (`ROS_DOMAIN_ID`) — the distributed backbone
- **Message contracts** — custom `drona_msgs` (AdvisingQuery/Response, GestureCommand,
  EngagementDetection, SessionState…)
- **Separation of transport and logic** — ROS nodes are thin wrappers over pure
  Python, so Phase-1 unit tests still cover Phase-2 behaviour

**Modelling & simulation**
- **URDF / xacro** — parametric robot description (`use_gz_camera`,
  `use_gz_control`, `use_mobile_base`)
- **Gazebo Harmonic (gz sim)** — physics, sensors, SDF worlds
- **ros_gz bridge** — typed ROS↔GZ topic bridging (clock, camera, joint states, `/cmd_vel`)
- **Digital twin / sim-first development** — identical policy code drives sim and hardware
- **Isaac Sim** stage builder (OmniGraph ROS2 bridge) — ready for an RTX machine

**Control & kinematics**
- **Joint position control** (per-joint PID in Gazebo)
- **Minimum-jerk trajectories** (5th-order: 10s³−15s⁴+6s⁵) — zero velocity and
  acceleration at endpoints, human-like motion
- **Differential-drive kinematics** — two driven wheels + caster; `/cmd_vel`
  (`geometry_msgs/Twist`) + odometry
- **Proportional range control** — approach behaviour with a speed cap and a
  fail-safe stop
- **Trajectory quality metrics** — jerk, path length, apex error

**Perception & behaviour**
- **Face detection → engagement classification** (ABSENT → PASSING_BY →
  APPROACHING → ENGAGED → DISENGAGING)
- **Monocular distance proxy** from face bounding-box area
- **Finite state machine** for session lifecycle (IDLE → GREETING →
  NEEDS_ASSESSMENT → ADVISING → CLOSURE)
- **Sensor abstraction** — same node consumes a simulated camera topic, a USB
  webcam, or a Pi CSI camera

**Deployment**
- **Hardware-in-the-loop** — a real Pi + USB camera drives the simulated robot
- **Distributed edge computing** — perception (edge) / control (robot) / cognition (cloud GPU)
- **Hardware-agnostic interfaces** — `/cmd_vel`, `JointState`, and an arm-interface
  abstraction (`SimArmInterface` ↔ `SO100ArmInterface`) so the same code drives
  Gazebo, a Pepper/TIAGo-class base, or a real servo arm

---

## 7. Research contributions (thesis framing)

| ID | Contribution | Evidence |
|---|---|---|
| **C1** | Hybrid retrieval beats single-retriever baselines for curriculum-grounded advising | NDCG@5 0.941 vs 0.871/0.909 |
| **C2** | Rule-based cognitive-bias detection with prompt-level mitigation | **macro-F1 1.000** (P=R=1.000) over 6 types, 0 false positives |
| **C3** | Demonstration-learned gestures are smoother than scripted playback | 100 % success; 13 % lower command jerk |
| **C4** | Local-first, zero-cost, privacy-preserving deployment | Nepal citation ratio 1.00; all open-weight, no paid API |
| **C5** | *(systems)* Bilingual (English/Nepali) bias-aware advising, RAG-grounded in the local curriculum | Nepali pathways citing real Softwarica modules |
| **C6** | *(systems)* Hardware-agnostic distributed robot with measured latency and defined failure behaviour | 6.9 ms decision path; graceful-degradation matrix |

---

## 8. Honest scope boundaries

State these before an examiner finds them:

- **Wheeled, not bipedal.** Matches deployed social robots (Pepper, TIAGo, temi);
  bipedal locomotion is a separate research programme.
- **Range-only approach control.** A monocular camera gives distance, not bearing.
  Full navigation is Nav2's job — and Nav2 consumes the same `/cmd_vel`.
- **Simulated student is geometry**, so MediaPipe cannot detect a face from the
  simulated camera — which is exactly why the Pi hardware-in-the-loop path exists.
- **C3's honest claim is command jerk**, not achieved jerk (the environment filters both).
- **Nepali model knowledge comes from RAG**, not the model — which is why grounding matters.
- **Isaac Sim not run locally** (needs RTX + ~32 GB); assets are ready for such a machine.
- **The 4 GB dev laptop cannot host the full stack** (reranker + LLM together
  segfault); the GPU tier exists for this reason.
