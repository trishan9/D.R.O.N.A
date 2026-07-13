# FINAL_STEPS.md — Complete Deployment & Execution Guide

This is the **single sequential guide** from a blank computer to the fully
operational D.R.O.N.A. system running in ROS 2 simulation (Gazebo / Isaac Sim),
with the web platform and trained models live. After finishing it, the **only
remaining task** is plugging in the physical robot (Part 8).

Follow the parts **in order**. Every part ends with a ✅ **Verify** step - do
not continue until it passes. Estimated total hands-on time: ~3-4 hours plus
~1 hour of Colab GPU time.

| Part | What you set up | Where it runs |
|---|---|---|
| 0 | Accounts + what data comes from where | - |
| 1 | Python dev environment + the repo | Windows |
| 2 | Datasets (automatic + manual + your own) | Windows |
| 3 | Model training (5 notebooks) | Google Colab (A100) |
| 4 | LLM serving, RAG index, API, web platform | Windows |
| 5 | WSL2 + ROS 2 Humble + Gazebo simulation | WSL2 (Ubuntu) |
| 6 | NVIDIA Isaac Sim (optional, RTX GPU) | Windows/Linux |
| 7 | Full-system validation checklist | everywhere |
| 8 | Physical robot deployment | robot |

---

## Part 0 · Accounts and data sources at a glance

**Accounts you need:**

| Account | Needed for | Cost |
|---|---|---|
| GitHub | hosting the repo so Colab can clone it | free |
| Google | Colab notebooks; **Colab Pro recommended for the A100** (T4 free tier also works - notebooks auto-fall back) | free / ~$10 for Pro |
| Hugging Face | *not required* - all models used (bge-small, JobBERT-v2, Qwen3-4B, bge-reranker-v2-m3) are public and download anonymously | - |
| Kaggle | *optional* - only as a Colab alternative (notebooks support it) | free |

**Every dataset, and how you get it:**

| Dataset | How obtained | Where it lands | License |
|---|---|---|---|
| **O*NET 30.3** (US DOL occupations) | **automatic** - `scripts/prepare_training_data.py` downloads + parses it | `data/processed/onet_career_pathways.parquet` | CC BY 4.0 |
| **NLFS 2017/18** (Nepal labour survey) | **automatic (attempted)** - notebook 01 tries the official NSO PDF; skips gracefully offline | `data/processed/` snippets + data card | Open govt data |
| **Synthetic SFT Q&A** (500 pairs) | **generated** - grounded in the real pathways above, bias-balanced | `data/finetune/sft_train.jsonl` / `sft_val.jsonl` | labelled `SYNTHETIC` |
| **Gesture demonstrations** | **generated** - keyframe + jitter, 25 episodes × 6 gestures | `data/demonstrations/demonstrations.jsonl` | - |
| **ESCO v1.2.1** (EU skills taxonomy) | **manual download (optional)** - <https://esco.ec.europa.eu/en/use-esco/download>, pick *CSV, English*, unzip | `data/raw/esco/` (`occupations_en.csv` etc.) | CC BY 4.0 |
| **BLS OEWS May 2025** (US wages) | **automatic** - notebook 01 downloads the national table (browser headers; manual fallback link inside) | `data/raw/bls/` -> USD bands on 38/39 pathways | Public domain |
| **Softwarica curriculum** | **YOU must provide** - see Part 2.3 | `data/raw/curriculum/` | institutional |
| **Nepali job postings** | **YOU must collect** - see Part 2.4 | `data/manual_collection/<portal>/` | manual, ToS-checked |

> The repo ships with **clearly marked placeholders** for the last two, so the
> entire system runs end-to-end *today*. Swap in real files before training the
> final thesis models.

---

## Part 1 · Development environment (Windows)

### 1.1 Install the basics

1. **Python 3.10-3.12** (3.11 recommended; the project also runs on 3.14):
   <https://www.python.org/downloads/> - tick **"Add python.exe to PATH"**.
2. **Git**: <https://git-scm.com/download/win> (defaults are fine).
3. **Node.js 20 LTS** (for the web platform): <https://nodejs.org/>.
4. **Ollama** (local LLM server): <https://ollama.com/download> (Windows installer).

### 1.2 Get the repo and install

