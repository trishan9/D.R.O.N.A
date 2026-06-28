"""Behavior-cloning gesture policy - Research Contribution C3 (CPU baseline).

A lightweight, **CPU-trainable** imitation-learning policy that learns gesture
trajectories from the keyframe demonstration dataset. It is the local baseline
for the demonstration-learned interaction claim: it needs no GPU and no LeRobot,
trains in seconds on this hardware, and plugs into the same ``BasePolicy``
interface and ``sim_eval`` harness as the production ACT/Diffusion policies
(which train on Colab T4 via notebooks 07/08).

Design - phase-conditioned behavior cloning:
    input  = [ joint_state (DOF), gesture_phase (1) ]   (closed-loop on state)
    output = [ target joint positions (DOF) ]

Markovian state→action BC is ambiguous on cyclic gestures (the rest pose maps to
both "move out" at t=0 and "stay" at t=end). Conditioning on a normalised gesture
phase resolves that ambiguity, so the learned policy reproduces the full
out-and-back trajectory. The policy tracks its own phase internally (like the
keyframe policy tracks its step), so ``select_action`` keeps the ``BasePolicy``
signature unchanged.

Checkpoint layout (HuggingFace-ish, one dir per gesture):
    <checkpoint_dir>/<gesture>/pytorch_model.bin   # torch state_dict
    <checkpoint_dir>/<gesture>/config.json         # {hidden, horizon, dof, ...}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from drona.interaction.act_policy import BasePolicy
from drona.interaction.demonstration import DOF, REST_POSE

DEFAULT_BC_DIR = "data/checkpoints/bc"
DEFAULT_HIDDEN = 128


def _build_mlp(input_dim: int, hidden: int, output_dim: int):
    """Construct the small feed-forward net used by the BC policy."""
    import torch.nn as nn

    return nn.Sequential(
        nn.Linear(input_dim, hidden),
        nn.ReLU(),
        nn.Linear(hidden, hidden),
        nn.ReLU(),
        nn.Linear(hidden, output_dim),
    )


class BCGesturePolicy(BasePolicy):
    """A trained phase-conditioned behavior-cloning policy for one gesture.

    Falls back to a no-op (holds rest) if the checkpoint is missing, so callers
    can always construct it; use :func:`checkpoint_exists` to gate selection.
    """

    def __init__(
        self,
        gesture_label: str,
        checkpoint_dir: str | Path = DEFAULT_BC_DIR,
        device: str = "cpu",
    ) -> None:
        self._gesture = gesture_label
        self._device = device
        self._step = 0
        self._horizon = 60
        self._input_dim = 1
        self._model = None
        self._dir = Path(checkpoint_dir) / gesture_label
        self._load()

    # ── Loading ─────────────────────────────────────────────────────────────
    def _load(self) -> None:
        cfg_path = self._dir / "config.json"
        weights_path = self._dir / "pytorch_model.bin"
        if not (cfg_path.exists() and weights_path.exists()):
            return
        import torch

        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        self._horizon = int(cfg.get("horizon", 60))
        hidden = int(cfg.get("hidden", DEFAULT_HIDDEN))
        dof = int(cfg.get("dof", DOF))
        # input_dim = 1 → phase-only (open-loop movement primitive);
        # input_dim = dof+1 → closed-loop (joint state + phase).
        self._input_dim = int(cfg.get("input_dim", 1))
        model = _build_mlp(self._input_dim, hidden, dof)
        model.load_state_dict(torch.load(weights_path, map_location=self._device))
        model.eval()
        self._model = model.to(self._device)

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    # ── BasePolicy interface ─────────────────────────────────────────────────
    def reset(self) -> None:
        self._step = 0

    def select_action(self, obs_dict: dict[str, Any]) -> np.ndarray:
        obs = np.asarray(
            obs_dict.get("observation.state", REST_POSE), dtype=np.float32
        ).reshape(-1)[:DOF]

        if self._model is None:
            # Untrained fallback: hold rest pose.
            return REST_POSE.astype(np.float32).copy()

        import torch

        phase = min(self._step / max(self._horizon - 1, 1), 1.0)
        # Open-loop primitive replays the demonstrated trajectory as a function of
        # gesture phase, so it reaches the apex regardless of env tracking lag.
        # Closed-loop mode also conditions on the current joint state.
        x = (np.array([phase], dtype=np.float32) if self._input_dim == 1
             else np.concatenate([obs, [phase]]).astype(np.float32))
        with torch.no_grad():
            t = torch.from_numpy(x).unsqueeze(0).to(self._device)
            action = self._model(t).squeeze(0).cpu().numpy().astype(np.float32)
        self._step += 1
        return action

    @property
    def is_complete(self) -> bool:
        return self._step >= self._horizon

    @property
    def name(self) -> str:
        tag = "trained" if self._model is not None else "untrained"
        return f"BCGesturePolicy({self._gesture}:{tag})"


def checkpoint_exists(gesture_label: str, checkpoint_dir: str | Path = DEFAULT_BC_DIR) -> bool:
    """True if a trained BC checkpoint exists for the gesture."""
    d = Path(checkpoint_dir) / gesture_label
    return (d / "config.json").exists() and (d / "pytorch_model.bin").exists()
