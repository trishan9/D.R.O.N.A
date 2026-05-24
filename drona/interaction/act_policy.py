"""
ACT policy wrapper for D.R.O.N.A. — Research Contribution C3.

ACT (Action Chunking with Transformers) is an imitation learning policy that
predicts a chunk of future actions from the current observation, trained on
demonstration data. It was introduced by Zhao et al. (2023) and is the core
algorithm in the HuggingFace LeRobot framework.

Why ACT for robotic advising gestures?
  ACT's action chunking significantly reduces compounding error compared to
  step-by-step prediction — critical for long, smooth gestures like waves and
  greetings. Its Transformer architecture also naturally handles the temporal
  structure of gesture execution (Zhao et al., 2023, §4).

Two-tier policy architecture:

  1. KeyframePolicy (always available)
     Interpolates between pre-programmed keyframes from demonstration.py.
     Used in Phase 1 (no trained model), for unit tests, and as the initial
     rollout policy before ACT training converges.

  2. ACTPolicy (requires LeRobot + trained checkpoint)
     Wraps lerobot.common.policies.act.ACTPolicy. If LeRobot is installed
     and a checkpoint path is provided, this is the live inference policy.
     Falls back to KeyframePolicy transparently if unavailable.

Both expose the same interface:
    policy.reset()
    action_chunk = policy.select_action(obs_dict)  # obs_dict["observation.state"]
    # action_chunk shape: (chunk_size, DOF)

The PolicyRouter selects the appropriate backend based on availability and
logs which is active, which is important for evaluation transparency (C3
claim: "ACT-trained policy outperforms keyframe baseline on smoothness").
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from drona.interaction.demonstration import (
    DOF,
    GESTURE_KEYFRAMES,
    REST_POSE,
    clamp_joints,
    interpolate_keyframes,
)


# ── Base interface ─────────────────────────────────────────────────────────────

class BasePolicy(ABC):
    """Shared interface for all gesture policies."""

    @abstractmethod
    def reset(self) -> None:
        """Reset any internal state (e.g. recurrent hidden states)."""

    @abstractmethod
    def select_action(self, obs_dict: dict[str, Any]) -> np.ndarray:
        """Predict the next action given the current observation.

        Args:
            obs_dict: Must contain "observation.state" (ndarray, shape DOF).

        Returns:
            action: shape (DOF,) — joint position targets.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable policy name for logging and evaluation."""


# ── Keyframe policy ────────────────────────────────────────────────────────────

class KeyframePolicy(BasePolicy):
    """Deterministic policy that replays pre-programmed keyframe trajectories.

    This is the Phase 1 baseline — it does not learn from data. It exists to:
      a) Make the system functional before ACT training is complete
      b) Serve as the "scripted baseline" in the C3 evaluation comparison
      c) Generate initial demonstration data for ACT training bootstrap

    When a gesture is requested, the trajectory is pre-computed from keyframes
    and replayed frame-by-frame. `select_action()` is stateful — it advances
    through the trajectory on each call.
    """

    def __init__(self, gesture_label: str, dt: float = 0.05) -> None:
        if gesture_label not in GESTURE_KEYFRAMES:
            raise ValueError(
                f"Unknown gesture: {gesture_label!r}. "
                f"Known: {list(GESTURE_KEYFRAMES)}"
            )
        self._gesture_label = gesture_label
        self._dt = dt
        self._trajectory: list[tuple[np.ndarray, float]] = []
        self._frame_idx = 0
        self._precompute()

    def _precompute(self) -> None:
        keyframes = GESTURE_KEYFRAMES[self._gesture_label]
        self._trajectory = interpolate_keyframes(keyframes, dt=self._dt)

    def reset(self) -> None:
        self._frame_idx = 0

    def select_action(self, obs_dict: dict[str, Any]) -> np.ndarray:
        if self._frame_idx >= len(self._trajectory):
            # Gesture complete — hold rest pose
            return REST_POSE.copy()
        action, _ = self._trajectory[self._frame_idx]
        self._frame_idx += 1
        return clamp_joints(action.astype(np.float32))

    @property
    def is_complete(self) -> bool:
        return self._frame_idx >= len(self._trajectory)

    @property
    def total_frames(self) -> int:
        return len(self._trajectory)

    @property
    def name(self) -> str:
        return f"KeyframePolicy({self._gesture_label})"


# ── ACT policy wrapper ─────────────────────────────────────────────────────────

class LeRobotACTPolicy(BasePolicy):
    """Wraps HuggingFace LeRobot's ACT policy for gesture inference.

    Lazy-imports lerobot so the rest of the system runs without it installed.
    Requires a trained checkpoint directory containing config.json and
    model weights (the standard LeRobot save format).

    Observation keys expected by LeRobot ACT:
        "observation.state" — shape (DOF,), dtype float32

    The policy outputs an action chunk of shape (chunk_size, DOF).
    We return the first action in the chunk (standard single-step rollout);
    for smoother execution consider temporal ensemble (Zhao et al. 2023 §5).
    """

    def __init__(
        self,
        checkpoint_dir: str | Path,
        device: str = "cpu",
        use_temporal_ensemble: bool = False,
    ) -> None:
        self._checkpoint_dir = Path(checkpoint_dir)
        self._device = device
        self._use_ensemble = use_temporal_ensemble
        self._policy: Any = None  # lazy-loaded
        self._chunk_buffer: list[np.ndarray] = []
        self._load()

    def _load(self) -> None:
        try:
            import torch
            from lerobot.common.policies.act.modeling_act import ACTPolicy as _ACT  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "LeRobot is not installed. Install with: "
                "pip install git+https://github.com/huggingface/lerobot.git"
            ) from exc

        if not self._checkpoint_dir.exists():
            raise FileNotFoundError(
                f"ACT checkpoint not found: {self._checkpoint_dir}. "
                "Train with scripts/train_act.py first."
            )

        logger.info(f"Loading ACT policy from {self._checkpoint_dir} on {self._device}")
        self._policy = _ACT.from_pretrained(str(self._checkpoint_dir))
        self._policy.eval()
        if hasattr(self._policy, "to"):
            self._policy.to(self._device)
        logger.info("ACT policy loaded")

    def reset(self) -> None:
        self._chunk_buffer = []
        if self._policy is not None and hasattr(self._policy, "reset"):
            self._policy.reset()

    def select_action(self, obs_dict: dict[str, Any]) -> np.ndarray:
        import torch

        # If we have buffered actions from a previous chunk, consume them
        if self._use_ensemble and self._chunk_buffer:
            return self._chunk_buffer.pop(0)

        obs_state = np.asarray(obs_dict["observation.state"], dtype=np.float32)
        obs_tensor = torch.tensor(obs_state, dtype=torch.float32).unsqueeze(0)

        with torch.no_grad():
            action_chunk = self._policy.select_action(
                {"observation.state": obs_tensor}
            )  # shape (1, chunk_size, DOF) or (chunk_size, DOF)

        if isinstance(action_chunk, torch.Tensor):
            action_np = action_chunk.squeeze(0).cpu().numpy()  # (chunk_size, DOF) or (DOF,)
        else:
            action_np = np.array(action_chunk)

        if action_np.ndim == 1:
            # Single action returned
            return clamp_joints(action_np.astype(np.float32))

        # Action chunk: buffer remaining, return first
        if self._use_ensemble:
            self._chunk_buffer = [
                clamp_joints(action_np[i].astype(np.float32))
                for i in range(1, len(action_np))
            ]
        return clamp_joints(action_np[0].astype(np.float32))

    @property
    def name(self) -> str:
        return f"LeRobotACT({self._checkpoint_dir.name})"


# ── Policy router ──────────────────────────────────────────────────────────────

class PolicyRouter:
    """Selects and caches the best available policy for each gesture.

    Priority:
      1. LeRobotACTPolicy (if checkpoint exists and lerobot installed)
      2. KeyframePolicy (always available)

    Caches one policy per gesture label to avoid repeated model loading.
    """

    def __init__(
        self,
        checkpoint_base_dir: str | Path | None = None,
        device: str = "cpu",
    ) -> None:
        self._checkpoint_base = Path(checkpoint_base_dir) if checkpoint_base_dir else None
        self._device = device
        self._cache: dict[str, BasePolicy] = {}

    def get_policy(self, gesture_label: str) -> BasePolicy:
        """Return (and cache) the best available policy for this gesture."""
        if gesture_label in self._cache:
            return self._cache[gesture_label]

        policy = self._load_policy(gesture_label)
        self._cache[gesture_label] = policy
        logger.info(f"Policy for '{gesture_label}': {policy.name}")
        return policy

    def _load_policy(self, gesture_label: str) -> BasePolicy:
        if self._checkpoint_base is not None:
            ckpt = self._checkpoint_base / gesture_label
            if ckpt.exists():
                try:
                    return LeRobotACTPolicy(ckpt, device=self._device)
                except (RuntimeError, ImportError, FileNotFoundError) as exc:
                    logger.warning(
                        f"Could not load ACT policy for '{gesture_label}': {exc}. "
                        "Falling back to KeyframePolicy."
                    )
        return KeyframePolicy(gesture_label)

    def clear_cache(self) -> None:
        self._cache.clear()


# ── Smoothness metric (for C3 evaluation) ─────────────────────────────────────

def trajectory_smoothness(trajectory: list[np.ndarray]) -> float:
    """Compute trajectory smoothness as mean jerk (lower = smoother).

    Jerk = third derivative of position. We approximate via finite differences.
    Used in the C3 evaluation to compare ACT vs keyframe baseline.

    Args:
        trajectory: List of joint position arrays (shape DOF each).

    Returns:
        Mean absolute jerk (radians/s³), averaged over joints. Lower is better.
    """
    if len(trajectory) < 4:
        return 0.0

    arr = np.stack(trajectory)  # (T, DOF)
    dt = 1.0  # assume unit time steps (normalised for comparison)

    vel = np.diff(arr, n=1, axis=0) / dt
    acc = np.diff(vel,  n=1, axis=0) / dt
    jerk = np.diff(acc, n=1, axis=0) / dt

    return float(np.mean(np.abs(jerk)))


def trajectory_path_length(trajectory: list[np.ndarray]) -> float:
    """Sum of Euclidean distances between consecutive joint-space positions."""
    if len(trajectory) < 2:
        return 0.0
    arr = np.stack(trajectory)
    deltas = np.diff(arr, axis=0)
    return float(np.sum(np.linalg.norm(deltas, axis=1)))