```bash
git clone https://github.com/<your-username>/D.R.O.N.A.git
cd D.R.O.N.A

# optional but recommended - a virtual environment:
python -m venv .venv
.venv\Scripts\activate          # PowerShell: .venv\Scripts\Activate.ps1

# core + dev + evaluation/notebooks + API backend + Streamlit dashboard:
pip install -e ".[dev,eval,backend,dashboard]"

# model export + robot-side inference support:
pip install -e ".[export]"
```

> **Windows console note:** prefix long-running scripts with `PYTHONUTF8=1`
> (Git Bash) or `$env:PYTHONUTF8=1` (PowerShell) - some scripts print
> box-drawing characters that crash cp1252 consoles.

### 1.3 Configure

```bash
cp .env.example .env    # defaults are correct; edit only if you change models
```

✅ **Verify**

```bash
python scripts/verify_env.py     # environment self-check
pytest -q                        # expect: 440 passed, 1 skipped (no network/GPU needed)
```

---

## Part 2 · Datasets

### 2.1 Automatic pipeline (always do this first)

```bash
PYTHONUTF8=1 python scripts/prepare_training_data.py
```

This downloads + parses O*NET, writes placeholder curriculum/jobs if none
exist, exports the JSON anchors, builds the SFT dataset and the gesture
demonstrations. Idempotent - safe to re-run (add `--skip-onet` once cached).

✅ **Verify**: it ends with `All training inputs ready` and these files exist:
`data/processed/onet_career_pathways.parquet`, `data/finetune/sft_train.jsonl`,
`data/demonstrations/demonstrations.jsonl`.

### 2.2 Optional enrichments (better salary + Nepal evidence)

- **ESCO**: download the English CSV bulk (link in Part 0), unzip into
  `data/raw/esco/`. Adds finer-grained ICT occupations.
- **BLS OEWS**: now **automatic** - notebook 01 downloads the May 2025
  national table and `prepare_training_data.py` applies it whenever the file
  is present (38/39 pathways gain USD wage bands). Manual fallback: drop the
  table from <https://www.bls.gov/oes/tables.htm> into `data/raw/bls/`.
- **ESCO** is picked up automatically by notebook 01 once the CSVs are in
  place; nothing else to configure.

### 2.3 Your real curriculum (replace the placeholder)

**What:** one file per Softwarica BSc Computing module descriptor.
**Format:** `.pdf`, `.docx`, `.md`, or `.txt` - the parser handles all four.
**Where:** `data/raw/curriculum/` (delete the placeholder `.md` files).
**How much:** every module of the programme (~25-40 files).
**Naming:** anything readable, e.g. `ST4056CEM_programming.pdf`.
**Why:** the curriculum collection is the retrieval ground truth for C1 -
placeholder text produces placeholder advice.

**Already done for you (public version):** `data/raw/curriculum/` now contains
the **23 real BSc (Hons) Computing modules** extracted from Softwarica's
official course page (all years/semesters, credits, descriptions, tools,
specialisation tracks). Because `data/raw/` is gitignored, commit them with
`git add -f data/raw/curriculum` so Colab trains on them. To enrich further
with the fuller LMS descriptors:

**All three programmes ship with real public module data** (74 modules):
Software Engineering (formerly Computing), Ethical Hacking & Cybersecurity,
and CS with Artificial Intelligence - extracted from the official course
pages. Each module file carries a `Programme:` line; the AI tailors advice to
the programme selected in the web profile.

### Authenticated learning-platform (LMS) content

The college's detailed materials live behind a login, so the integration is an
**offline authenticated sync**, not a live connection: you fetch the content
once *with your own session*, it lands in the knowledge base, and the AI cites
it like any other curriculum source. Credentials never enter the request path
and nothing is fetched at question-time - access control stays with the LMS.

**For the c4mpus platform** (`c4mpus.com` - your real weekly learning content),
use `scripts/fetch_lms.py`. It logs in, lists your enrolled modules, and
downloads each module's weekly lessons **and their full lesson bodies**:

```bash
# One command - logs in, syncs every enrolled module:
python scripts/fetch_lms.py --login -u <your-student-id> -p <your-password>
#   (omit -p to be prompted without the password showing on screen)

# Then rebuild + re-index so the AI can cite the new material:
python scripts/prepare_training_data.py --skip-onet
python scripts/ingest_data.py
```

Each module becomes `data/raw/curriculum/lms_<slug>.md` (every week's lessons
with the actual lecture text **plus the text of linked PDF worksheets/decks**,
HTML stripped, tagged with `Programme:`), and the raw JSON is cached in
`data/raw/lms_raw/` so you can re-parse offline without re-fetching.

