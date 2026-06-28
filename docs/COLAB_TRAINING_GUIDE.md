# D.R.O.N.A. - Colab / Kaggle Training & Finalization Guide

Every step to train the GPU-only models on **Google Colab or Kaggle**, bring the
checkpoints back, and run the **full system + simulation** on your PC.

> TL;DR of what runs where
>
> | Task | Where | Why |
> |---|---|---|
> | Data pipeline, embeddings, retrieval, CPU behavior-cloning policy, web app, tests | **Your PC (CPU)** | No GPU needed |
> | **Phi-3.5 LoRA fine-tune** (nb09) | **Colab/Kaggle GPU** | Needs CUDA + bitsandbytes |
> | **ACT policy** (nb07), **Diffusion policy** (nb08) | **Colab/Kaggle GPU** | LeRobot training needs a GPU |
> | Live LLM advising | Your PC + **Ollama** | Local-only inference (no paid API) |
> | Gazebo / RViz embodied sim | **WSL2 (Ubuntu) on Windows** | ROS2 only runs on Linux |

The local pipeline is already populated and verified (see `PROGRESS.md`). This
guide covers the parts that **could not** run on your CPU box.

---

## 0. One-time: get the project onto Colab/Kaggle

The notebooks need two things: the **code** (the `drona` package) and the
**training data**. The data regenerates itself from `scripts/prepare_training_data.py`,
so you only have to deliver the code. Pick **one** of these:

### Option A - GitHub (recommended)
1. Create a repo (private is fine) and push:
   ```bash
   git remote add origin https://github.com/<your-username>/D.R.O.N.A.git
   git push -u origin feat/data-training-bringup   # or main
   ```
2. In each notebook's **cell 1**, set:
   ```python
   REPO_URL = "https://github.com/<your-username>/D.R.O.N.A.git"
   ```
   Private repo? Use a fine-grained **read** token:
   `https://<TOKEN>@github.com/<your-username>/D.R.O.N.A.git`

### Option B - Zip upload (no GitHub)
1. On your PC, zip the project (exclude big/local folders):
   ```bash
   cd ..
   zip -r drona.zip D.R.O.N.A -x "*/node_modules/*" "*/.git/*" "*/.next/*" \
       "*/__pycache__/*" "*/data/chromadb/*" "*/data/lerobot/*"
   ```
2. **Colab:** Files panel (left) → upload `drona.zip` → add a cell before setup:
   `!unzip -q drona.zip`. **Kaggle:** create a **Dataset** from `drona.zip`
   (it mounts under `/kaggle/input/drona/`).
3. Leave `REPO_URL` unchanged - the setup cell auto-finds the unzipped/attached repo.

### Real data vs placeholders
The repo ships with **placeholder** curriculum + jobs so everything runs today.
For a *real* model, before training replace:
- `data/raw/curriculum/*.md` → your real Softwarica module descriptors (`.pdf/.docx/.md/.txt` all work), and
- `data/manual_collection/<portal>/*.json` → your collected postings (schema = `data/manual_collection/_template.json`).

Then commit them (Option A) or include them in the zip (Option B). `data/raw/` is
gitignored, so for GitHub either force-add your curriculum
(`git add -f data/raw/curriculum`) or rely on `make_placeholder_data.py` for dummies.

---

## 1. Notebook 09 - LoRA fine-tune of Phi-3.5 (advising brain, C2/C3)

**GPU required.** Colab: `Runtime ▸ Change runtime type ▸ T4 GPU`.
Kaggle: `Settings ▸ Accelerator ▸ GPU T4 x2`.

