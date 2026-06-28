"""
MuJoCo simulation environment for D.R.O.N.A. robot gestures.

Phase 1 strategy:
  We provide two execution backends for the same interface:

  1. StubEnv (always available) - tracks joint state as a pure Python/NumPy
     state machine. No physics. Useful for unit tests, CI, and machines without
     MuJoCo. The ACT policy trains against recorded trajectories, so physics
     fidelity during inference is less important than interface consistency.

  2. MuJoCoEnv (optional) - wraps a minimal MuJoCo XML model of a 6-DOF arm.
     Loaded only when `mujoco` is importable. For WS3 evaluation, this is the
     target environment. The XML model is embedded as a string to avoid asset
     file dependencies.

Both backends implement the same `BaseEnv` protocol:
    reset() → obs (ndarray, shape DOF)
    step(action) → (obs, done)
    close() → None

The environment also records a trajectory log (list of obs/action pairs) during
each episode, which the gesture dispatcher uses for `InteractionActionResult`
timing and the evaluation harness uses for ACT policy assessment.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from loguru import logger

from drona.interaction.demonstration import (
    DOF,
    REST_POSE,
    DemonstrationEpisode,
    clamp_joints,
)

# ── MuJoCo XML model (embedded) ───────────────────────────────────────────────
#
# Minimal 6-DOF arm for gesture simulation. Masses and inertia are approximate
# for a SO-100-class manipulator (~500g per link). The goal is behavioural
# fidelity for gesture timing - not kinematic accuracy.

_MUJOCO_XML = """
<mujoco model="drona_arm">
  <option timestep="0.01" gravity="0 0 -9.81"/>
  <worldbody>
    <light name="top" pos="0 0 2" dir="0 0 -1"/>
    <geom name="floor" type="plane" size="1 1 0.1" rgba="0.8 0.8 0.8 1"/>
    <!-- Base -->
    <body name="base" pos="0 0 0.3">
      <joint name="j0_base_yaw" type="hinge" axis="0 0 1"
             range="-3.14 3.14" damping="2.0"/>
      <geom type="cylinder" size="0.04 0.05" rgba="0.3 0.3 0.8 1" mass="0.5"/>
      <!-- Shoulder -->
      <body name="upper_arm" pos="0 0 0.05">
        <joint name="j1_shoulder" type="hinge" axis="0 1 0"
               range="-1.57 1.57" damping="1.5"/>
        <geom type="capsule" size="0.025" fromto="0 0 0 0 0 0.15"
              rgba="0.3 0.8 0.3 1" mass="0.3"/>
        <!-- Elbow -->
        <body name="forearm" pos="0 0 0.15">
          <joint name="j2_elbow" type="hinge" axis="0 1 0"
                 range="-3.14 3.14" damping="1.0"/>
          <geom type="capsule" size="0.02" fromto="0 0 0 0 0 0.12"
                rgba="0.8 0.3 0.3 1" mass="0.2"/>
          <!-- Wrist pitch -->
          <body name="wrist_pitch_body" pos="0 0 0.12">
            <joint name="j3_wrist_pitch" type="hinge" axis="0 1 0"
                   range="-1.57 1.57" damping="0.5"/>
            <geom type="capsule" size="0.015" fromto="0 0 0 0 0 0.07"
                  rgba="0.8 0.8 0.3 1" mass="0.1"/>
            <!-- Wrist roll -->
            <body name="wrist_roll_body" pos="0 0 0.07">
              <joint name="j4_wrist_roll" type="hinge" axis="0 0 1"
                     range="-3.14 3.14" damping="0.3"/>
              <geom type="capsule" size="0.012" fromto="0 0 0 0 0 0.04"
                    rgba="0.5 0.5 0.9 1" mass="0.05"/>
              <!-- Gripper -->
              <body name="gripper_body" pos="0 0 0.04">
                <joint name="j5_gripper" type="slide" axis="1 0 0"
                       range="0 0.04" damping="0.1"/>
                <geom type="box" size="0.01 0.01 0.01"
                      rgba="0.9 0.5 0.5 1" mass="0.02"/>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
    <position name="act_j0" joint="j0_base_yaw"   kp="200"/>
    <position name="act_j1" joint="j1_shoulder"    kp="200"/>
    <position name="act_j2" joint="j2_elbow"       kp="150"/>
    <position name="act_j3" joint="j3_wrist_pitch" kp="100"/>
    <position name="act_j4" joint="j4_wrist_roll"  kp="80"/>
    <position name="act_j5" joint="j5_gripper"     kp="50"/>
  </actuator>
</mujoco>
"""


# ── Base protocol ─────────────────────────────────────────────────────────────

class BaseEnv(ABC):
    """Shared interface for both stub and MuJoCo backends."""

    @abstractmethod
    def reset(self) -> np.ndarray:
        """Reset to rest pose. Returns initial observation (joint positions)."""

    @abstractmethod
    def step(self, action: np.ndarray) -> tuple[np.ndarray, bool]:
        """Apply joint position command. Returns (obs, done)."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""

    @property
    @abstractmethod
    def trajectory(self) -> list[dict[str, Any]]:
        """Obs/action log for this episode."""