**PDF attachments:** much of the real teaching material is uploaded as PDF lab
worksheets and lecture slides. `fetch_lms.py` downloads those PDFs and folds
their extracted text into the module (on by default; `--no-files` to skip for a
quicker text-only sync). Image-only slides (`.png/.jpg` exports) are **not**
captured - that would need OCR, which is out of scope. Options: `--modules
mine.txt` (subset), `--token`/`--curl-file` (existing session), `--max-lessons N`,
`--no-files`. A **401** means the session expired - just re-run `--login`.

**Official programme data (fees, careers, entry requirements, structure)** -
no login needed. `scripts/fetch_softwarica_courses.py` pulls the data behind the
softwarica.edu.np course-page tabs from the public course API
(`ftp.softwarica.edu.np/api`) and writes a programme guide per course:

```bash
python scripts/fetch_softwarica_courses.py       # all 3 BSc + the MSc
python scripts/prepare_training_data.py --skip-onet
python scripts/ingest_data.py
```

Each guide (`_guide_<slug>.md`, tagged by programme) carries the real **fee
structure** (per-year breakdown + grand total), **career opportunities**,
**admission eligibility + IELTS requirement**, degree highlights, and the
official module list with credits - so the advisor can answer "how much does
Ethical Hacking cost?" or "what jobs does CS-AI lead to?".

**For any other login-protected page** (Moodle-style LMS, module PDFs), use the
generic fetcher with your browser cookie:

```bash
# F12 > Network > any request > Request Headers > copy the "cookie" value
python scripts/fetch_curriculum.py --urls-file lms_pages.txt --cookie "MoodleSession=..."
python scripts/prepare_training_data.py --skip-onet && python scripts/ingest_data.py
```

Re-run the sync whenever materials change. Only sync content your account is
entitled to see, and keep the synced files out of any public repo if the
material is not publicly licensed (`data/raw/` is gitignored by default -
share it only into your **private** training repo).

**No copy-paste needed** - `scripts/fetch_curriculum.py` downloads the module
pages for you, including login-protected campus platforms:

```bash
# 1. put one module-page URL per line in a file:
notepad my_modules.txt
# 2. logged-in campus pages: copy the Cookie header once from your browser
#    (F12 > Network > click any request > Request Headers > cookie)
python scripts/fetch_curriculum.py --urls-file my_modules.txt --cookie "MoodleSession=..."
```

It converts each page to clean Markdown in `data/raw/curriculum/` (PDF links
are saved as-is). Alternative with zero tooling: while logged in, print each
module page to PDF (Ctrl+P) straight into the folder.

After replacing: re-run `prepare_training_data.py` (2.1) — it re-parses and
re-exports everything.

### 2.4 Your real Nepali job postings (replace the placeholder)

**Now automated:** `scripts/scrape_nepali_jobs.py` collects real current tech
postings from **MeroJob** (public API - skills + salary) and **KumariJob**
(schema.org data), maps them to the JobPosting schema (Nepal tier), and
replaces the placeholders:

```bash
python scripts/scrape_nepali_jobs.py            # ~90-100 real tech jobs today
python scripts/prepare_training_data.py --skip-onet
python scripts/ingest_data.py
```

Re-run any day to refresh/accumulate (Nepal's tech market is small on a given
day, so more postings appear over time). **LinkedIn is deliberately excluded**
(ToS prohibition + project ethics policy). Company career pages (Leapfrog,
CedarGate, ...) mostly lack public ATS APIs and those firms post on MeroJob
anyway. To add postings manually instead:


**What:** postings from Nepali job portals, collected **manually** (copy-paste
into JSON) - deliberate choice: automated scraping of these portals is
ToS-restricted, and manual collection with provenance is defensible at viva.

- **Sources:** MeroJob, JobsNepal, Kumari Job, InternSathi (check each site's
  robots.txt/ToS first - guidance in `docs/data_ethics.md`). **Never LinkedIn**
  (ToS prohibits it).
- **Fields per posting:** title, employer, location, skills_required,
  salary range (NPR, if listed), experience, description, URL, dates - the
  exact schema with an example is `data/manual_collection/_template.json`.
- **Where:** `data/manual_collection/<portal>/<anything>.json` (one file can
  hold many postings).