1. Open `notebooks/09_lora_finetune_phi35.ipynb` in Colab/Kaggle.
2. **Cell 1 (Setup):** edit `REPO_URL` (Option A) or rely on your upload (Option B). Run it - it prints the GPU and `repo:` path.
3. **Cell 2:** installs transformers/peft/trl/accelerate/datasets/bitsandbytes.
4. **Cell 3:** runs `prepare_training_data.py` → builds `data/finetune/sft_train.jsonl` (≈450) + `sft_val.jsonl` (≈50) and prints a sample.
5. **Cells 4–6:** load Phi-3.5 in 4-bit and **train** (`trainer.train()`). ~30–60 min on T4.
6. **Cell 7:** saves the adapter to `models/phi35-lora-advising/`.
7. **Cell 8 (optional):** export a merged **GGUF** for Ollama (uncomment the block).
8. **Cell 9:** quick base+LoRA generation sanity check.
9. **Cell 10:** zips + **downloads** `drona_phi35_lora_adapter.zip`.

**Bring it back (on your PC):**
```bash
unzip drona_phi35_lora_adapter.zip -d models/phi35-lora-advising
```

---

## 2. Notebook 07 - ACT gesture policy (C3)

**GPU required.**
1. Open `notebooks/07_lerobot_act_training.ipynb`.
2. **Cell 1:** setup (`REPO_URL`).
3. **Cell 2:** installs LeRobot.
4. **Cell 3:** regenerates demonstrations and builds the `LeRobotDataset` (self-contained).
5. **Cell 4:** **trains ACT** (`--steps=20000`; lower it for a quick smoke run). ~15–30 min.
6. **Cell 5:** evaluates ACT vs the keyframe baseline (success / jerk).
7. **Cell 6:** downloads `drona_act_checkpoints.zip`.

**Bring it back:**
```bash
unzip drona_act_checkpoints.zip -d data/checkpoints/act
```
The `PolicyRouter` auto-loads a per-gesture checkpoint from `data/checkpoints/<gesture>/`
when present - see notebook 11 / `STUDENT_RUNBOOK.md` for the exact layout if you
split per gesture.

## 3. Notebook 08 - Diffusion policy ablation (C3)
Same flow as nb07 (you can run it in the **same session** right after - the dataset
is reused). Output → `drona_diffusion_checkpoints.zip` → `data/checkpoints/diffusion`.
Cell 5 prints the three-way **keyframe vs ACT vs Diffusion** comparison for the thesis.

---

## 4. Serve the LoRA model locally with Ollama (live advising)

Retrieval (C1) works without any LLM, but the spoken advice (C2) needs a local model.

1. **Install Ollama:** <https://ollama.com/download> (Windows installer). Then in a terminal:
   ```bash
   ollama serve            # leave running (or it runs as a service)
   ```
2. **Easiest path - pull the model DRONA already defaults to** (no `.env` edit needed):
   ```bash
   ollama pull phi3.5:3.8b-mini-instruct-q4_K_M    # = the default OLLAMA_MODEL
   ollama pull qwen2.5:3b-instruct-q4_K_M          # the multilingual fallback (optional)
   ```
   To use a different model, copy `.env.example` → `.env` and set
   `OLLAMA_MODEL=<tag>` (e.g. `llama3.2:3b`).
3. **Your fine-tuned model** (if you exported GGUF in nb09 cell 8): create a
   `Modelfile` next to `models/phi35-advising.gguf`:
   ```
   FROM ./models/phi35-advising.gguf
   ```
   then:
   ```bash
   ollama create phi35-advising -f Modelfile
   ```
   and set `OLLAMA_MODEL=phi35-advising` in `.env`.

---

## 5. Finalize on your PC - ingest, advise, web, simulate

> Windows note: prefix CLI commands with `PYTHONUTF8=1` (Git Bash) or
> `$env:PYTHONUTF8=1` (PowerShell) - Python 3.14 + cp1252 consoles crash on the
> box-drawing characters these scripts print.

### 5a. Build the knowledge base (real embeddings)
```bash
python scripts/prepare_training_data.py     # (re)generate data; --skip-onet if cached
python scripts/ingest_data.py               # → ChromaDB: curriculum + career collections
python scripts/ingest_data.py --stats-only  # confirm doc counts
```

### 5b. Run the advising API (needs Ollama from step 4)
```bash
pip install -e ".[backend]"
python scripts/run_api.py                    # FastAPI at http://localhost:8000 ( /docs )
# quick test:
python scripts/advise.py --query "What careers suit a Python + ML student in Nepal?"
```

