# D.R.O.N.A. — Student Runbook

**Your step-by-step guide** for everything the codebase cannot do for you: data
collection, where to put files, what to run locally vs Colab/Kaggle, ROS2/simulation
on Ubuntu, and time estimates.

> **Status:** Phases 0–8 of the software build are **complete** (431 tests pass).
> What remains is **your data**, **your training runs**, **your demo recording**, and
> (later) **physical hardware + user study** (Phase 2 per the proposal).

---

## Quick answer: what is left for YOU?

| # | Task | Who | Where | Time (estimate) |
|---|---|---|---|---|
| 1 | Place 3 Softwarica curriculum PDFs/text | **You** | `data/raw/curriculum/` | 30 min |
| 2 | Manually collect ~150–200 Nepali job postings | **You** | `data/manual_collection/<source>/` | **6–9 hours** (spread over days) |
| 3 | Download ESCO CSV + NLFS PDF (links below) | **You** (one-time) | `data/raw/esco/`, `data/raw/` | 30–60 min |
| 4 | Run data pipeline scripts (O\*NET auto-downloads) | **You** | Windows or Ubuntu | 1–3 hours first run |
| 5 | Install Ollama + pull Phi-3.5 + Qwen | **You** | Local (Win/Ubuntu) | 20–40 min download |
| 6 | Run advising API + Next.js frontend | **You** | Local | 5 min to start |
| 7 | Generate synthetic Q&A + LoRA train | **You** | Local gen → **Colab T4** train | Colab **2–4 h** |
| 8 | Collect gesture demos + ACT/Diffusion train | **You** | Local collect → **Colab T4** | Colab **3–6 h** each |
| 9 | ROS2 + Gazebo simulation demo | **You** | **WSL2 on Windows** (`docs/wsl_setup.md`) | 2–4 h first setup |
| 10 | Record demo video + viva prep | **You** | See `docs/demo_video_script.md` | 2–3 h |
| 11 | (Phase 2) SO-100 arm + student user study | **You** | Hardware + ethics board | Weeks/months |

Everything else (code, tests, docs, harness, notebooks, ROS2 packages, frontend) is
**already built**.

---

## Where to run what (environment matrix)

| Work | Windows (dev) | WSL2 (Ubuntu 22.04) | Colab Free T4 | Kaggle GPU |
|---|---|---|---|---|
| `pip install`, `pytest` | ✅ primary | ✅ | ○ | ○ |
| Data download + ingest | ✅ | ✅ | ○ | ○ |
| Ollama + advising API | ✅ (CPU/GPU partial) | ✅ | ❌ | ❌ |
| Next.js frontend | ✅ | ✅ | ❌ | ❌ |
| Streamlit dashboard (legacy) | ✅ | ✅ | ❌ | ❌ |
| Notebooks 01–06, 10–11 (analysis) | ✅ | ✅ | optional | optional |
| Notebook 09 LoRA fine-tune | ❌ (VRAM) | ❌ (4 GB VRAM) | ✅ **recommended** | ✅ alt |
| Notebooks 07–08 ACT/Diffusion | ❌ (VRAM) | ❌ | ✅ **recommended** | ✅ alt |
| `colcon build`, ROS2 nodes | ❌ (no ROS2 on Win) | ✅ **required** | ❌ | ❌ |
| Gazebo Harmonic sim | ❌ | ✅ **required** (WSLg GUI) | ❌ | ❌ |
| Isaac Sim | ❌ | ○ if ≥8 GB VRAM | ○ cloud GPU | ○ |

**Your machine:** Windows 11 + GTX 1650 4 GB, 16 GB RAM. **No Ubuntu dual-boot —
ROS2 runs in WSL2** (real Ubuntu 22.04 inside Windows; WSLg shows the Gazebo/RViz
windows). Local = **inference** only; all **training** on Colab T4 (or Kaggle);
Isaac Sim = cloud only. Full WSL setup: **`docs/wsl_setup.md`**.