- **How much:** 50-200 postings across the portals is plenty; aim for breadth
  of roles (dev, data, QA, sysadmin, security) rather than volume.
- **Ethics:** collect only public posting text, no personal data, keep the
  source URL for provenance. Full policy: `docs/data_ethics.md`.

After adding: re-run `prepare_training_data.py`, then re-index (Part 4.2).

### 2.5 International postings from a popular public dataset (already imported)

`scripts/import_public_postings.py` pulls postings from the widely used
Hugging Face dataset **`lukebarousse/data_jobs`** (~785k tech postings; the
repo ships with 200 already imported at
`data/manual_collection/data_jobs/international_postings.json`). They are
tier-labelled **international**, so Nepal-tier evidence still ranks first
(C4); USD salaries stay in the description text and are never converted to
NPR; LinkedIn-sourced rows are excluded (ethics policy). Re-run with
`--limit`/`--keyword` to change the mix, or `--csv` for any Kaggle CSV.

✅ **Verify**: `PYTHONUTF8=1 python scripts/ingest_data.py --stats-only` shows
document counts that reflect your real data.

---

## Part 3 · Model training on Google Colab (A100)

The five staged notebooks in [`notebooks/`](notebooks/README.md) are the
canonical ML pipeline. Run them **in order, top to bottom**; every notebook
clones the repo itself and regenerates missing inputs.

### 3.1 One-time: put the repo on GitHub

```bash
git add -A && git commit -m "my data"     # include your real curriculum: git add -f data/raw/curriculum
git remote add origin https://github.com/<you>/D.R.O.N.A.git
git push -u origin main
```

(Private repo? In each notebook's cell 1 use
`https://<fine-grained-read-token>@github.com/<you>/D.R.O.N.A.git`.)

### 3.2 Run the notebooks - where, in what order, and how long

Open each in Colab (`File ▸ Open notebook ▸ GitHub`), edit `REPO_URL` in
**cell 1**, then `Runtime ▸ Run all`. Run them **in order** the first time.

| # | Notebook | Colab runtime to select | Time (A100) | Time (T4 free) |
|---|---|---|---|---|
| 01 | data cleaning | **CPU** is enough (any runtime works) | ~10 min | ~10 min |
| 02 | EDA | **CPU** | ~5 min | ~5 min |
| 03 | features/embeddings | CPU works; **T4/A100** makes encoding faster | ~5 min | ~8 min |
| 04 | model training | **GPU required** - A100 best, T4 works | ~45-70 min | **~2.5-3.5 h** |
| 05 | evaluation | **CPU** | ~10 min | ~10 min |

Tip: run 01-03 in one CPU session (no GPU quota used), then switch to a GPU
runtime for 04, then back to CPU for 05.

**Will notebook 04 crash when the Colab runtime expires?** Sessions do
disconnect (idle timeouts, free-tier preemption) - and notebook 04 is built
for exactly that:

- Its **persistence cell** mounts Google Drive (one auth prompt) and copies
  every finished model to `MyDrive/drona_training/` **the moment it is
  trained** - the LoRA adapter, BC+ONNX, ACT and Diffusion each persist
  independently, and the final zip is also copied to Drive.
- On a fresh session it **restores from Drive and skips completed parts** -
  after a disconnect: reconnect → `Runtime ▸ Run all` → only the unfinished
  model retrains. Nothing already trained is ever lost or repeated.
- On the free T4, set `TRAIN_DIFFUSION = False` for the first pass (saves
  ~60-90 min) and add the ablation model in a second session later - the
  resume logic makes that a no-cost decision. `FORCE_RETRAIN = True` redoes
  everything deliberately.
- Keep the tab open and interact occasionally on the free tier (idle
  disconnects are the most common cause of death, not the 12 h cap).

| # | Notebook | GPU? | Time (A100) | You get |
|---|---|---|---|---|
| 01 | data cleaning & preprocessing | no | ~10 min | validated datasets + audits + data cards |
| 02 | exploratory data analysis | no | ~5 min | all EDA figures (`reports/figures/`) |
| 03 | feature engineering / embeddings | helps | ~5 min | dual-embedding analysis + ChromaDB |
| 04 | model training | **yes** | ~45-60 min | LoRA adapter, BC+ACT+Diffusion checkpoints, **ONNX/TorchScript exports**, learning curves |
| 05 | evaluation & comparison | no | ~10 min | C1-C4 numbers, verdict table, thesis figures |

