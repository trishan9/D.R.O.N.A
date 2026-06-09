"""
LoRA / PEFT configuration for fine-tuning Phi-3.5-mini on a Colab T4 (16 GB).

Defaults are sized for a free Colab T4: 4-bit base (QLoRA), rank-16 adapters on
the attention + MLP projections, small per-device batch with gradient
accumulation to reach an effective batch of 16, bf16/fp16 mixed precision.

The dataclass is pure (no heavy imports). ``to_peft_config()`` /
``to_bnb_config()`` / ``to_training_args()`` build the real objects lazily so
this module imports fine without peft/transformers/trl installed.

References: QLoRA (Dettmers et al. 2023) for 4-bit + LoRA on consumer GPUs;
target modules per the Phi-3 architecture (qkv_proj, o_proj, gate_up_proj, down_proj).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DronaLoraConfig:
    """Hyperparameters for the advising LoRA fine-tune."""

    base_model: str = "microsoft/Phi-3.5-mini-instruct"
    output_dir: str = "models/phi35-lora-advising"

    # LoRA
    r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list[str] = field(
        default_factory=lambda: [
            "qkv_proj",
            "o_proj",
            "gate_up_proj",
            "down_proj",
        ]
    )

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