---

## Directory map — where every file goes

```
D.R.O.N.A/
├── data/
│   ├── raw/                          # YOU download / place source files here
│   │   ├── curriculum/               # ← YOUR 3 Softwarica module PDFs (.pdf or .txt)
│   │   ├── esco/                     # ← unzipped ESCO v1.2.1 CSV distribution
│   │   └── nlfs_2017_18.pdf          # ← NLFS PDF (you download once)
│   ├── manual_collection/            # ← YOUR hand-collected job postings
│   │   ├── merojob/*.json            # manual only (ToS forbids scraping)
│   │   ├── jobsnepal/*.json          # optional manual backup
│   │   ├── internsathi/*.json
│   │   ├── kumarijobs/*.json
│   │   └── linkedin/*.json           # published-report style entries only
│   ├── processed/                    # scripts WRITE here (parquet/json)
│   ├── chromadb/                     # ingest creates vector index (auto)
│   ├── checkpoints/                  # YOU copy Colab-trained weights here
│   │   ├── act-gesture-policy/
│   │   ├── diffusion-gesture-policy/
│   │   └── phi35-lora-advising/
│   └── evaluation/                   # eval reports saved here (auto)
├── .env                              # copy from .env.example, add API keys
├── frontend/                         # Next.js dashboard
├── ros2_ws/                          # ROS2 — build/run inside WSL2 (see docs/wsl_setup.md)
└── notebooks/                        # 01–11 canonical analysis + Colab training
```

**Do not commit:** `.env`, `data/raw/*.zip`, `data/chromadb/`, large checkpoints,
downloaded model weights.

---

## Part A — One-time environment setup

### A1. Python (Windows or Ubuntu)

```powershell
# From repo root
python -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # Ubuntu

pip install -e ".[dev,backend,eval]"
python scripts/verify_env.py      # must pass required packages
pytest -q                         # expect ~431 passed, 1 skipped
```

| Step | Time |
|---|---|
| venv + pip install | 10–20 min |
| First pytest run | ~30 s |
| verify_env | ~5 s |

### A2. Environment file

```powershell
copy .env.example .env
# Edit .env: paths are fine by default; add PINECONE/GEMINI keys only if you use them offline
```

### A3. Docker (optional Postgres; Ollama usually native)

```powershell
docker compose up -d db            # Postgres + pgvector only
# Default vector backend is ChromaDB — you do NOT need Postgres for the thesis demo
```

### A4. Ollama (local LLM — required for live advising)

```powershell
# Install from https://ollama.com — then:
ollama pull phi3.5:3.8b-mini-instruct-q4_K_M
ollama pull qwen2.5:3b-instruct-q4_K_M
ollama serve                       # keep running in a terminal
```

| Step | Time |
|---|---|
| Ollama install | 5 min |
| Model downloads | 15–30 min (depends on connection) |

### A5. Next.js frontend (one-time)

```powershell
cd frontend
npm install
cd ..
```

| Step | Time |
|---|---|
| npm install | 2–5 min |

### A6. ROS2 via WSL2 (do once — you no longer need a dual-boot)

You have Windows + WSL, not a dual-boot. ROS2 runs in **WSL2 (Ubuntu 22.04)** and
WSLg displays the Gazebo/RViz windows. **Full guide: `docs/wsl_setup.md`.** Short
version:

```powershell
# Windows PowerShell (admin) — one time:
wsl --install -d Ubuntu-22.04
wsl --update
```

```bash
# Then INSIDE the Ubuntu (WSL) shell:
sudo apt update && sudo apt install -y ros-humble-desktop ros-humble-ros-gz \
  gz-harmonic python3-colcon-common-extensions ros-humble-xacro ros-humble-rviz2
echo 'source /opt/ros/humble/setup.bash' >> ~/.bashrc && source ~/.bashrc
cd /mnt/c/Users/trish/Documents/Developer/D.R.O.N.A/ros2_ws   # repo via /mnt/c
colcon build --symlink-install && source install/setup.bash
```

