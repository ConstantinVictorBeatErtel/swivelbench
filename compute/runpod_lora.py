"""Pinned LoRA/SFT configuration for RunPod workers."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LoraConfig:
    model_id: str
    context_length: int = 16_384
    rank: int = 32
    alpha: int = 64
    dropout: float = 0.05
    learning_rate: float = 2e-4
    epochs: int = 2
    warmup_ratio: float = 0.03
    precision: str = "bf16"
    gradient_checkpointing: bool = True
    flash_attention: bool = True
    assistant_only_loss: bool = True
    packing: bool = True
    vision_encoder_frozen_first_pass: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


CREDIT_LORA = LoraConfig("Qwen/Qwen3-8B")
TEACHING_LORA = LoraConfig(
    "Qwen/Qwen3-VL-8B-Instruct", learning_rate=1e-4,
    vision_encoder_frozen_first_pass=True)
