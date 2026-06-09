"""
LoRA fine-tuning package for D.R.O.N.A. (Phase 3).

Pipeline:
  1. qa_generator  — synthesise ~500 advising Q&A grounded in real data
  2. gold_set      — stratified-sample ~50 for human review (the gold set)
  3. dataset       — format pairs into chat SFT examples + train/val split
  4. lora_config   — Colab-T4-shaped PEFT/LoRA + training args
  5. ablation      — compare base+RAG vs LoRA+RAG over the eval query set
  6. model_card    — provenance card for the trained adapter

Heavy training deps (transformers/peft/trl/bitsandbytes) are OPTIONAL and only
needed in the Colab notebook (09_lora_finetune_phi35.ipynb). The data-prep and
ablation logic here is pure and runs offline with no GPU.
"""