| Step | Time |
|---|---|
| `wsl --install` + Ubuntu first boot | 10–20 min |
| ROS2 Humble + Gazebo install | 30–60 min |
| colcon build | 2–5 min |

---

## Part B — Data collection (YOUR work)

### B1. Curriculum (required for Nepal-grounded advising)

**What:** 3 Softwarica BSc Computing module descriptors (PDF or plain text).

**Where:** `data/raw/curriculum/`

```
data/raw/curriculum/
  software_engineering_module.pdf
  database_systems_module.pdf
  machine_learning_module.pdf
```

**How:** Get PDFs from your college LMS / module leader. No PII in these files.

**Time:** ~30 min to gather files.

---

### B2. Nepali job postings (required — your main dataset contribution)

**What:** ~150–200 junior/graduate tech job postings from Nepal.

**Where:** JSON files under source subfolders (see `data/manual_collection/README.md`).

| Source | Target count | Folder | Collection |
|---|---|---|---|
| MeroJob | 50 | `data/manual_collection/merojob/` | **Manual only** (ToS §3.E) |
| JobsNepal | 40 | `data/manual_collection/jobsnepal/` | Manual **or** `scrape_jobs.py` |
| Internsathi | 30 | `data/manual_collection/internsathi/` | Manual **or** `scrape_jobs.py` |
| Kumari Jobs | 30 | `data/manual_collection/kumarijobs/` | Manual **or** `scrape_jobs.py` |
| LinkedIn | ~30 | `data/manual_collection/linkedin/` | **Manual only** (never scrape) |

**Template:** copy fields from `data/manual_collection/_template.json`.

**Rules:**
- Paraphrase descriptions (2–4 sentences); do not paste full postings.
- Always include `source_url` and `is_synthetic: false`.
- No applicant PII (phone numbers, personal emails).
- Salary: use `null` if not stated — never guess.

**Time:** ~2–3 min/posting × 180 ≈ **6–9 hours** over 3–4 days.

---

### B3. Automated downloads (you run scripts; no manual browsing)

| Dataset | You download? | Script | Output |
|---|---|---|---|
| O\*NET 30.3 | No (script fetches) | `scripts/download_onet.py` | `data/processed/onet_career_pathways.parquet` |
| ESCO v1.2.1 | **Yes** — CSV zip from esco.ec.europa.eu | `scripts/ingest_sources.py esco --csv-dir data/raw/esco` | `data/processed/esco_career_pathways.json` |
| BLS OEWS May 2025 | **Yes** — national .xlsx from bls.gov/oes | `scripts/ingest_sources.py bls --oews <file>` | `data/processed/bls_oews_wages.json` |
| NLFS 2017/18 | **Yes** — PDF from NSO Nepal open data | `scripts/ingest_sources.py nlfs --pdf data/raw/nlfs_2017_18.pdf` | `data/processed/nlfs_indicators.json` |

**ESCO download:** https://esco.ec.europa.eu/en/use-esco/download → CSV package → unzip to `data/raw/esco/`.

**NLFS PDF:** https://data.nsonepal.gov.np/ (search "Labour Force Survey 2017/18").

**Time:** ~30–60 min total for manual downloads; scripts run in minutes.

---

## Part C — Data pipeline (run in THIS order)

Run from repo root with venv activated.

### Step C1 — O\*NET (automated)

```powershell
python scripts/download_onet.py
```

| | |
|---|---|
| **Time** | 5–15 min (download + parse) |
| **Needs network** | Yes |
| **Output** | `data/processed/onet_career_pathways.parquet` |

### Step C2 — ESCO, BLS, NLFS (after you place raw files)

