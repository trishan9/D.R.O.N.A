"""
Simulation evaluation for D.R.O.N.A. gesture policies - Research Contribution C3.

Rolls a policy out in the simulation environment and scores it on:

  - success rate   : did the gesture reach its apex pose AND return to rest?
  - gesture quality : mean jerk (smoothness) + joint-space path length
  - apex error      : closest approach to the intended apex pose

This is the harness behind the C3 claim ("ACT-trained policy is smoother than
the keyframe baseline"). It is policy- and backend-agnostic: any `BasePolicy`
(Keyframe / ACT / Diffusion / SmolVLA) and any `BaseEnv` (Stub / MuJoCo) plug in,
so the same numbers are produced regardless of what's installed.

Everything here is pure given a policy + env, so it runs offline in CI with the
KeyframePolicy + StubEnv.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field

import numpy as np
from loguru import logger

from drona.interaction.act_policy import (
    BasePolicy,
    KeyframePolicy,
    trajectory_path_length,
    trajectory_smoothness,
)
from drona.interaction.demonstration import GESTURE_KEYFRAMES, REST_POSE
from drona.interaction.mujoco_env import BaseEnv, StubEnv

# Tolerances in joint-space L2 distance (radians). Lenient because the stub env
# is a first-order tracker (obs lags the commanded target).
APEX_TOL = 0.35
REST_TOL = 0.30
IDLE_STILLNESS_TOL = 0.15


def gesture_apex_pose(gesture_label: str) -> np.ndarray:
    """Return the keyframe pose furthest from rest - the gesture's 'apex'."""
    keyframes = GESTURE_KEYFRAMES[gesture_label]
    best = np.array(keyframes[0][0], dtype=np.float32)
    best_dist = -1.0
    for pose_list, _hold in keyframes:
        pose = np.array(pose_list, dtype=np.float32)
        d = float(np.linalg.norm(pose - REST_POSE))
        if d > best_dist:
            best_dist, best = d, pose
    return best


def rollout(policy: BasePolicy, env: BaseEnv, n_steps: int) -> list[np.ndarray]:
    """Reset policy + env and roll out for n_steps, returning observed poses."""
    policy.reset()
    obs = env.reset()
    positions = [np.asarray(obs, dtype=np.float32)]
    for _ in range(n_steps):
        action = policy.select_action({"observation.state": obs})
        obs, _done = env.step(action)
        positions.append(np.asarray(obs, dtype=np.float32))
    return positions


@dataclass
class GestureMetrics:
    gesture: str
    policy: str
    success: bool
    reached_apex: bool
    returned_to_rest: bool
    apex_error: float
    final_rest_error: float
    jerk: float
    path_length: float
    n_steps: int


def evaluate_gesture(
    policy: BasePolicy,
    env: BaseEnv,
    gesture_label: str,
    n_steps: int = 120,
) -> GestureMetrics:
    """Roll out one gesture and compute success + quality metrics."""
    positions = rollout(policy, env, n_steps)
    arr = np.stack(positions)

    if gesture_label == "idle":
        # Success = the arm stays near rest the whole time.
        max_dev = float(np.max(np.linalg.norm(arr - REST_POSE, axis=1)))
        reached_apex = True
        returned_to_rest = max_dev < IDLE_STILLNESS_TOL
        apex_error = max_dev
        final_rest_error = float(np.linalg.norm(arr[-1] - REST_POSE))
    else:
        apex = gesture_apex_pose(gesture_label)
        apex_error = float(np.min(np.linalg.norm(arr - apex, axis=1)))
        final_rest_error = float(np.linalg.norm(arr[-1] - REST_POSE))
        reached_apex = apex_error < APEX_TOL
        returned_to_rest = final_rest_error < REST_TOL

    success = reached_apex and returned_to_rest
    return GestureMetrics(
        gesture=gesture_label,
        policy=policy.name,
        success=success,
        reached_apex=reached_apex,
        returned_to_rest=returned_to_rest,
        apex_error=round(apex_error, 4),
        final_rest_error=round(final_rest_error, 4),
        jerk=round(trajectory_smoothness(positions), 6),
        path_length=round(trajectory_path_length(positions), 4),
        n_steps=n_steps,
    )


@dataclass
class SimEvalReport:
    policy_label: str
    per_gesture: dict[str, dict] = field(default_factory=dict)
    success_rate: float = 0.0
    mean_jerk: float = 0.0
    mean_path_length: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_policy(
    policy_factory: Callable[[str], BasePolicy],
    gestures: list[str] | None = None,
    env_factory: Callable[[], BaseEnv] | None = None,
    n_steps: int = 120,
) -> SimEvalReport:
    """Evaluate a policy across gestures.

    Args:
        policy_factory: gesture_label -> BasePolicy (e.g. KeyframePolicy).
        gestures: which gestures to evaluate (default: all).
        env_factory: () -> BaseEnv (default: StubEnv).
        n_steps: rollout length.
    """
    gestures = gestures or list(GESTURE_KEYFRAMES.keys())
    env_factory = env_factory or (lambda: StubEnv())

    metrics: list[GestureMetrics] = []
    label = ""
    for g in gestures:
        policy = policy_factory(g)
        label = label or policy.name.split("(")[0]
        m = evaluate_gesture(policy, env_factory(), g, n_steps=n_steps)
        metrics.append(m)

    n = len(metrics)
    report = SimEvalReport(
        policy_label=label or "policy",
        per_gesture={m.gesture: asdict(m) for m in metrics},
        success_rate=round(sum(m.success for m in metrics) / n, 4) if n else 0.0,
        mean_jerk=round(sum(m.jerk for m in metrics) / n, 6) if n else 0.0,
        mean_path_length=round(sum(m.path_length for m in metrics) / n, 4) if n else 0.0,
    )
    logger.info(
        f"Sim eval [{report.policy_label}]: success={report.success_rate:.0%}, "
        f"mean_jerk={report.mean_jerk:.4f}, mean_path={report.mean_path_length:.3f}"
    )
    return report


def evaluate_keyframe_baseline(
    gestures: list[str] | None = None, n_steps: int = 120
) -> SimEvalReport:
    """Convenience: evaluate the always-available keyframe baseline."""
    return evaluate_policy(lambda g: KeyframePolicy(g), gestures, n_steps=n_steps)


def compare_policies(
    base_factory: Callable[[str], BasePolicy],
    other_factory: Callable[[str], BasePolicy],
    gestures: list[str] | None = None,
    env_factory: Callable[[], BaseEnv] | None = None,
    n_steps: int = 120,
) -> dict:
    """Compare two policies (e.g. keyframe vs ACT) and report deltas.

    Lower jerk = smoother (the C3 win condition).
    """
    base = evaluate_policy(base_factory, gestures, env_factory, n_steps)
    other = evaluate_policy(other_factory, gestures, env_factory, n_steps)
    return {
        "base": base.to_dict(),
        "other": other.to_dict(),
        "delta": {
            "success_rate": round(other.success_rate - base.success_rate, 4),
            "mean_jerk": round(other.mean_jerk - base.mean_jerk, 6),
            "mean_path_length": round(other.mean_path_length - base.mean_path_length, 4),
        },
        "smoother": other.mean_jerk < base.mean_jerk,
    }