### 3.3 Bring the models home

Notebook 04's last cell downloads **`drona_trained_models.zip`**. On your PC:

```bash
unzip drona_trained_models.zip -d .     # at the repo root - paths match exactly
```

✅ **Verify**

```bash
PYTHONUTF8=1 python -c "from drona.interaction.act_policy import PolicyRouter; \
print(PolicyRouter(checkpoint_base_dir='data/checkpoints').get_policy('greet').name)"
# expect: LeRobotACTPolicy(...) or OnnxBCPolicy(greet) - NOT KeyframePolicy
PYTHONUTF8=1 python scripts/run_evaluation.py --c2 --c3   # thesis numbers, no LLM needed
```

(If you trained only locally: `python scripts/train_bc_gesture.py` then
`python scripts/export_policies.py` produces the deployment ONNX without Colab.)

---

## Part 4 · LLM serving, RAG index, API, web platform (Windows)

### 4.1 Ollama (the local advising LLM)

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M    # the default OLLAMA_MODEL
ollama serve                                     # leave running (often runs as a service)
```

If that tag is not in your Ollama library version, `.env.example` lists working
alternatives (`qwen3:4b`, `qwen2.5:3b-instruct-q4_K_M`); set `OLLAMA_MODEL` accordingly.

**Alternative - serve the fine-tuned model directly from Hugging Face weights
(no Ollama, no GGUF):** set `LLM_BACKEND=transformers` in `.env`. The advising
engine then loads the base model + your trained LoRA adapter
(`models/advising-lora/`) exactly like the embedding models are loaded. Best on
any CUDA GPU; on a CPU-only PC keep the default `ollama` backend - it is
several times faster there.

Optional - serve **your fine-tuned** model: export GGUF in notebook 04
(merge + llama.cpp instructions are in `docs/COLAB_TRAINING_GUIDE.md` §4),
`ollama create drona-advising -f Modelfile`, set `OLLAMA_MODEL=drona-advising`
in `.env`.

### 4.1b If replies feel slow - the latency playbook

Only the **final advising answer** waits on the LLM - the robot itself never
freezes (gestures are millisecond ONNX inference, and during generation it
plays a LISTEN gesture and says "Let me think about that..."; the web advisor
streams progress events over the websocket). To speed up the answer itself,
in order of preference:

1. **Confirm GPU offload is on.** Ollama automatically uses the GTX 1650.
   While a query runs: `ollama ps` - the model should show `100% GPU` (or a
   high split). `qwen2.5:3b` (1.9 GB) fits the 4 GB card fully;
   `qwen3:4b` is borderline and may split CPU/GPU. If it splits and feels
   slow, set `OLLAMA_MODEL=qwen2.5:3b-instruct-q4_K_M` for day-to-day dev.
2. **Demo / viva day: cloud Ollama on a free Colab GPU** - already documented
   as Option B in `docs/RUN_EVERYTHING.md` (run Ollama in a GPU notebook,
   point `OLLAMA_HOST` at the tunnel URL). Same open-source model, ~5x faster
   generation, zero code changes, still no paid API.
3. **Train a small fast fine-tune too.** Notebook 04's `BASE_MODEL` selector
   accepts `Qwen/Qwen2.5-1.5B-Instruct` (Apache-2.0) - it trains with the
   identical pipeline, fits entirely in the 4 GB card, and answers ~3x faster.
   Reporting the 4B-vs-1.5B quality/latency trade-off with
   `scripts/run_evaluation.py --llm` is thesis material (C4 measures latency),
   not a compromise.
4. **Shorter answers**: `LLM_MAX_TOKENS=600` in `.env` roughly halves
   generation time; `MAX_PATHWAYS=3` is already the default.

### 4.2 Build the RAG index

```bash
PYTHONUTF8=1 python scripts/ingest_data.py            # dual-collection ChromaDB
PYTHONUTF8=1 python scripts/ingest_data.py --stats-only
```

### 4.3 API + one advising round-trip

```bash
python scripts/run_api.py          # FastAPI on http://localhost:8000 (docs at /docs)
# in a second terminal:
python scripts/advise.py --query "What careers suit a Python + ML student in Nepal?"
```

### 4.4 Web platform

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

✅ **Verify**: open `http://localhost:3000/advisor`, ask a question - a
streamed, citation-grounded answer appears. `npm run build` completes with 13
routes. `/robot` shows the animated 6-DOF twin.