```powershell
python scripts/ingest_sources.py esco --csv-dir data/raw/esco
python scripts/ingest_sources.py bls --oews data/raw/oews_M2025.xlsx --onet-parquet data/processed/onet_career_pathways.parquet
python scripts/ingest_sources.py nlfs --pdf data/raw/nlfs_2017_18.pdf
```

| | |
|---|---|
| **Time** | 2–10 min each |
| **Skip if** | raw file not yet downloaded (pipeline still runs without them) |

### Step C3 — Job postings (after manual collection OR scrape)

```powershell
# Option A: load manual JSON + limited automated scrape
python scripts/scrape_jobs.py --source all

# Option B: manual only (safest for MeroJob)
python scripts/scrape_jobs.py --source manual
```

| | |
|---|---|
| **Time** | seconds (manual) to 30+ min (full scrape with limits) |
| **Output** | `data/processed/*_postings.json` |

### Step C4 — Build vector index (ChromaDB)

```powershell
python scripts/ingest_data.py
# Verify:
python scripts/ingest_data.py --stats-only
```

| | |
|---|---|
| **Time** | **20–60 min first run** (downloads embedding models ~1–2 GB) |
| **Subsequent** | 5–15 min |
| **Output** | `data/chromadb/` populated |
| **Prerequisite** | Steps C1–C3 + curriculum PDFs for best results |

### Step C5 — Explore data (notebook)

```powershell
jupyter notebook notebooks/01_data_eda.ipynb
```

| | |
|---|---|
| **Time** | 10–20 min |
| **Where** | Local |

---

## Part D — Run the advising system (demo path)

### D1 — Start backend

```powershell
# Terminal 1 — Ollama (if not already running)
ollama serve

# Terminal 2 — API
python scripts/run_api.py
# Open http://127.0.0.1:8000/docs
```

### D2 — Start frontend

```powershell
# Terminal 3
cd frontend
npm run dev
# Open http://localhost:3000
```

### D3 — Quick CLI test (no browser)

```powershell
python scripts/advise.py "What software jobs exist in Kathmandu for new graduates?"
```

| | |
|---|---|
| **Time to first advice** | ~30–90 s per query (CPU Ollama) |
| **Prerequisite** | Ollama running + ChromaDB ingested |

**Legacy UI:** `streamlit run drona/dashboard/app.py` (older dashboard; Next.js is the thesis UI).

---

## Part E — Training (Colab / Kaggle only)

### E1 — Synthetic Q&A + LoRA (Phase 3)

**Local first** (generates training files):

```powershell
python scripts/generate_qa.py --pathways data/processed/onet_career_pathways.parquet --n 500
```

| | |
|---|---|
| **Time** | 10–30 min (uses local Ollama or falls back to template) |
| **Output** | `data/processed/sft_train.jsonl`, gold review file |

**Then Colab** — open `notebooks/09_lora_finetune_phi35.ipynb`:

1. Upload repo or clone from GitHub.
2. Runtime → T4 GPU.
3. Run all cells.
4. Download adapter to `data/checkpoints/phi35-lora-advising/` (or `models/phi35-lora-advising/`).

| | |
|---|---|
| **Colab time** | **2–4 hours** (500 examples, 3 epochs) |
| **Kaggle alt** | Similar; watch session limits |

---

### E2 — Gesture demonstrations (local)

```powershell
python scripts/collect_demonstrations.py --output data/cards/gesture_demonstrations.json
# Or use the keyframe generator built into notebook 07
```

| | |
|---|---|
| **Time** | 30–60 min |
| **Where** | Local (StubEnv / no GPU) |

### E3 — ACT policy (Colab)

Open `notebooks/07_lerobot_act_training.ipynb` on **Colab T4**.

1. Run data-prep cells (uses bundled/generated demos).
2. Train ACT.
3. Download checkpoint → `data/checkpoints/act-gesture-policy/`.