### 5c. Run the web app
```bash
cd frontend
npm install        # or: pnpm install
npm run dev        # http://localhost:3000  (set NEXT_PUBLIC_DRONA_API_URL if API not on :8000)
```
Pages: Dashboard, Advisor (live streaming), Pathways, Skills, Analytics, **Robot**
(animated 6-DOF twin + live ROS2 mode), Profile, Achievements, Preferences, About.

### 5d. Run the embodied simulation (no ROS2 needed)
```bash
# Gesture playback (uses your trained ACT checkpoints if present, else keyframe):
PYTHONUTF8=1 python scripts/run_simulation.py --no-viz --gestures greet,nod,point,farewell

# Full session: perception → FSM → gestures → advising (needs Ollama for the LLM step):
PYTHONUTF8=1 python scripts/run_simulation.py \
    --query "What careers suit a student who enjoys Python and data in Nepal?"

# CPU behavior-cloning baseline (no GPU/Colab) - trains + evaluates locally:
python scripts/collect_demonstrations.py --episodes 25
python scripts/train_bc_gesture.py
```

### 5e. Evaluation harness (thesis numbers)
```bash
python scripts/run_evaluation.py --c2 --c3      # bias-mitigation + gesture metrics
```

---

## 6. Gazebo / RViz embodied sim (WSL2)

ROS2 only runs on Linux; on Windows 11 use **WSL2** (full guide: `docs/wsl_setup.md`).
Summary once ROS2 Humble + Gazebo Harmonic are installed in WSL2:
```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch drona_bringup drona_system.launch.py use_rviz:=true rosbridge:=true
# trigger a gesture:
ros2 action send_goal /drona/execute_gesture_action \
    drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback
```
With `rosbridge:=true`, the web **Robot** page (`/robot`, "Live ROS2" mode) drives and
mirrors the real joint stream.

---

## 7. Finalization checklist

- [ ] (Optional) Replace placeholder curriculum + jobs with real data; re-run 5a.
- [ ] nb09 → LoRA adapter → `models/phi35-lora-advising/` (or GGUF → Ollama).
- [ ] nb07 → ACT checkpoints → `data/checkpoints/act/`.
- [ ] nb08 → Diffusion checkpoints → `data/checkpoints/diffusion/` (ablation).
- [ ] Ollama installed + model pulled/created; `OLLAMA_MODEL` set in `.env`.
- [ ] `python scripts/ingest_data.py` run → ChromaDB populated.
- [ ] API (`run_api.py`) + web (`npm run dev`) up; `/advisor` streams a real answer.
- [ ] `run_simulation.py` full session completes with advising.
- [ ] (Optional) WSL2 ROS2 build + `drona_system.launch.py` for Gazebo/RViz.
- [ ] `pytest -q` → green; record the demo (`docs/demo_video_script.md`).

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `No GPU` in cell 1 | Switch the runtime/accelerator to a T4 GPU and re-run. |
| `Repo not found` assert | Set `REPO_URL`, or upload the zip / attach the Kaggle dataset, then re-run cell 1. |
| `bitsandbytes` / CUDA error (LoRA) | You're on CPU - select a GPU runtime. bitsandbytes is GPU-only. |
| LeRobot CLI flag errors | LeRobot's API drifts; `pip install -U git+...lerobot.git` and check `python -m lerobot.scripts.train --help`. |
| Colab session disconnects mid-train | Lower `--steps` / epochs, or save to Google Drive (`drive.mount`) and resume. |
| `UnicodeEncodeError` on Windows CLI | Prefix with `PYTHONUTF8=1` (Git Bash) / `$env:PYTHONUTF8=1` (PowerShell). |
| Advisor returns a refusal / error | Ollama not running or `OLLAMA_MODEL` unset/unpulled. Start `ollama serve`, pull a model, set `.env`. |
| Retrieval empty | Run `python scripts/ingest_data.py` first (ChromaDB must be populated). |
