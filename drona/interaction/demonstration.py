"""
Demonstration data layer for D.R.O.N.A. - Research Contribution C3.

Defines the schema for recording, storing, and loading robot gesture
demonstrations used to train the ACT (Action Chunking with Transformers)
imitation learning policy.

Data model (mirrors LeRobot HuggingFace dataset convention):
  - DemonstrationFrame: one timestep (observation + action + metadata)
  - DemonstrationEpisode: ordered sequence of frames for one gesture execution
  - DemonstrationDataset: collection of episodes, serializable to disk

Joint space:
  Six-DOF arm [j0..j5] in radians, matching a SO-100 or similar open-source
  manipulator. All angles clamped to [-π, π]. The same joint convention is used
  in both the simulation environment and ACT policy I/O so no remapping occurs.

  j0 - base rotation (yaw)
  j1 - shoulder pitch
  j2 - elbow pitch
  j3 - wrist pitch
  j4 - wrist roll
  j5 - gripper (0 = open, 1 = closed)

Storage:
  Primary: HuggingFace datasets (parquet) when `datasets` package is available.
  Fallback: JSON-lines file (.jsonl). The fallback is always used in Phase 1
  tests; the HuggingFace path is exercised in WS3 data collection scripts.

Why imitation learning instead of hand-coded kinematics?
  Gesture quality in embodied advising affects student engagement. IK-solved
  motions look robotic and uncanny; demonstration-trained motions inherit the
  demonstrator's natural timing and trajectory curvature. This is the core
  empirical claim of C3.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

# ── Joint space constants ─────────────────────────────────────────────────────

DOF = 6  # degrees of freedom
JOINT_NAMES = ["j0_base_yaw", "j1_shoulder", "j2_elbow", "j3_wrist_pitch", "j4_wrist_roll", "j5_gripper"]
JOINT_LIMITS_LOW  = np.array([-math.pi, -math.pi/2, -math.pi, -math.pi/2, -math.pi, 0.0])
JOINT_LIMITS_HIGH = np.array([ math.pi,  math.pi/2,  math.pi,  math.pi/2,  math.pi, 1.0])

# Rest pose - arm hanging naturally at side
REST_POSE = np.array([0.0, -0.3, 0.5, -0.2, 0.0, 0.0])


def clamp_joints(q: np.ndarray) -> np.ndarray:
    """Clamp joint angles to hardware limits."""
    return np.clip(q, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)


# ── Pre-programmed gesture keyframes (reference trajectories) ─────────────────
#
# Each gesture is a list of (joint_angles, hold_seconds) keyframes.
# These serve as:
#   1. Fallback execution when no trained ACT model is available (Phase 1)
#   2. Seed demonstrations for ACT training (record these as episodes)
#
# All poses in radians; j5 (gripper) is 0.0 throughout (open).

GESTURE_KEYFRAMES: dict[str, list[tuple[list[float], float]]] = {
    "greet": [
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.3),   # start: rest
        ([0.3,  0.2,  0.2,  0.0,  0.0, 0.0], 0.4),   # raise arm
        ([0.3,  0.2,  0.2,  0.3,  0.4, 0.0], 0.25),  # wave right
        ([0.3,  0.2,  0.2,  0.3, -0.4, 0.0], 0.25),  # wave left
        ([0.3,  0.2,  0.2,  0.3,  0.4, 0.0], 0.25),  # wave right
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.5),   # return to rest
    ],
    "nod": [
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.2),   # rest
        ([0.0, -0.2,  0.4, -0.3,  0.0, 0.0], 0.3),   # dip forward
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.3),   # return
        ([0.0, -0.2,  0.4, -0.3,  0.0, 0.0], 0.3),   # dip again
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.3),   # rest
    ],
    "point": [
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.2),   # rest
        ([0.0,  0.1,  0.0, -0.1,  0.0, 0.0], 0.5),   # extend forward
        ([0.0,  0.1,  0.0, -0.1,  0.0, 0.0], 0.8),   # hold point
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.4),   # return
    ],
    "idle": [
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 1.0),   # rest, stationary
    ],
    "listen": [
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.3),   # rest
        ([0.0, -0.1,  0.3, -0.1,  0.0, 0.0], 0.5),   # slight lean / open
        ([0.0, -0.1,  0.3, -0.1,  0.0, 0.0], 1.0),   # hold open posture
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.4),   # return
    ],
    "farewell": [
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.2),   # rest
        ([0.4,  0.2,  0.2,  0.0,  0.0, 0.0], 0.4),   # raise arm (left biased)
        ([0.4,  0.2,  0.2,  0.2,  0.5, 0.0], 0.3),   # wave right
        ([0.4,  0.2,  0.2,  0.2, -0.5, 0.0], 0.3),   # wave left
        ([0.4,  0.2,  0.2,  0.2,  0.5, 0.0], 0.3),   # wave right
        ([0.0, -0.3,  0.5, -0.2,  0.0, 0.0], 0.5),   # return
    ],
}


# ── Data schema ───────────────────────────────────────────────────────────────

@dataclass
class DemonstrationFrame:
    """One timestep of a recorded demonstration.

    Mirrors a single row in a LeRobot dataset - every field maps directly to a
    HuggingFace datasets column. The order of fields is the serialization order.
    """
    episode_index: int
    frame_index: int
    timestamp: float              # seconds since episode start
    observation_state: np.ndarray  # shape (DOF,) - current joint positions
    action: np.ndarray             # shape (DOF,) - commanded joint positions
    gesture_label: str             # e.g. "greet", "nod"
    is_terminal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_index": self.episode_index,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "observation_state": self.observation_state.tolist(),
            "action": self.action.tolist(),
            "gesture_label": self.gesture_label,
            "is_terminal": self.is_terminal,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DemonstrationFrame:
        return cls(
            episode_index=int(d["episode_index"]),
            frame_index=int(d["frame_index"]),
            timestamp=float(d["timestamp"]),
            observation_state=np.array(d["observation_state"], dtype=np.float32),
            action=np.array(d["action"], dtype=np.float32),
            gesture_label=str(d["gesture_label"]),
            is_terminal=bool(d.get("is_terminal", False)),
        )


@dataclass
class DemonstrationEpisode:
    """One complete gesture demonstration (ordered sequence of frames)."""
    episode_index: int
    gesture_label: str
    frames: list[DemonstrationFrame] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if not self.frames:
            return 0.0
        return self.frames[-1].timestamp - self.frames[0].timestamp

    @property
    def n_frames(self) -> int:
        return len(self.frames)

    def add_frame(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        timestamp: float,
    ) -> None:
        frame = DemonstrationFrame(
            episode_index=self.episode_index,
            frame_index=len(self.frames),
            timestamp=timestamp,
            observation_state=clamp_joints(obs.astype(np.float32)),
            action=clamp_joints(action.astype(np.float32)),
            gesture_label=self.gesture_label,
            is_terminal=False,
        )
        self.frames.append(frame)

    def mark_terminal(self) -> None:
        if self.frames:
            self.frames[-1].is_terminal = True


@dataclass
class DemonstrationDataset:
    """Collection of recorded demonstration episodes.

    Provides save/load in two formats:
      - JSONL (always available, no extra deps) - one JSON object per frame
      - HuggingFace datasets parquet (when `datasets` is installed)
    """
    episodes: list[DemonstrationEpisode] = field(default_factory=list)
    name: str = "drona_gestures"

    @property
    def total_frames(self) -> int:
        return sum(e.n_frames for e in self.episodes)

    @property
    def gesture_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for ep in self.episodes:
            counts[ep.gesture_label] = counts.get(ep.gesture_label, 0) + 1
        return counts

    def add_episode(self, episode: DemonstrationEpisode) -> None:
        self.episodes.append(episode)

    # ── JSONL persistence ──────────────────────────────────────────────────────

    def save_jsonl(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for ep in self.episodes:
                for frame in ep.frames:
                    f.write(json.dumps(frame.to_dict()) + "\n")
        logger.info(
            f"Saved {self.total_frames} frames ({len(self.episodes)} episodes) → {path}"
        )

    @classmethod
    def load_jsonl(cls, path: Path, name: str = "drona_gestures") -> DemonstrationDataset:
        path = Path(path)
        ds = cls(name=name)
        episodes_map: dict[int, DemonstrationEpisode] = {}

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                frame = DemonstrationFrame.from_dict(json.loads(line))
                if frame.episode_index not in episodes_map:
                    episodes_map[frame.episode_index] = DemonstrationEpisode(
                        episode_index=frame.episode_index,
                        gesture_label=frame.gesture_label,
                    )
                episodes_map[frame.episode_index].frames.append(frame)

        ds.episodes = [episodes_map[k] for k in sorted(episodes_map.keys())]
        logger.info(f"Loaded {ds.total_frames} frames from {path}")
        return ds

    # ── HuggingFace datasets persistence ──────────────────────────────────────

    def save_hf(self, path: Path) -> bool:
        """Save as HuggingFace datasets parquet. Returns False if not installed."""
        try:
            from datasets import Dataset  # type: ignore[import]
        except ImportError:
            logger.warning("datasets not installed; falling back to JSONL")
            self.save_jsonl(Path(str(path).replace(".parquet", ".jsonl")))
            return False

        rows = [frame.to_dict() for ep in self.episodes for frame in ep.frames]
        ds = Dataset.from_list(rows)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        ds.save_to_disk(str(path))
        logger.info(f"Saved HuggingFace dataset ({len(rows)} frames) → {path}")
        return True

    @classmethod
    def load_hf(cls, path: Path, name: str = "drona_gestures") -> DemonstrationDataset:
        from datasets import load_from_disk  # type: ignore[import]
        raw = load_from_disk(str(path))
        ds = cls(name=name)
        episodes_map: dict[int, DemonstrationEpisode] = {}
        for row in raw:
            frame = DemonstrationFrame.from_dict(row)
            if frame.episode_index not in episodes_map:
                episodes_map[frame.episode_index] = DemonstrationEpisode(
                    episode_index=frame.episode_index,
                    gesture_label=frame.gesture_label,
                )
            episodes_map[frame.episode_index].frames.append(frame)
        ds.episodes = [episodes_map[k] for k in sorted(episodes_map.keys())]
        return ds


# ── Keyframe trajectory generator ─────────────────────────────────────────────

def interpolate_keyframes(
    keyframes: list[tuple[list[float], float]],
    dt: float = 0.05,
) -> list[tuple[np.ndarray, float]]:
    """Interpolate between keyframes using linear interpolation.

    Args:
        keyframes: List of (joint_angles, hold_seconds) pairs.
        dt: Time step between generated frames (seconds).

    Returns:
        List of (joint_position, timestamp) pairs.
    """
    if not keyframes:
        return []

    frames: list[tuple[np.ndarray, float]] = []
    t = 0.0
    prev_q = np.array(keyframes[0][0], dtype=np.float32)

    for target_list, hold in keyframes:
        target_q = np.array(target_list, dtype=np.float32)
        # Number of interpolation steps for this segment
        n_steps = max(1, int(hold / dt))
        for step in range(n_steps):
            alpha = step / n_steps
            q = prev_q + alpha * (target_q - prev_q)
            frames.append((clamp_joints(q), t))
            t += dt
        prev_q = target_q

    return frames


def record_keyframe_episode(
    gesture_label: str,
    episode_index: int,
    dt: float = 0.05,
) -> DemonstrationEpisode:
    """Generate a demonstration episode from the pre-programmed keyframes.

    This is the seed data for ACT training. Real demonstrations would be
    recorded from teleoperation; these serve as initial references.

    Args:
        gesture_label: One of the keys in GESTURE_KEYFRAMES.
        episode_index: Index for this episode in the dataset.
        dt: Simulation timestep in seconds.

    Returns:
        A DemonstrationEpisode ready to add to a DemonstrationDataset.
    """
    if gesture_label not in GESTURE_KEYFRAMES:
        raise ValueError(
            f"Unknown gesture: {gesture_label!r}. "
            f"Known gestures: {list(GESTURE_KEYFRAMES)}"
        )

    keyframes = GESTURE_KEYFRAMES[gesture_label]
    traj = interpolate_keyframes(keyframes, dt=dt)

    episode = DemonstrationEpisode(
        episode_index=episode_index,
        gesture_label=gesture_label,
        metadata={"source": "keyframe_interpolation", "dt": dt},
    )

    for i, (q, t) in enumerate(traj):
        # observation = current state; action = next target
        next_q = traj[i + 1][0] if i + 1 < len(traj) else q
        episode.add_frame(obs=q, action=next_q, timestamp=t)

    episode.mark_terminal()
    return episode