| | |
|---|---|
| **Colab time** | **3–5 hours** |

### E4 — Diffusion policy ablation (Colab)

Open `notebooks/08_lerobot_diffusion_policy.ipynb` — same flow as E3.

| | |
|---|---|
| **Colab time** | **3–6 hours** |

### E5 — Verify policies locally (after copying checkpoints)

```powershell
python scripts/run_simulation.py
jupyter notebook notebooks/11_sim_to_real_handoff.ipynb
```

---

## Part F — Evaluation (thesis numbers)

### F1 — Quick eval (no Ollama/ChromaDB)

```powershell
python scripts/run_evaluation.py --c2 --c3
```

### F2 — Full eval (needs ChromaDB + optionally Ollama)

```powershell
python scripts/run_evaluation.py --all --llm
```

| | |
|---|---|
| **Time** | 1–5 min (no LLM) to 15–30 min (with LLM) |
| **Output** | `data/evaluation/report_<timestamp>.json` |

### F3 — Notebooks (run in order for thesis chapter)

| # | Notebook | Needs | Time |
|---|---|---|---|
| 01 | `01_data_eda.ipynb` | ChromaDB | 15 min |
| 02 | `02_curriculum_parsing.ipynb` | curriculum PDFs | 10 min |
| 03 | `03_embedding_quality.ipynb` | sentence-transformers download | 20–40 min |
| 04 | `04_retrieval_ablations.ipynb` | ChromaDB | 15 min |
| 05 | `05_bias_detection_eval.ipynb` | nothing | 5 min |
| 06 | `06_llm_response_quality.ipynb` | Ollama | 30–60 min |
| 07 | `07_lerobot_act_training.ipynb` | **Colab T4** | 3–5 h |
| 08 | `08_lerobot_diffusion_policy.ipynb` | **Colab T4** | 3–6 h |
| 09 | `09_lora_finetune_phi35.ipynb` | **Colab T4** | 2–4 h |
| 10 | `10_end_to_end_eval.ipynb` | ChromaDB + optional Ollama | 20 min |
| 11 | `11_sim_to_real_handoff.ipynb` | local; ROS section on Ubuntu | 15 min |

---

## Part G — ROS2 + simulation (WSL2 on Windows)

**When:** After Python advising works and (optionally) after Colab policy training.

**Where:** Inside the **WSL2 Ubuntu 22.04 shell** — not the Windows PowerShell, and
no dual-boot needed. One-time WSL/ROS2 install is in Part A6 and **`docs/wsl_setup.md`**.
WSLg shows the Gazebo/RViz windows on your Windows desktop automatically.

### G1 — Build workspace (in the Ubuntu/WSL shell)

```bash
# repo on the Windows drive is reachable from WSL at /mnt/c:
cd /mnt/c/Users/trish/Documents/Developer/D.R.O.N.A/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

> If `colcon build` is slow on `/mnt/c`, clone a copy into the native WSL home
> (`~/drona`) and build there — see `docs/wsl_setup.md` §3.

### G2 — Gazebo Harmonic (recommended on GTX 1650)

```bash
ros2 launch drona_bringup drona_gazebo.launch.py
```

Setup details: `docs/sim_setup_gazebo.md`

| | |
|---|---|
| **First-time setup** | 1–2 hours (install Gazebo Harmonic + bridges) |
| **Each launch** | 1–2 min |

### G3 — Full system + RViz + record demo bag

```bash
ros2 launch drona_bringup drona_system.launch.py use_rviz:=true record:=true bag_path:=demo_run
```

### G4 — Send a gesture (second terminal)

```bash
ros2 action send_goal /drona/execute_gesture_action \
  drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback
