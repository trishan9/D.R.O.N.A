"""
LoRA / PEFT configuration for fine-tuning the advising LLM on Colab (A100/T4).

Base model default: **Qwen/Qwen3-4B-Instruct-2507** (Apache-2.0) - the
strongest ~4B open instruct model at selection time (mid-2025 refresh,
non-thinking variant so JSON output stays clean), and it still serves locally
on CPU via Ollama after Q4 quantisation. Previous default
(microsoft/Phi-3.5-mini-instruct) remains a one-line swap.

``target_modules="all-linear"`` (QLoRA paper best practice) makes the adapter
architecture-agnostic - Qwen/Phi/Llama/Gemma all work without editing module
lists. Explicit per-architecture lists are kept in ``ARCH_TARGET_MODULES`` for
reference and ablations.

Sizing: on an A100 the notebook trains in full bf16; on a T4 it flips to
4-bit QLoRA. Effective batch stays 16 in both modes so runs are comparable.

The dataclass is pure (no heavy imports). ``to_peft_config()`` /
``to_bnb_config()`` / ``to_training_args()`` build the real objects lazily so
this module imports fine without peft/transformers/trl installed.

References: QLoRA (Dettmers et al. 2023) - 4-bit + LoRA, all-linear targeting.
"""

from __future__ import annotations

from dataclasses import dataclass

# Explicit per-architecture projection lists (reference / ablations). The
# default config uses "all-linear" instead, which covers all of these.
ARCH_TARGET_MODULES: dict[str, list[str]] = {
    "phi3": ["qkv_proj", "o_proj", "gate_up_proj", "down_proj"],
    "qwen": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    "llama": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
}


@dataclass
class DronaLoraConfig:
    """Hyperparameters for the advising LoRA fine-tune."""

    base_model: str = "Qwen/Qwen3-4B-Instruct-2507"
    output_dir: str = "models/advising-lora"

    # LoRA
    r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    # "all-linear" = LoRA on every linear layer (QLoRA paper best practice);
    # works across architectures. Use ARCH_TARGET_MODULES for explicit lists.
    target_modules: list[str] | str = "all-linear"

    # Quantization (QLoRA)
    load_in_4bit: bool = True
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_use_double_quant: bool = True

    # Training (T4-friendly)
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 8  # effective batch = 16
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    max_seq_length: int = 2048
    logging_steps: int = 10
    save_strategy: str = "epoch"
    seed: int = 230352

    @property
    def effective_batch_size(self) -> int:
        return self.per_device_train_batch_size * self.gradient_accumulation_steps

    # ── Lazy builders (require optional training deps) ──────────────────────

    def to_peft_config(self):
        from peft import LoraConfig

        return LoraConfig(
            r=self.r,
            lora_alpha=self.lora_alpha,
            lora_dropout=self.lora_dropout,
            target_modules=self.target_modules,
            bias="none",
            task_type="CAUSAL_LM",
        )

    def to_bnb_config(self):
        import torch
        from transformers import BitsAndBytesConfig

        return BitsAndBytesConfig(
            load_in_4bit=self.load_in_4bit,
            bnb_4bit_quant_type=self.bnb_4bit_quant_type,
            bnb_4bit_use_double_quant=self.bnb_4bit_use_double_quant,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

    def to_training_args(self):
        from transformers import TrainingArguments

        return TrainingArguments(
            output_dir=self.output_dir,
            num_train_epochs=self.num_train_epochs,
            per_device_train_batch_size=self.per_device_train_batch_size,
            gradient_accumulation_steps=self.gradient_accumulation_steps,
            learning_rate=self.learning_rate,
            warmup_ratio=self.warmup_ratio,
            weight_decay=self.weight_decay,
            logging_steps=self.logging_steps,
            save_strategy=self.save_strategy,
            seed=self.seed,
            bf16=True,
            report_to=[],
        )
