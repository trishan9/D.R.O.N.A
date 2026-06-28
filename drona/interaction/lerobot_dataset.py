"""
Convert D.R.O.N.A. demonstrations into the LeRobot dataset format (C3).

`DemonstrationDataset` (drona.interaction.demonstration) is our portable schema.
LeRobot's ACT/Diffusion trainers expect a `LeRobotDataset` (HF v2 layout). This
module is the bridge:

  - ``to_lerobot_records()`` - PURE: flattens episodes into the canonical record
    list (observation.state / action / episode_index / frame_index / timestamp /
    next.done / task). Unit-testable with no LeRobot installed.
  - ``LEROBOT_FEATURES`` - the feature/dtype/shape spec LeRobot needs.
  - ``build_lerobot_dataset()`` - LAZY: creates an on-disk LeRobotDataset via the
    `LeRobotDataset.create` API and writes one frame at a time. Only imported in
    the Colab training notebooks (07/08).

The "task" string is the gesture label, which doubles as the natural-language
instruction for VLA-style policies (SmolVLA), keeping one dataset usable across
ACT, Diffusion Policy, and VLA experiments (Capuano et al. 2025 tutorial).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from drona.interaction.demonstration import DOF, JOINT_NAMES, DemonstrationDataset

# Default control frequency: keyframe interpolation uses dt=0.05s → 20 FPS.
DEFAULT_FPS = 20

# LeRobot v2 feature spec for the 6-DOF arm (no camera in sim gestures).
LEROBOT_FEATURES: dict[str, dict[str, Any]] = {
    "observation.state": {"dtype": "float32", "shape": [DOF], "names": JOINT_NAMES},
    "action": {"dtype": "float32", "shape": [DOF], "names": JOINT_NAMES},
}


def to_lerobot_records(dataset: DemonstrationDataset) -> list[dict[str, Any]]:
    """Flatten a DemonstrationDataset into LeRobot-shaped frame records (pure).

    Returns one dict per frame with the keys LeRobot consumes plus `task`
    (the gesture label, used as the language instruction).
    """
    records: list[dict[str, Any]] = []
    for ep in dataset.episodes:
        n = len(ep.frames)
        for i, frame in enumerate(ep.frames):
            records.append(
                {
                    "observation.state": frame.observation_state.astype("float32").tolist(),
                    "action": frame.action.astype("float32").tolist(),
                    "episode_index": ep.episode_index,
                    "frame_index": i,
                    "timestamp": float(frame.timestamp),
                    "next.done": bool(i == n - 1 or frame.is_terminal),
                    "task": ep.gesture_label,
                }
            )
    return records


def build_lerobot_dataset(
    dataset: DemonstrationDataset,
    repo_id: str = "drona/gestures",
    fps: int = DEFAULT_FPS,
    root: str | Path | None = None,
):
    """Materialise a LeRobotDataset on disk from our demonstrations (LAZY).

    Requires `lerobot` installed. Returns the created LeRobotDataset. Each
    episode is written then closed with `save_episode()`; the gesture label is
    passed as the per-frame `task`.
    """
    try:
        from lerobot.common.datasets.lerobot_dataset import LeRobotDataset  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover - exercised only in Colab
        raise RuntimeError(
            "LeRobot not installed. Install with: "
            "pip install git+https://github.com/huggingface/lerobot.git"
        ) from exc

    lerobot_ds = LeRobotDataset.create(
        repo_id=repo_id,
        fps=fps,
        features=LEROBOT_FEATURES,
        root=str(root) if root else None,
    )

    import numpy as np

    for ep in dataset.episodes:
        for frame in ep.frames:
            lerobot_ds.add_frame(
                {
                    "observation.state": np.asarray(frame.observation_state, dtype=np.float32),
                    "action": np.asarray(frame.action, dtype=np.float32),
                    "task": ep.gesture_label,
                }
            )
        lerobot_ds.save_episode()

    logger.success(
        f"Built LeRobotDataset '{repo_id}' - {len(dataset.episodes)} episodes, "
        f"{dataset.total_frames} frames @ {fps} FPS"
    )
    return lerobot_ds
