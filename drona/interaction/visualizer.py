"""
Real-time 6-DOF arm visualizer for D.R.O.N.A.

Two backends (selected automatically):
  MuJoCoVisualizer  - renders the embedded MuJoCo model with a viewer window
  MatplotlibVisualizer - headless-compatible ASCII/matplotlib 3D stick figure

Both share BaseVisualizer so gesture_dispatcher and run_simulation.py need no
backend-specific code.

Usage:
    from drona.interaction.visualizer import make_visualizer
    with make_visualizer() as viz:
        for q in trajectory:
            viz.update(q)
            time.sleep(0.05)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from loguru import logger

from drona.interaction.demonstration import (
    DOF,
    REST_POSE,
)

# ── Base ──────────────────────────────────────────────────────────────────────

class BaseVisualizer(ABC):
    """Shared interface for arm visualizers."""

    @abstractmethod
    def open(self) -> None:
        """Open the visualizer window / figure."""

    @abstractmethod
    def update(self, q: np.ndarray, label: str = "") -> None:
        """Push new joint positions to the display.

        Args:
            q: Joint angles in radians, shape (DOF,).
            label: Optional text annotation (gesture name, policy, etc.).
        """

    @abstractmethod
    def close(self) -> None:
        """Close the window and release resources."""

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()


# ── MuJoCo visualizer ─────────────────────────────────────────────────────────

class MuJoCoVisualizer(BaseVisualizer):
    """Interactive 3D viewer backed by MuJoCo's built-in renderer.

    Requires mujoco >= 3.0 with a display (works in X11 / WSLg).
    Falls back gracefully to MatplotlibVisualizer if unavailable.
    """

    def __init__(self, dt: float = 0.05) -> None:
        self._dt = dt
        self._model: Any = None
        self._data: Any = None
        self._viewer: Any = None

    def open(self) -> None:
        try:
            import mujoco
            import mujoco.viewer

            from drona.interaction.mujoco_env import _MUJOCO_XML
        except ImportError as exc:
            raise RuntimeError(
                "MuJoCo not installed. Run: pip install mujoco\n"
                "Or use MatplotlibVisualizer."
            ) from exc

        self._model = mujoco.MjModel.from_xml_string(_MUJOCO_XML)
        self._data = mujoco.MjData(self._model)
        self._viewer = mujoco.viewer.launch_passive(self._model, self._data)
        logger.info("MuJoCo visualizer opened.")

    def update(self, q: np.ndarray, label: str = "") -> None:
        if self._data is None or self._viewer is None:
            return
        import mujoco
        self._data.qpos[:DOF] = q[:DOF]
        mujoco.mj_forward(self._model, self._data)
        self._viewer.sync()

    def close(self) -> None:
        if self._viewer is not None:
            self._viewer.close()
            self._viewer = None
        logger.info("MuJoCo visualizer closed.")


# ── Matplotlib visualizer ──────────────────────────────────────────────────────

# Forward kinematic constants for a simplified 4-link stick figure
# Link lengths in metres (approximate for a table-top manipulator)
_LINK_LENGTHS = [0.0, 0.10, 0.13, 0.12, 0.08, 0.03]  # base, shoulder, elbow, wrist, roll, grip


def _forward_kinematics(q: np.ndarray) -> list[np.ndarray]:
    """Compute 3D joint positions via simple planar FK (for visualization only).

    Returns list of (x, y, z) positions for each joint (7 points: base + 6 joints).
    This is NOT a precision kinematic model - it is only for visualization.
    """
    import math
    positions = [np.array([0.0, 0.0, 0.0])]

    # Cumulative rotation angles (greatly simplified: ignore wrist roll)
    yaw = q[0]       # j0 base yaw
    sh = q[1]        # j1 shoulder pitch
    el = q[2]        # j2 elbow pitch
    wp = q[3]        # j3 wrist pitch

    # Base → shoulder
    x0 = positions[-1]
    sh_pos = x0 + np.array([
        _LINK_LENGTHS[1] * math.cos(yaw) * math.cos(sh),
        _LINK_LENGTHS[1] * math.sin(yaw) * math.cos(sh),
        _LINK_LENGTHS[1] * math.sin(sh),
    ])
    positions.append(sh_pos)

    # Shoulder → elbow
    el_angle = sh + el
    el_pos = sh_pos + np.array([
        _LINK_LENGTHS[2] * math.cos(yaw) * math.cos(el_angle),
        _LINK_LENGTHS[2] * math.sin(yaw) * math.cos(el_angle),
        _LINK_LENGTHS[2] * math.sin(el_angle),
    ])
    positions.append(el_pos)

    # Elbow → wrist
    w_angle = el_angle + wp
    w_pos = el_pos + np.array([
        _LINK_LENGTHS[3] * math.cos(yaw) * math.cos(w_angle),
        _LINK_LENGTHS[3] * math.sin(yaw) * math.cos(w_angle),
        _LINK_LENGTHS[3] * math.sin(w_angle),
    ])
    positions.append(w_pos)

    # Wrist → tip
    tip = w_pos + np.array([
        _LINK_LENGTHS[4] * math.cos(yaw) * math.cos(w_angle),
        _LINK_LENGTHS[4] * math.sin(yaw) * math.cos(w_angle),
        _LINK_LENGTHS[4] * math.sin(w_angle),
    ])
    positions.append(tip)

    return positions


class MatplotlibVisualizer(BaseVisualizer):
    """Non-interactive matplotlib 3D stick figure. Saves frames to output_dir."""

    def __init__(self, output_dir: str | None = None, show: bool = True) -> None:
        self._output_dir = output_dir
        self._show = show
        self._fig = None
        self._ax = None
        self._frame = 0
        self._line = None
        self._dots = None
        self._text = None

    def open(self) -> None:
        import matplotlib
        if not self._show:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

        self._fig = plt.figure(figsize=(6, 6))
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._ax.set_xlim(-0.4, 0.4)
        self._ax.set_ylim(-0.4, 0.4)
        self._ax.set_zlim(0.0, 0.5)
        self._ax.set_xlabel("X")
        self._ax.set_ylabel("Y")
        self._ax.set_zlabel("Z")
        self._ax.set_title("D.R.O.N.A. Arm")

        pts = _forward_kinematics(REST_POSE)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        self._line, = self._ax.plot(xs, ys, zs, "b-o", linewidth=3, markersize=6)
        self._text = self._ax.text2D(0.05, 0.95, "", transform=self._ax.transAxes)

        if self._show:
            plt.ion()
            plt.show()

        if self._output_dir:
            import os

            os.makedirs(self._output_dir, exist_ok=True)
        logger.info("Matplotlib visualizer opened.")

    def update(self, q: np.ndarray, label: str = "") -> None:
        pts = _forward_kinematics(q)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        self._line.set_data_3d(xs, ys, zs)
        self._text.set_text(label)

        if self._show:
            self._fig.canvas.draw()
            self._fig.canvas.flush_events()

        if self._output_dir:
            self._fig.savefig(f"{self._output_dir}/frame_{self._frame:05d}.png", dpi=72)
        self._frame += 1

    def close(self) -> None:
        import matplotlib.pyplot as plt
        if self._fig:
            plt.close(self._fig)
        logger.info(f"Matplotlib visualizer closed ({self._frame} frames rendered).")


# ── Factory ───────────────────────────────────────────────────────────────────

def make_visualizer(
    prefer_mujoco: bool = True,
    output_dir: str | None = None,
    show: bool = True,
) -> BaseVisualizer:
    """Return the best available visualizer.

    Args:
        prefer_mujoco: Try MuJoCo first; fall back to Matplotlib.
        output_dir: If set, save PNG frames here (Matplotlib only).
        show: Whether to display a live window (set False for headless rendering).
    """
    if prefer_mujoco:
        try:
            viz = MuJoCoVisualizer()
            viz.open()
            return viz
        except Exception as exc:
            logger.warning(f"MuJoCo visualizer unavailable ({exc}). Using Matplotlib.")

    viz = MatplotlibVisualizer(output_dir=output_dir, show=show)
    viz.open()
    return viz