# ── Stub backend (always available) ───────────────────────────────────────────

class StubEnv(BaseEnv):
    """Pure NumPy environment - no physics, no external dependencies.

    Joint state evolves via first-order exponential tracking:
        q(t+dt) = q(t) + gain * (action - q(t))
    This produces plausible, smooth trajectories without MuJoCo.
    """

    def __init__(self, dt: float = 0.05, tracking_gain: float = 0.25) -> None:
        self._dt = dt
        self._gain = tracking_gain
        self._q = REST_POSE.copy()
        self._step_count = 0
        self._t = 0.0
        self._trajectory: list[dict[str, Any]] = []

    def reset(self) -> np.ndarray:
        self._q = REST_POSE.copy()
        self._step_count = 0
        self._t = 0.0
        self._trajectory = []
        return self._q.copy()

    def step(self, action: np.ndarray) -> tuple[np.ndarray, bool]:
        action = clamp_joints(np.asarray(action, dtype=np.float32))
        # First-order tracking
        self._q = self._q + self._gain * (action - self._q)
        self._q = clamp_joints(self._q)
        self._step_count += 1
        self._t += self._dt
        self._trajectory.append({
            "t": self._t,
            "obs": self._q.tolist(),
            "action": action.tolist(),
        })
        return self._q.copy(), False  # stub never terminates on its own

    def close(self) -> None:
        pass

    @property
    def trajectory(self) -> list[dict[str, Any]]:
        return self._trajectory


# ── MuJoCo backend (optional) ─────────────────────────────────────────────────

class MuJoCoEnv(BaseEnv):
    """MuJoCo-backed environment. Loaded lazily; falls back to StubEnv.

    Uses position actuators (PD control) which match what ACT outputs -
    joint position targets, not torques.
    """

    def __init__(self, dt: float = 0.01) -> None:
        import mujoco  # type: ignore[import]
        self._mj = mujoco
        self._model = mujoco.MjModel.from_xml_string(_MUJOCO_XML)
        self._data = mujoco.MjData(self._model)
        self._model.opt.timestep = dt
        self._dt = dt
        self._steps_per_action = max(1, int(0.05 / dt))  # 50ms control period
        self._trajectory: list[dict[str, Any]] = []
        self._t = 0.0
        logger.info("MuJoCo environment initialised")

    def reset(self) -> np.ndarray:
        self._mj.mj_resetData(self._model, self._data)
        # Set rest pose
        for i, q in enumerate(REST_POSE[:DOF - 1]):  # j0-j4 are hinge joints
            self._data.qpos[i] = q
        self._mj.mj_forward(self._model, self._data)
        self._trajectory = []
        self._t = 0.0
        return self._get_obs()

    def step(self, action: np.ndarray) -> tuple[np.ndarray, bool]:
        action = clamp_joints(np.asarray(action, dtype=np.float32))
        # Set actuator targets
        self._data.ctrl[:] = action
        # Step physics
        for _ in range(self._steps_per_action):
            self._mj.mj_step(self._model, self._data)
        self._t += self._steps_per_action * self._dt
        obs = self._get_obs()
        self._trajectory.append({
            "t": self._t,
            "obs": obs.tolist(),
            "action": action.tolist(),
        })
        return obs, False

    def _get_obs(self) -> np.ndarray:
        return np.array(self._data.qpos[:DOF], dtype=np.float32)

    def close(self) -> None:
        pass  # MuJoCo data is GC'd

    @property
    def trajectory(self) -> list[dict[str, Any]]:
        return self._trajectory


# ── Factory ────────────────────────────────────────────────────────────────────

def make_env(prefer_mujoco: bool = True, dt: float = 0.05) -> BaseEnv:
    """Create an environment, preferring MuJoCo if available.

    Args:
        prefer_mujoco: Try MuJoCo first; fall back to StubEnv if unavailable.
        dt: Control timestep in seconds.

    Returns:
        A BaseEnv instance (StubEnv or MuJoCoEnv).
    """
    if prefer_mujoco:
        try:
            env = MuJoCoEnv(dt=dt)
            logger.info("Using MuJoCo physics backend")
            return env
        except ImportError:
            logger.info("MuJoCo not available - using StubEnv (no physics)")
        except Exception as exc:
            logger.warning(f"MuJoCo init failed ({exc}) - using StubEnv")
    return StubEnv(dt=dt)


# ── Trajectory execution helper ────────────────────────────────────────────────

def execute_trajectory(
    env: BaseEnv,
    episode: DemonstrationEpisode,
    realtime: bool = False,
) -> list[dict[str, Any]]:
    """Execute a recorded demonstration episode in the environment.

    Args:
        env: A BaseEnv instance (must already be reset).
        episode: The episode whose actions to replay.
        realtime: If True, sleep to match real time (for visualisation).

    Returns:
        The environment's trajectory log.
    """
    dt = 0.05  # assume 50ms control period
    for frame in episode.frames:
        t0 = time.monotonic()
        env.step(frame.action)
        if realtime:
            elapsed = time.monotonic() - t0
            sleep_time = dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    return env.trajectory