```

### G5 — Isaac Sim (optional — needs ≥8 GB VRAM or cloud)

See `docs/sim_setup_isaac.md` and `ros2_ws/src/drona_bringup/isaac/drona_isaac_stage.py`.

**Interface reference:** `docs/ros2_topics_actions.md`

---

## Part H — Recommended master timeline

| Week | Focus | Hours |
|---|---|---|
| **1** | Env setup (A) + curriculum PDFs + start job collection (B1–B2) | 8–12 |
| **2** | Finish job collection + run pipeline (C) + first advising demo (D) | 10–15 |
| **3** | Colab: LoRA (E1) + ACT (E3) | 6–10 (mostly Colab waiting) |
| **4** | Colab: Diffusion (E4) + evaluation notebooks (F) | 8–12 |
| **5** | WSL2: ROS2 + Gazebo demo (G) + record video | 8–12 |
| **6** | Viva prep (`docs/viva_prep.md`) + thesis writing | — |

**Minimum viable demo (if short on time):**
1. Skip ESCO/BLS/NLFS (O\*NET + 50 manual MeroJob postings still works).
2. Skip LoRA/ACT training — use keyframe gestures (already work).
3. Run advising on Windows without ROS2; show Next.js + evaluation JSON.
   (ROS2/Gazebo in WSL2 is a bonus demo, not required for the core advising story.)

---

## Part I — Troubleshooting

| Problem | Fix |
|---|---|
| `ChromaDB appears empty` | Run `python scripts/ingest_data.py` after `download_onet.py` + `scrape_jobs.py` |
| Ollama connection refused | Start `ollama serve`; check `OLLAMA_HOST` in `.env` |
| Frontend can't reach API | Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` in `frontend/.env.local` |
| Embedding download slow/fails | Retry; need ~2 GB disk; use stable connection |
| `colcon build` fails | Must be inside WSL2 Ubuntu 22.04 with ROS2 Humble sourced (`source /opt/ros/humble/setup.bash`) |
| WSL: no GUI window / Gazebo black screen | `wsl --update` + `wsl --shutdown`; or `export LIBGL_ALWAYS_SOFTWARE=1`. See `wsl_setup.md` §7 |
| Gazebo blank / no model | Check `drona_description` package installed; see `sim_setup_gazebo.md` |
| Colab disconnects | Save checkpoints to Drive; reduce batch size in notebook |
| Nepal citation ratio low | Add more manual Nepal postings; re-run ingest |

---

## Part J — Checklist before viva

- [ ] `pytest -q` → 431 passed
- [ ] `data/raw/curriculum/` has your 3 module PDFs
- [ ] `data/manual_collection/` has ≥100 real postings (target 180)
- [ ] `python scripts/ingest_data.py --stats-only` shows non-zero docs
- [ ] Live demo: API + Next.js answers a biased query with flags + citations
- [ ] `data/evaluation/report_*.json` exists with C1–C4 numbers
- [ ] At least one Colab training artifact OR documented keyframe-only C3 baseline
- [ ] WSL2: one Gazebo or RViz gesture recording (video/bag) — see `docs/wsl_setup.md`
- [ ] Demo video recorded per `docs/demo_video_script.md`
- [ ] Read `docs/viva_prep.md`

---

## Related docs

| Doc | Purpose |
|---|---|
| [`data/manual_collection/README.md`](../data/manual_collection/README.md) | Job JSON template + field rules |
| [`data_ethics.md`](./data_ethics.md) | PII, licensing, scraping policy |
| [`demo_video_script.md`](./demo_video_script.md) | Recording storyboard |
| [`viva_prep.md`](./viva_prep.md) | Examiner Q&A |
| [`wsl_setup.md`](./wsl_setup.md) | **ROS2 + Gazebo on Windows via WSL2 (start here for sim)** |
| [`sim_setup_gazebo.md`](./sim_setup_gazebo.md) | Gazebo launch details (runs in WSL2) |
| [`ros2_setup.md`](./ros2_setup.md) | ROS2 Humble install + topic/node reference |
| [`PROGRESS.md`](../PROGRESS.md) | What the build already shipped |