---

## Part 5 · WSL2 + ROS 2 Humble + Gazebo simulation

ROS 2 runs on Linux; on Windows 11 use WSL2 (no dual boot - WSLg shows GUI
windows on your desktop). Deeper explanations: `docs/wsl_setup.md`.

### 5.1 Install WSL2 + Ubuntu 22.04 (once, PowerShell as Administrator)

```powershell
wsl --install -d Ubuntu-22.04
# reboot if asked; create a Linux username/password on first launch
```

All following commands run **inside the Ubuntu shell** (`wsl` in a terminal).

### 5.2 Install ROS 2 Humble

```bash
sudo apt update && sudo apt install -y software-properties-common curl
sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
     -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | \
     sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update && sudo apt install -y \
    ros-humble-desktop \
    ros-dev-tools \
    ros-humble-ros-gz \
    ros-humble-rosbridge-suite \
    ros-humble-joint-state-publisher \
    ros-humble-xacro
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && source ~/.bashrc
```

(`ros-humble-ros-gz` pulls in Gazebo; if you want the newest Gazebo Harmonic
specifically, follow `docs/sim_setup_gazebo.md`.)

### 5.3 Python deps inside WSL

The drona nodes import the `drona` package, so install the repo in WSL too.
Your Windows checkout is visible at `/mnt/c/...`:

```bash
cd /mnt/c/Users/trish/Documents/Developer/D.R.O.N.A
pip install -e ".[deploy]"          # core + onnxruntime (robot-side inference)
# optional perception extras for camera modes:
pip install mediapipe opencv-python-headless
```

### 5.4 Build the ROS 2 workspace

```bash
cd /mnt/c/Users/trish/Documents/Developer/D.R.O.N.A/ros2_ws
colcon build --symlink-install
source install/setup.bash
echo "source $(pwd)/install/setup.bash" >> ~/.bashrc
```

✅ **Verify (stub mode - no simulator yet)**

```bash
ros2 launch drona_bringup drona_system.launch.py use_rviz:=true rosbridge:=true
```

In a **second** WSL terminal:

```bash
ros2 topic list                    # expect /drona/engagement /drona/joint_states /diagnostics ...
ros2 topic echo /diagnostics --once   # every drona/* component reports OK within ~5s
ros2 action send_goal /drona/execute_gesture_action \
    drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback
```

RViz shows the robot performing the greet gesture; the action returns
`success: true` with the policy name (`OnnxBCPolicy(greet)` once models are in).
With `rosbridge:=true`, the web app's `/robot` page ("Live ROS2" mode) drives
and mirrors this same robot.

### 5.5 Gazebo simulation (the full sim mirror)

```bash
ros2 launch drona_bringup drona_gazebo.launch.py
# headless (no GUI, e.g. weak GPU):  ... headless:=true
# GL trouble under WSL:  export LIBGL_ALWAYS_SOFTWARE=1
```

What you should see: the `drona_advising` world - the robot standing on a desk
facing a student figure. The gz model **physically performs** every gesture
(per-joint PID controllers fed from `/drona/joint_states`), and the head
camera publishes real rendered images.

✅ **Verify**

```bash
ros2 topic hz /drona/camera/image_raw      # ~15 Hz rendered camera
ros2 topic echo /drona/engagement --once   # perception consuming the SIM camera
ros2 action send_goal /drona/execute_gesture_action \
    drona_msgs/action/ExecuteGesture "{gesture_label: 'point'}" --feedback
# watch the gz robot point, then return to rest
ros2 bag record -o demo /drona/joint_states /drona/session_state   # optional demo capture
```

> Note: MediaPipe will not detect a "face" on the simple student figure - the
> sim proves the full camera→perception **data path**; engagement classification
> on real faces is exercised with the webcam (Part 8) or Isaac's human assets.

---

## Part 6 · NVIDIA Isaac Sim (optional - needs an RTX GPU, ≥8 GB VRAM)

The GTX 1650 dev box cannot run Isaac - use Gazebo (Part 5) locally, or Isaac
on a cloud GPU. Full guide: `docs/sim_setup_isaac.md`. Summary:

1. Install **NVIDIA Omniverse Launcher** → Isaac Sim (2023.1+).
2. Terminal 1 (Isaac's bundled python):
   `./python.sh <repo>/ros2_ws/src/drona_bringup/isaac/drona_isaac_stage.py`
3. Terminal 2 (ROS 2 sourced):
   `ros2 launch drona_bringup drona_isaac.launch.py`

Isaac publishes `/clock` and mirrors the articulation through its ROS 2 bridge;
the same verification commands from 5.4 apply.

---

## Part 7 · Full-system validation checklist

Run through this once, in order - it is the definition of "done":

- [ ] `pytest -q` → **440 passed** (Windows).
- [ ] `python scripts/ingest_data.py --stats-only` → curriculum + career docs indexed.
- [ ] Notebooks 01-05 executed on Colab; `reports/evaluation_report.json` +
      `reports/final_comparison.csv` exist and hybrid retrieval wins C1.
- [ ] `drona_trained_models.zip` unzipped; PolicyRouter reports a **learned**
      policy (not keyframe) for `greet`.
- [ ] `data/checkpoints/bc/export_manifest.json` exists (ONNX deployment
      formats, parity verified).
- [ ] Ollama serving; `scripts/advise.py` returns grounded advice with citations.
- [ ] Web `npm run build` → 13 routes; `/advisor` streams; `/robot` twin animates.
- [ ] WSL: `colcon build` clean; stub launch → `/diagnostics` all OK; action
      goal succeeds in RViz.
- [ ] Gazebo launch → camera at ~15 Hz, gz robot physically gestures.
- [ ] `ros2 bag record` captures a full session (for the demo video).

**Debugging checkpoints** (symptom → fix):

| Symptom | Fix |
|---|---|
| `pytest` import errors | re-run `pip install -e ".[dev,eval]"` in the right venv |
| O*NET download fails | re-run later or use the cached parquet (`--skip-onet`) |
| Retrieval empty / C1 skipped | `python scripts/ingest_data.py` first |
| Advisor refuses / errors | Ollama not running or model not pulled; check `OLLAMA_MODEL` in `.env` |
| Colab: "No GPU" | Runtime ▸ Change runtime type ▸ A100/T4, re-run cell 1 |
| LeRobot CLI flag errors | API drifts: `pip install -U git+https://github.com/huggingface/lerobot.git`, check `--help` |
| `colcon build` fails on `drona_msgs` | `sudo apt install ros-dev-tools` and re-source `/opt/ros/humble/setup.bash` |
| Nodes crash importing `drona` | Part 5.3 was skipped - `pip install -e .` inside WSL |
| Gazebo window black / GL errors | `export LIBGL_ALWAYS_SOFTWARE=1` or `headless:=true` |
| No camera images in Gazebo | you launched with `empty.sdf` somehow - the drona launch uses `drona_advising.sdf` (its Sensors system is required) |
| `/diagnostics` shows ERROR for a component | that node crashed - check its terminal output; the component name maps 1:1 to the node |
| Web `/robot` live mode dead | launch with `rosbridge:=true`; check `ws://localhost:9090` |

---

## Part 8 · Deploy to the physical robot (the only remaining task)

Everything before this point is hardware-independent. When the SO-100 arm and
a webcam are available:

1. **Connect hardware**: SO-100 via the U2D2 USB adapter (note the port -
   `/dev/ttyUSB0` typically; `ls /dev/ttyUSB*`), webcam via USB. In WSL2, USB
   pass-through uses `usbipd` (<https://github.com/dorssel/usbipd-win>) - or
   run ROS 2 on a native Ubuntu machine/Raspberry Pi connected to the robot.
2. **One-time calibration**: verify the arm's physical home position matches
   `REST_POSE` - procedure in `ros2_ws/src/drona_ros/drona_ros/arm_interface.py`
   (read tick values with Dynamixel Wizard, adjust `_CENTER_TICK` if needed).
3. **Tune** `ros2_ws/src/drona_bringup/config/hardware.yaml` only if needed
   (camera index, session timeout). The serial port is a launch argument.
4. **Launch**:
   ```bash
   ros2 launch drona_bringup drona_hardware.launch.py arm_port:=/dev/ttyUSB0 use_rviz:=true rosbridge:=true
   ```
5. **Verify** exactly as in 5.4: `/diagnostics` all OK, action goal `greet`
   moves the **real arm**, the webcam drives `/drona/engagement`, and the web
   `/robot` page mirrors the physical robot live.

No further software development is required: the same nodes, parameters,
policies (served from the exported ONNX), and web platform you validated in
simulation are what run on the robot.
