"""Deployment-format gesture policies - ONNX inference without torch.

``scripts/export_policies.py`` exports every trained BC checkpoint to ONNX
(and TorchScript) next to its torch weights:

    <checkpoint_dir>/<gesture>/model.onnx            # opset 17, batch-dynamic
    <checkpoint_dir>/<gesture>/model.torchscript.pt  # torch.jit alternative
    <checkpoint_dir>/<gesture>/config.json           # shared with BCGesturePolicy

``OnnxBCPolicy`` runs the ONNX file through onnxruntime with the exact same
phase-conditioning semantics as :class:`drona.interaction.bc_policy.BCGesturePolicy`,
so the two are interchangeable behind :class:`BasePolicy`. This is the
deployment path: the ROS2 ``policy_node`` (via ``PolicyRouter``) prefers the
ONNX artifact when onnxruntime is available, which removes torch from the
robot's runtime dependencies entirely.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from drona.interaction.act_policy import BasePolicy
from drona.interaction.bc_policy import DEFAULT_BC_DIR
from drona.interaction.demonstration import DOF, REST_POSE

ONNX_FILENAME = "model.onnx"
TORCHSCRIPT_FILENAME = "model.torchscript.pt"


class OnnxBCPolicy(BasePolicy):
    """Phase-conditioned BC policy served from an exported ONNX graph.

    Mirrors ``BCGesturePolicy`` exactly (same config.json, same phase logic);
    only the inference backend differs. Construction raises ``RuntimeError``
    if onnxruntime or the artifact is missing - use :func:`onnx_exists` to
    gate selection, matching the ``checkpoint_exists`` idiom.
    """

    def __init__(
        self,
        gesture_label: str,
        checkpoint_dir: str | Path = DEFAULT_BC_DIR,
        providers: list[str] | None = None,
    ) -> None:
        self._gesture = gesture_label
        self._step = 0
        self._dir = Path(checkpoint_dir) / gesture_label

        onnx_path = self._dir / ONNX_FILENAME
        cfg_path = self._dir / "config.json"
        if not (onnx_path.exists() and cfg_path.exists()):
            raise RuntimeError(f"No ONNX export at {onnx_path}")

        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "onnxruntime is required for OnnxBCPolicy: pip install onnxruntime"
            ) from exc

        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        self._horizon = int(cfg.get("horizon", 60))
        self._input_dim = int(cfg.get("input_dim", 1))

        self._session = ort.InferenceSession(
            str(onnx_path), providers=providers or ["CPUExecutionProvider"]
        )
        self._input_name = self._session.get_inputs()[0].name

    # ── BasePolicy interface ─────────────────────────────────────────────────
    def reset(self) -> None:
        self._step = 0

    def select_action(self, obs_dict: dict[str, Any]) -> np.ndarray:
        obs = np.asarray(
            obs_dict.get("observation.state", REST_POSE), dtype=np.float32
        ).reshape(-1)[:DOF]

        phase = min(self._step / max(self._horizon - 1, 1), 1.0)
        x = (np.array([phase], dtype=np.float32) if self._input_dim == 1
             else np.concatenate([obs, [phase]]).astype(np.float32))
        (action,) = self._session.run(None, {self._input_name: x[None, :]})
        self._step += 1
        return np.asarray(action, dtype=np.float32).reshape(-1)[:DOF]

    @property
    def is_complete(self) -> bool:
        return self._step >= self._horizon

    @property
    def name(self) -> str:
        return f"OnnxBCPolicy({self._gesture})"


def onnx_exists(gesture_label: str, checkpoint_dir: str | Path = DEFAULT_BC_DIR) -> bool:
    """True if a deployable ONNX export exists for the gesture."""
    d = Path(checkpoint_dir) / gesture_label
    return (d / ONNX_FILENAME).exists() and (d / "config.json").exists()
