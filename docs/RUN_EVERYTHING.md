# D.R.O.N.A. - RUN EVERYTHING (the one complete guide)

This is the **single, self-contained guide** that takes the project from a fresh
machine to a fully working system: data → knowledge base → the LLM → the trained
GPU models → the web app → the simulation. Follow it top to bottom. Every command
is copy-paste ready, with **Git Bash** and **PowerShell** variants where they differ.

> **Windows must-do:** every Python CLI here is prefixed with `PYTHONUTF8=1`
> (Git Bash) because Python 3.14 + the Windows console crash on the box-drawing
> characters the scripts print. In **PowerShell** run `$env:PYTHONUTF8 = "1"` once
> per terminal instead of the prefix.

---

## Contents
- [0. Big picture + the LLM decision (read this)](#0-big-picture--the-llm-decision)
- [1. One-time local setup](#1-one-time-local-setup)
- [2. Prepare the data](#2-prepare-the-data)
- [3. Build the knowledge base (embeddings)](#3-build-the-knowledge-base)
- [4. The LLM - TWO OPTIONS (pick one)](#4-the-llm--two-options)
- [5. Train the GPU models on Colab/Kaggle](#5-train-the-gpu-models-on-colabkaggle)
- [6. Train the CPU gesture model (optional, already done)](#6-train-the-cpu-gesture-model)
- [7. Run the whole system (API + web + sim)](#7-run-the-whole-system)
- [8. (Optional) Gazebo / ROS2 robot sim in WSL2](#8-optional-gazebo--ros2-robot-sim)
- [9. Evaluation + notebooks](#9-evaluation--notebooks)
- [10. Record the demo](#10-record-the-demo)
- [11. Troubleshooting](#11-troubleshooting)
- [12. Final checklist](#12-final-checklist)

---

## 0. Big picture + the LLM decision

**What runs where**

| Piece | Where | Needs |
|---|---|---|
| Data, embeddings, retrieval, CPU gesture model, web app, tests | **Your PC** | nothing special |
| LoRA fine-tune, ACT, Diffusion policies | **Colab / Kaggle GPU** | a free T4 GPU |
| The advising LLM | **Local Ollama** *or* **cloud Ollama** | see below |
| Gazebo / RViz robot sim | **WSL2 (Ubuntu)** | one-time install |

### The LLM - will it run on your device?

**Yes.** The advisor uses a **3-billion-parameter, 4-bit quantized** model
(`qwen3:4b-instruct-2507-q4_K_M`, ~2.5 GB). That runs on **CPU with ~4 GB RAM**,
and your GTX 1650 (4 GB) offloads some layers to speed it up. It is **slower** than
a data-center GPU (expect a short pause per answer), but it works and it is **free,
private, and offline** - which is the entire point of your **C4 contribution
(Nepal-local, open-source, no paid APIs)**.

So you have two options:

| | **Option A - Local Ollama** ⭐ recommended | **Option B - Cloud-GPU Ollama** |
|---|---|---|
| Runs on | your PC (CPU + GTX 1650) | a free Colab/Kaggle GPU you expose to your PC |
| Speed | slower (seconds per answer) | fast |
| Cost / privacy | free, fully offline, private | free, but data leaves your PC over a tunnel |
| Thesis (C4 "local-only") | ✅ exactly the claim | ⚠️ self-hosted, weaker version of the claim |
| Best for | **everyday use + the real thesis story** | **recording the demo if local feels slow** |

**Recommendation: use Option A (local Ollama).** It is genuinely fine on your
hardware and it *is* the contribution. Keep **Option B** in your back pocket only if
you want snappy responses while screen-recording the demo. Both use the same
open-source Ollama - **never** a paid API (that would break C4; the repo enforces it).

---

## 1. One-time local setup

### 1.1 Prerequisites (install once)
- **Python 3.10+** (you have 3.14) - <https://www.python.org/downloads/>
- **Node.js 18+** (you have v25) - <https://nodejs.org/>
- **Git** - <https://git-scm.com/>

### 1.2 Get the project + Python dependencies
```bash
# from the folder that contains the repo
cd D.R.O.N.A
pip install -e ".[dev,backend]"
```
This installs the `drona` package, the data/ML stack, and the FastAPI backend.

### 1.3 Create your .env
```bash
cp .env.example .env
```
Defaults are fine for **Option A**. You only edit `.env` for **Option B** (later).

### 1.4 Frontend dependencies
```bash
cd frontend
npm install        # (pnpm install also works)
cd ..
```

### 1.5 Sanity check
```bash
# Git Bash
PYTHONUTF8=1 python -c "import drona; print('drona OK')"
PYTHONUTF8=1 python -m pytest -q        # expect: 440 passed, 1 skipped
```
```powershell
# PowerShell equivalent
$env:PYTHONUTF8 = "1"
python -c "import drona; print('drona OK')"
python -m pytest -q
```

---

## 2. Prepare the data

The repo ships with **placeholder** curriculum + Nepali jobs so everything works
today. One command builds **every** input (placeholder data + the real O*NET
dataset + the LoRA training set + the gesture demonstrations):

```bash
PYTHONUTF8=1 python scripts/prepare_training_data.py
```
Expected tail: `SFT train=450 val=50`, `5000 frames / 150 episodes`, `All training inputs ready`.

### Using your REAL data (do this when you have it)
1. Put real module descriptors (`.pdf/.docx/.md/.txt`) in `data/raw/curriculum/`
   (delete the dummy `*.md` first).
2. Put real postings in `data/manual_collection/<portal>/*.json`
   (schema = `data/manual_collection/_template.json`; delete the dummy
   `*_placeholder_postings.json`).
3. Re-run the command above, then re-ingest (Part 3). Everything downstream adapts.

---

## 3. Build the knowledge base

Embed the data into the dual ChromaDB collections (this is C1):
```bash
PYTHONUTF8=1 python scripts/ingest_data.py
PYTHONUTF8=1 python scripts/ingest_data.py --stats-only   # verify
```
Expected: `curriculum collection: 50 documents`, `career collection: 79 documents`
(numbers change with your real data). First run downloads the embedding models
(~500 MB) once.

---

## 4. The LLM - TWO OPTIONS

Pick **A** (recommended) or **B**. You only need one.

### Option A ⭐ - Local Ollama (recommended)

**A1. Install Ollama**
- Windows: download + run the installer from <https://ollama.com/download>.
- After install, Ollama runs in the background automatically. Verify in a terminal:
  ```bash
  ollama --version
  ```

**A2. Pull the model DRONA defaults to** (no `.env` edit needed)
```bash
ollama pull qwen2.5:3b-instruct-q4_K_M          # primary: fast, typo-robust, multilingual
ollama pull qwen3:4b-instruct-2507-q4_K_M    # fallback (optional)
```

**A3. Test it**
```bash
ollama run qwen2.5:3b-instruct-q4_K_M "Say hello in one sentence."
```
If it replies, you're done. (Leave Ollama running; on Windows it stays in the tray.)

> **About speed:** the **first** query loads the model (slow, one-time). DRONA keeps
> it warm (`OLLAMA_KEEP_ALIVE=30m`) so later queries are much faster. If it's still
> slow, free GPU memory (close Chrome) so the 3B model fits in your 4 GB card, try
> an even smaller model (`ollama pull llama3.2:1b` then set `OLLAMA_MODEL=llama3.2:1b`),
> or use **Option B**.

➡️ **Skip Option B - go to [Part 5](#5-train-the-gpu-models-on-colabkaggle).**

---

### Option B - Cloud-GPU Ollama (only if local is too slow)

You run Ollama on a **free Kaggle/Colab GPU** and expose it to your PC through a
secure tunnel. Your PC's API then talks to that URL. Still open-source Ollama, no
paid API. **Caveat:** free cloud sessions expire after a few hours, so do this when
you're actively using/recording, not 24/7.

**B1. In a Kaggle or Colab notebook** (GPU runtime on), run these cells:

```python
# Cell 1 - install Ollama and start the server bound to all interfaces
import os, subprocess, time
subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
os.environ["OLLAMA_HOST"] = "0.0.0.0:11434"          # so the tunnel can reach it
subprocess.Popen(["ollama", "serve"])
time.sleep(6)
subprocess.run(["ollama", "pull", "qwen3:4b-instruct-2507-q4_K_M"], check=True)
print("ollama ready")
```

```python
# Cell 2 - open a public tunnel to port 11434 (cloudflared, no signup)
subprocess.run("wget -q https://github.com/cloudflare/cloudflared/releases/latest/"
               "download/cloudflared-linux-amd64 -O cloudflared && chmod +x cloudflared",
               shell=True, check=True)
# This prints a https://<random>.trycloudflare.com URL - COPY IT.
# It keeps running; leave this cell running while you use DRONA.
get_ipython().system_raw("./cloudflared tunnel --url http://localhost:11434 "
                         "> cloudflared.log 2>&1 &")
time.sleep(8)
print(open("cloudflared.log").read())   # find the https://...trycloudflare.com line
```
Copy the printed `https://<something>.trycloudflare.com` URL.

**B2. On your PC**, point DRONA at that URL. Edit `.env`:
```
OLLAMA_HOST=https://<something>.trycloudflare.com
OLLAMA_MODEL=qwen3:4b-instruct-2507-q4_K_M
```
That's it - the backend now sends advising requests to the cloud GPU. When the
cloud session ends, re-run B1–B2 and update the URL (or switch back to Option A).

---

## 5. Train the GPU models on Colab/Kaggle

Three models need a GPU. The notebooks are ready; you just deliver the code and run.

> **Recommended:** on a Colab **A100**, use the staged pipeline
> [`notebooks/`](../notebooks/README.md) instead of the individual
> notebooks below - `notebooks/04_model_training.ipynb` trains the LoRA + BC + ACT
> + Diffusion models in one sitting (~45-60 min) and exports a single
> `drona_trained_models.zip`, and `notebook 05` produces all the thesis figures.
> The steps below remain the minimal T4 path.

### 5.1 Get the repo onto Colab/Kaggle (do this once)

**Easiest - GitHub:**
```bash
# create an empty repo on github.com first (private is fine), then:
git push -u origin feat/data-training-bringup
```
You'll set this URL inside each notebook's first cell.

**No GitHub? - zip upload:**
```bash
cd ..
zip -r drona.zip D.R.O.N.A -x "*/node_modules/*" "*/.git/*" "*/.next/*" \
    "*/__pycache__/*" "*/data/chromadb/*" "*/data/lerobot/*"
```
Colab: upload `drona.zip` (Files panel) and add a first cell `!unzip -q drona.zip`.
Kaggle: make a **Dataset** from `drona.zip` (mounts under `/kaggle/input/`).

### 5.2 Notebook 04 - train every model in one sitting
1. Set the GPU: Colab `Runtime ▸ Change runtime type ▸ A100` (T4 also works).
2. Open `notebooks/04_model_training.ipynb`, set `REPO_URL` in cell 1, **Run all**.
   It trains the advising LoRA + BC (with ONNX export) + ACT + Diffusion and
   downloads one **`drona_trained_models.zip`**.
3. **On your PC:**
   ```bash
   unzip drona_trained_models.zip -d .    # at the repo root
   ```

> Want the LoRA model served by Ollama? Merge + GGUF-convert (COLAB guide
> section 4), or simpler: serve it directly with `LLM_BACKEND=transformers`. A
> GGUF. Then locally: create a `Modelfile` with `FROM ./models/advising.gguf`,
> run `ollama create drona-advising -f Modelfile`, and set
> `OLLAMA_MODEL=drona-advising` in `.env`.

---

## 6. Train the CPU gesture model

This one needs **no GPU** and is already trained in the repo. To (re)train the
phase-indexed behavior-cloning policy and see it beat/match the keyframe baseline:
```bash
PYTHONUTF8=1 python scripts/collect_demonstrations.py --episodes 25
PYTHONUTF8=1 python scripts/train_bc_gesture.py        # 6 gestures, ~1 min, 100% success
```
Checkpoints land in `data/checkpoints/bc/`.

---

## 7. Run the whole system

Open **three terminals** (or run the API + web, then the sim).

**Terminal 1 - advising API** (needs the LLM from Part 4 running):
```bash
PYTHONUTF8=1 python scripts/run_api.py        # http://localhost:8000  (docs at /docs)
```

**Terminal 2 - web app:**
```bash
cd frontend
npm run dev                                   # http://localhost:3000
```
Open <http://localhost:3000>. Pages: Dashboard, **Advisor** (live streaming),
Pathways, Skills, Analytics, **Robot** (animated 6-DOF twin + live ROS2 mode),
Profile, Achievements, Preferences, About.
> If the API isn't on port 8000, create `frontend/.env.local` with
> `NEXT_PUBLIC_DRONA_API_URL=http://localhost:8000`.

**Terminal 3 - embodied simulation** (no ROS2 needed):
```bash
# gesture playback (uses your trained ACT checkpoints if present, else keyframe):
PYTHONUTF8=1 python scripts/run_simulation.py --no-viz --gestures greet,nod,point,farewell

# full session: perception → FSM → gestures → advising (needs the LLM):
PYTHONUTF8=1 python scripts/run_simulation.py \
    --query "What careers suit a student who enjoys Python and data in Nepal?"
```

**Quick CLI advice (no web):**
```bash
PYTHONUTF8=1 python scripts/advise.py --query "Career paths for a Python + ML student in Nepal?"
```

---

## 8. (Optional) Gazebo / ROS2 robot sim

ROS2 only runs on Linux; on Windows 11 use **WSL2**. Full one-time install:
[`docs/wsl_setup.md`](wsl_setup.md). Once ROS2 Humble + Gazebo Harmonic are in WSL2:
```bash
# inside WSL2 (Ubuntu), in the repo's ros2_ws:
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch drona_bringup drona_system.launch.py use_rviz:=true rosbridge:=true
# trigger a gesture from another WSL terminal:
ros2 action send_goal /drona/execute_gesture_action \
    drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback
```
With `rosbridge:=true`, the web **Robot** page ("Live ROS2" mode) drives and mirrors
the real joint stream.

---

## 9. Evaluation + notebooks

**Metrics harness (C1–C4):**
```bash
PYTHONUTF8=1 python scripts/run_evaluation.py --all --out data/evaluation/eval_report.json
# add --llm once Ollama is running for response-level numbers
```

**Analysis notebooks** (already executed in the repo with outputs). To re-run them:
```bash
PYTHONUTF8=1 python -m nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=400 notebooks/01_data_eda.ipynb
# (repeat for 02–06, 10, 11; or open them in VS Code / Jupyter and Run All)
```
07/08/09 are the GPU notebooks from Part 5.

---

## 10. Record the demo

Shot-by-shot script: [`docs/demo_video_script.md`](demo_video_script.md).
Suggested flow: web Advisor (ask a biased question → see bias flags + multiple
pathways) → Pathways comparison → Robot page gesture → (optional) Gazebo →
Analytics. Use **Option B** for the LLM if you want snappy responses on camera.

---

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| `UnicodeEncodeError` / weird crash on a Python script | Prefix `PYTHONUTF8=1` (Git Bash) or run `$env:PYTHONUTF8="1"` (PowerShell). |
| Advisor returns a refusal / "could not generate" | The LLM isn't reachable. Option A: is Ollama running + model pulled? Option B: is the tunnel cell still running + `OLLAMA_HOST` correct in `.env`? |
| Ollama answers very slowly | Use `qwen2.5:3b` as `OLLAMA_MODEL`, close other apps, or use Option B. |
| Retrieval empty / advisor has no evidence | Run `python scripts/ingest_data.py` (Part 3) first. |
| `bitsandbytes` / CUDA error in a notebook | You're on CPU - select a **GPU** runtime (Part 5.2 step 1). |
| Notebook 04 LeRobot flag errors | `pip install -U git+https://github.com/huggingface/lerobot.git`; check `python -m lerobot.scripts.train --help`. |
| Colab/Kaggle session disconnected mid-train | Lower `--steps`/epochs, or save to Google Drive and resume. |
| `cloudflared` URL stopped working | The cloud session ended - re-run B1–B2 and update `OLLAMA_HOST`. |
| Web app can't reach API | API not running, or set `NEXT_PUBLIC_DRONA_API_URL` in `frontend/.env.local`. |
| `colcon`/`ros2` not found | That's a WSL2 step (Part 8 / `docs/wsl_setup.md`), not Windows. |

---

## 12. Final checklist

Local, no GPU:
- [ ] `pip install -e ".[dev,backend]"` + `cp .env.example .env`
- [ ] `python scripts/prepare_training_data.py`
- [ ] `python scripts/ingest_data.py` → ChromaDB populated
- [ ] `python scripts/train_bc_gesture.py` → gesture model (already in repo)
- [ ] `pytest -q` → green

The LLM (pick one):
- [ ] **A:** Ollama installed + `ollama pull qwen3:4b-instruct-2507-q4_K_M`, **or**
- [ ] **B:** cloud Ollama + cloudflared tunnel + `OLLAMA_HOST` set in `.env`

GPU models (Colab/Kaggle):
- [ ] notebook 04 → `drona_trained_models.zip` unzipped at repo root
      (adapter + BC/ONNX + ACT + Diffusion)

Run + finalize:
- [ ] API (`run_api.py`) + web (`npm run dev`) → `/advisor` streams a real answer
- [ ] `run_simulation.py` full session completes with advising
- [ ] `run_evaluation.py --all --llm` for the thesis numbers
- [ ] (Optional) WSL2 Gazebo via `drona_system.launch.py`
- [ ] (Optional) real curriculum/jobs swapped in + re-ingested
- [ ] Demo recorded
