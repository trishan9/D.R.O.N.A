"""
Gesture dispatcher for D.R.O.N.A. - bridges advising contracts to robot motion.

Takes an InteractionAction (from the contracts layer) and executes it in the
simulation environment using the appropriate ACT or keyframe policy.

Design:
  The dispatcher is stateless with respect to policy selection - it delegates
  that to PolicyRouter. It owns the environment and controls the execution loop.

  The POINT gesture receives special treatment: `target_direction` in the
  InteractionAction is used to compute the base yaw angle (j0) so the arm
  points in the correct direction relative to the perceived student position.

  Execution is synchronous in Phase 1. In Phase 2, this becomes a ROS2 action
  server with a preemptable goal - the same interface, different transport.

Timing contract:
  The dispatcher runs each gesture to completion (all keyframe frames consumed,
  or `max_steps` hit as a safety limit) then returns InteractionActionResult
  with the actual measured duration. This gives the orchestrator accurate
  timing information for speech synchronisation.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from drona.contracts import (
    GestureType,
    InteractionAction,
    InteractionActionResult,
)
from drona.interaction.act_policy import KeyframePolicy, PolicyRouter
from drona.interaction.demonstration import (
    DOF,
    GESTURE_KEYFRAMES,
    REST_POSE,
    clamp_joints,
    interpolate_keyframes,
)
from drona.interaction.mujoco_env import BaseEnv, StubEnv, make_env

# Safety limit: never run more than 10 seconds of steps at 50ms each
_MAX_STEPS = 200
_DT = 0.05  # control period seconds


def _gesture_label(gesture: GestureType) -> str:
    """Map GestureType enum to GESTURE_KEYFRAMES key."""
    return gesture.value  # enum values match keyframe dict keys exactly


def _adjust_for_target(
    trajectory: list[tuple[np.ndarray, float]],
    target_direction: tuple[float, float, float] | None,
) -> list[tuple[np.ndarray, float]]:
    """Override j0 (base yaw) to point toward target_direction for POINT gesture.

    target_direction is (x, y, z) in robot-frame coordinates. We compute the
    yaw angle from the x/y components and apply it to j0 across all frames.
    """
    if target_direction is None:
        return trajectory
    tx, ty, _ = target_direction
    yaw = float(np.arctan2(ty, tx))
    adjusted: list[tuple[np.ndarray, float]] = []
    for q, t in trajectory:
        q_new = q.copy()
        q_new[0] = np.clip(yaw, -np.pi, np.pi)  # j0
        adjusted.append((clamp_joints(q_new), t))
    return adjusted


class GestureDispatcher:
    """Executes InteractionAction commands in the simulation environment.

    Usage:
        dispatcher = GestureDispatcher()
        result = dispatcher.execute(action)
    """

    def __init__(
        self,
        env: BaseEnv | None = None,
        checkpoint_base_dir: str | Path | None = None,
        prefer_mujoco: bool = False,
        device: str = "cpu",
    ) -> None:
        self._env = env or make_env(prefer_mujoco=prefer_mujoco)
        self._router = PolicyRouter(
            checkpoint_base_dir=checkpoint_base_dir,
            device=device,
        )
        self._env.reset()

    def execute(self, action: InteractionAction) -> InteractionActionResult:
        """Execute a gesture and return the result.

        Args:
            action: An InteractionAction from the advising orchestrator.

        Returns:
            InteractionActionResult with timing and success status.
        """
        label = _gesture_label(action.gesture)
        logger.info(
            f"Executing gesture: {label} "
            f"(action_id={action.action_id})"
        )

        try:
            duration = self._run_gesture(label, action.target_direction)
            logger.info(f"Gesture '{label}' complete in {duration:.2f}s")
            return InteractionActionResult(
                action_id=action.action_id,
                success=True,
                error_message=None,
                actual_duration_seconds=duration,
            )
        except Exception as exc:
            logger.error(f"Gesture '{label}' failed: {exc}")
            return InteractionActionResult(
                action_id=action.action_id,
                success=False,
                error_message=str(exc),
                actual_duration_seconds=None,
            )

    def _run_gesture(
        self,
        label: str,
        target_direction: tuple[float, float, float] | None,
    ) -> float:
        """Internal: run the gesture policy, return wall-clock duration."""
        policy = self._router.get_policy(label)
        policy.reset()
        self._env.reset()

        # For KeyframePolicy: precompute trajectory and apply target adjustment
        if isinstance(policy, KeyframePolicy):
            traj = policy._trajectory
            if target_direction is not None:
                traj = _adjust_for_target(traj, target_direction)
            return self._replay_trajectory(traj)

        # For ACT or other learned policy: step-by-step inference
        return self._rollout_policy(policy, label, target_direction)

    def _replay_trajectory(
        self,
        traj: list[tuple[np.ndarray, float]],
    ) -> float:
        """Replay a pre-computed trajectory in the environment."""
        t_start = time.monotonic()
        obs = self._env.reset()
        for action_vec, _ in traj:
            obs, _ = self._env.step(action_vec)
        return time.monotonic() - t_start

    def _rollout_policy(
        self,
        policy: Any,
        label: str,
        target_direction: tuple[float, float, float] | None,
    ) -> float:
        """Roll out a learned policy step-by-step."""
        t_start = time.monotonic()
        obs = self._env.reset()
        step = 0

        while step < _MAX_STEPS:
            obs_dict = {"observation.state": obs}
            action_vec = policy.select_action(obs_dict)

            # Apply target direction override on j0 if POINT
            if target_direction is not None:
                tx, ty, _ = target_direction
                action_vec = action_vec.copy()
                action_vec[0] = float(np.clip(np.arctan2(ty, tx), -np.pi, np.pi))

            obs, _ = self._env.step(action_vec)
            step += 1

            # KeyframePolicy signals completion via is_complete
            if hasattr(policy, "is_complete") and policy.is_complete:
                break

        return time.monotonic() - t_start

    def get_trajectory(self) -> list[dict[str, Any]]:
        """Return the trajectory log from the most recent execution."""
        return self._env.trajectory

    def close(self) -> None:
        self._env.close()


# ── Convenience factory ────────────────────────────────────────────────────────

def make_dispatcher(
    checkpoint_base_dir: str | Path | None = None,
    prefer_mujoco: bool = False,
) -> GestureDispatcher:
    """Create a GestureDispatcher with default settings."""
    return GestureDispatcher(
        checkpoint_base_dir=checkpoint_base_dir,
        prefer_mujoco=prefer_mujoco,
    )


def make_action(
    gesture: GestureType,
    speech_text: str | None = None,
    target_direction: tuple[float, float, float] | None = None,
    duration_seconds: float | None = None,
) -> InteractionAction:
    """Helper to construct an InteractionAction without boilerplate."""
    return InteractionAction(
        action_id=str(uuid.uuid4()),
        gesture=gesture,
        target_direction=target_direction,
        speech_text=speech_text,
        duration_seconds=duration_seconds,
    )
