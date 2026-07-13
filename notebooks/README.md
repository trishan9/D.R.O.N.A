# D.R.O.N.A. notebooks — the ML pipeline

One staged suite, run **in order**. Designed for **Google Colab with an A100
GPU** (Runtime ▸ Change runtime type ▸ A100; T4 works too — everything
auto-falls back). Every notebook clones the repo itself (edit `REPO_URL` in
cell 1), regenerates any missing input, and saves publication-quality figures
to `reports/figures/`.

| # | Notebook | Stage | Needs GPU? | Wall time (A100) |
|---|----------|-------|-----------|------------------|
| 01 | `01_data_cleaning_preprocessing` | Download, validate, dedupe, outlier-flag and encode all datasets (O*NET 30.3 auto, BLS OEWS auto, optional ESCO/NLFS, all-programme curriculum, Nepali + international postings); build SFT + demonstration corpora | no | ~10 min |
| 02 | `02_exploratory_data_analysis` | Distributions, missingness, correlations, class balance, curriculum↔market alignment, gesture-trajectory EDA | no | ~5 min |
| 03 | `03_feature_engineering_embeddings` | Dual-embedding feature space (bge-small + JobBERT-v2), projections, similarity structure, dual-vs-single ablation, BM25 features, ChromaDB ingest | speeds it up | ~5 min |
| 04 | `04_model_training` | Advising-LLM LoRA (Qwen3-4B-Instruct-2507; bf16 on A100, QLoRA fallback), BC baseline + **ONNX/TorchScript export**, ACT, Diffusion Policy; learning curves, optional LR sweep, TensorBoard, one-zip export | **yes** | ~45-60 min |
| 05 | `05_model_evaluation_comparison` | C1-C4 metrics, three-way retrieval ablation, confusion matrices, policy statistics, base-vs-LoRA, final verdict table | no | ~10 min |

**Bring checkpoints home:** notebook 04's last cells zip
`models/advising-lora/` + `data/checkpoints/{bc,act,diffusion}/` into
`drona_trained_models.zip` — unzip it at the repo root on your PC and the
`PolicyRouter`, web robot-twin, ROS2 nodes, and the dashboard's `/evaluation`
analytics pick everything up automatically.

> **History note:** eleven earlier per-topic notebooks (data EDA, retrieval
> ablations, per-model trainers 07/08/09, …) were consolidated into this suite
> on 2026-07-12 — each stage supersedes its deep-dive predecessor. See git
> history if you ever need the originals.
