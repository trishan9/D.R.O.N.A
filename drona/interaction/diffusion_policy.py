"""
Diffusion Policy wrapper for D.R.O.N.A. gestures — C3 ablation (Chi et al. 2023).

Diffusion Policy models the action distribution with a conditional denoising
diffusion process, which captures multimodal action distributions better than
ACT's deterministic chunk regression. We include it purely as the **ablation
comparison** against ACT (the proposal's C3 secondary policy), sharing the same
LeRobot dataset and the same `BasePolicy` interface so the sim-eval harness can
score them identically.

Like the ACT wrapper, this lazy-imports LeRobot and falls back transparently to
the KeyframePolicy when LeRobot/checkpoint is unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from drona.interaction.act_policy import BasePolicy, KeyframePolicy
from drona.interaction.demonstration import clamp_joints


class LeRobotDiffusionPolicy(BasePolicy):
    """Wraps HuggingFace LeRobot's Diffusion Policy for gesture inference."""

    def __init__(self, checkpoint_dir: str | Path, device: str = "cpu") -> None:
        self._checkpoint_dir = Path(checkpoint_dir)
        self._device = device
        self._policy: Any = None
        self._load()

    def _load(self) -> None:
        try:
            from lerobot.common.policies.diffusion.modeling_diffusion import (  # type: ignore[import]
                DiffusionPolicy as _Diffusion,
            )
        except ImportError as exc:
            raise RuntimeError(
                "LeRobot not installed. Install with: "
                "pip install git+https://github.com/huggingface/lerobot.git"
            ) from exc
        if not self._checkpoint_dir.exists():
            raise FileNotFoundError(
                f"Diffusion checkpoint not found: {self._checkpoint_dir}. "
                "Train via notebooks/08_lerobot_diffusion_policy.ipynb first."
            )
        logger.info(f"Loading Diffusion Policy from {self._checkpoint_dir} on {self._device}")
        self._policy = _Diffusion.from_pretrained(str(self._checkpoint_dir))
        self._policy.eval()
        if hasattr(self._policy, "to"):
            self._policy.to(self._device)

    def reset(self) -> None:
        if self._policy is not None and hasattr(self._policy, "reset"):
            self._policy.reset()

    def select_action(self, obs_dict: dict[str, Any]) -> np.ndarray:
        import torch

        state = np.asarray(obs_dict["observation.state"], dtype=np.float32)
        tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            action = self._policy.select_action({"observation.state": tensor})
        arr = action.squeeze(0).cpu().numpy() if isinstance(action, torch.Tensor) else np.array(action)
        if arr.ndim > 1:
            arr = arr[0]
        return clamp_joints(arr.astype(np.float32))

    @property
    def name(self) -> str:
        return f"LeRobotDiffusion({self._checkpoint_dir.name})"


def make_diffusion_or_keyframe(
    gesture_label: str, checkpoint_dir: str | Path | None, device: str = "cpu"
) -> BasePolicy:
    """Return a Diffusion policy if available, else the keyframe baseline."""
    if checkpoint_dir is not None:
        ckpt = Path(checkpoint_dir) / gesture_label
        if ckpt.exists():
            try:
                return LeRobotDiffusionPolicy(ckpt, device=device)
            except (RuntimeError, ImportError, FileNotFoundError) as exc:
                logger.warning(f"Diffusion unavailable for '{gesture_label}': {exc}; using keyframe")
    return KeyframePolicy(gesture_label)
