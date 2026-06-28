"""Phase 4 (LeRobot policies) tests - dataset conversion, sim eval, VLA seam.

All pure-Python paths run without lerobot/torch/mujoco installed (the
KeyframePolicy + StubEnv fallbacks). Heavy backends are only exercised lazily
in the Colab notebooks, so they are not required here.
"""

from __future__ import annotations

import numpy as np
import pytest

from drona.interaction.demonstration import (
    DOF,
    GESTURE_KEYFRAMES,
    REST_POSE,
    DemonstrationDataset,
    record_keyframe_episode,
)
from drona.interaction.lerobot_dataset import (
    DEFAULT_FPS,
    LEROBOT_FEATURES,
    to_lerobot_records,
)

# ── LeRobot dataset conversion ────────────────────────────────────────────────

def _sample_dataset() -> DemonstrationDataset:
    ds = DemonstrationDataset()
    ds.add_episode(record_keyframe_episode("greet", 0))
    ds.add_episode(record_keyframe_episode("nod", 1))
    return ds


class TestLeRobotDataset:
    def test_features_schema(self) -> None:
        assert set(LEROBOT_FEATURES) == {"observation.state", "action"}
        for feat in LEROBOT_FEATURES.values():
            assert feat["dtype"] == "float32"
            assert feat["shape"] == [DOF]
            assert len(feat["names"]) == DOF

    def test_records_count_matches_frames(self) -> None:
        ds = _sample_dataset()
        recs = to_lerobot_records(ds)
        assert len(recs) == ds.total_frames

    def test_record_keys_and_types(self) -> None:
        recs = to_lerobot_records(_sample_dataset())
        r = recs[0]
        for key in ("observation.state", "action", "episode_index",
                    "frame_index", "timestamp", "next.done", "task"):
            assert key in r
        assert len(r["observation.state"]) == DOF
        assert len(r["action"]) == DOF
        assert isinstance(r["next.done"], bool)

    def test_task_is_gesture_label(self) -> None:
        recs = to_lerobot_records(_sample_dataset())
        tasks = {r["task"] for r in recs}
        assert tasks == {"greet", "nod"}

    def test_done_flag_only_on_last_frame_per_episode(self) -> None:
        recs = to_lerobot_records(_sample_dataset())
        by_ep: dict[int, list[dict]] = {}
        for r in recs:
            by_ep.setdefault(r["episode_index"], []).append(r)
        for frames in by_ep.values():
            dones = [f["next.done"] for f in frames]
            assert dones[-1] is True
            assert sum(dones) == 1

    def test_frame_index_is_sequential(self) -> None:
        recs = to_lerobot_records(_sample_dataset())
        ep0 = [r for r in recs if r["episode_index"] == 0]
        assert [r["frame_index"] for r in ep0] == list(range(len(ep0)))

    def test_default_fps(self) -> None:
        # dt=0.05 in keyframe interpolation → 20 FPS.
        assert DEFAULT_FPS == 20

    def test_build_lerobot_dataset_requires_lerobot(self) -> None:
        from drona.interaction.lerobot_dataset import build_lerobot_dataset

        try:
            import lerobot  # noqa: F401
        except ImportError:
            with pytest.raises(RuntimeError, match="LeRobot not installed"):
                build_lerobot_dataset(_sample_dataset())


# ── Sim evaluation ────────────────────────────────────────────────────────────

class TestSimEval:
    def test_apex_pose_is_furthest_from_rest(self) -> None:
        from drona.interaction.sim_eval import gesture_apex_pose

        apex = gesture_apex_pose("greet")
        assert apex.shape == (DOF,)
        # apex should be at least as far from rest as every keyframe.
        dists = [
            float(np.linalg.norm(np.array(p, dtype=np.float32) - REST_POSE))
            for p, _ in GESTURE_KEYFRAMES["greet"]
        ]
        assert float(np.linalg.norm(apex - REST_POSE)) == pytest.approx(max(dists), abs=1e-5)

    def test_keyframe_baseline_all_succeed(self) -> None:
        from drona.interaction.sim_eval import evaluate_keyframe_baseline

        report = evaluate_keyframe_baseline()
        assert report.success_rate == 1.0
        assert set(report.per_gesture) == set(GESTURE_KEYFRAMES)
        assert report.mean_jerk >= 0.0

    def test_evaluate_gesture_metrics_fields(self) -> None:
        from drona.interaction.act_policy import KeyframePolicy
        from drona.interaction.mujoco_env import StubEnv
        from drona.interaction.sim_eval import evaluate_gesture

        m = evaluate_gesture(KeyframePolicy("nod"), StubEnv(), "nod")
        assert m.gesture == "nod"
        assert m.success is True
        assert m.reached_apex and m.returned_to_rest
        assert m.jerk >= 0.0
        assert m.path_length >= 0.0

    def test_idle_success_is_stillness(self) -> None:
        from drona.interaction.act_policy import KeyframePolicy
        from drona.interaction.mujoco_env import StubEnv
        from drona.interaction.sim_eval import evaluate_gesture

        m = evaluate_gesture(KeyframePolicy("idle"), StubEnv(), "idle")
        assert m.success is True
        assert m.path_length == pytest.approx(0.0, abs=1e-3)

    def test_rollout_length(self) -> None:
        from drona.interaction.act_policy import KeyframePolicy
        from drona.interaction.mujoco_env import StubEnv
        from drona.interaction.sim_eval import rollout

        positions = rollout(KeyframePolicy("greet"), StubEnv(), n_steps=50)
        assert len(positions) == 51  # initial obs + n_steps
        assert all(p.shape == (DOF,) for p in positions)

    def test_compare_identical_policies_zero_delta(self) -> None:
        from drona.interaction.act_policy import KeyframePolicy
        from drona.interaction.sim_eval import compare_policies

        result = compare_policies(
            base_factory=lambda g: KeyframePolicy(g),
            other_factory=lambda g: KeyframePolicy(g),
        )
        assert result["delta"]["success_rate"] == 0.0
        assert result["delta"]["mean_jerk"] == pytest.approx(0.0, abs=1e-6)


# ── SmolVLA seam ──────────────────────────────────────────────────────────────

class TestSmolVLA:
    def test_instruction_mapping(self) -> None:
        from drona.interaction.smolvla import instruction_to_gesture

        assert instruction_to_gesture("please greet the new student") == "greet"
        assert instruction_to_gesture("point to the screen") == "point"
        assert instruction_to_gesture("say goodbye now") == "farewell"
        assert instruction_to_gesture("nod in agreement") == "nod"
        assert instruction_to_gesture("just wait there") == "idle"

    def test_unknown_instruction_defaults_idle(self) -> None:
        from drona.interaction.smolvla import instruction_to_gesture

        assert instruction_to_gesture("xyzzy frobnicate") == "idle"

    def test_fallback_when_lerobot_absent(self) -> None:
        from drona.interaction.smolvla import SmolVLAPolicy

        try:
            import lerobot  # noqa: F401

            pytest.skip("lerobot installed; fallback path not exercised")
        except ImportError:
            pass

        policy = SmolVLAPolicy("greet the student")
        assert policy.using_fallback is True
        assert policy.gesture == "greet"
        action = policy.select_action({"observation.state": np.zeros(DOF, dtype=np.float32)})
        assert action.shape == (DOF,)
        assert "fallback" in policy.name

    def test_no_fallback_raises_without_lerobot(self) -> None:
        from drona.interaction.smolvla import SmolVLAPolicy

        try:
            import lerobot  # noqa: F401

            pytest.skip("lerobot installed")
        except ImportError:
            pass

        with pytest.raises(RuntimeError, match="SmolVLA unavailable"):
            SmolVLAPolicy("greet", allow_fallback=False)


# ── Diffusion Policy wrapper ──────────────────────────────────────────────────

class TestDiffusionPolicy:
    def test_make_diffusion_falls_back_to_keyframe(self) -> None:
        from drona.interaction.act_policy import KeyframePolicy
        from drona.interaction.diffusion_policy import make_diffusion_or_keyframe

        policy = make_diffusion_or_keyframe("greet", checkpoint_dir=None)
        assert isinstance(policy, KeyframePolicy)

    def test_diffusion_policy_requires_lerobot(self) -> None:
        from drona.interaction.diffusion_policy import LeRobotDiffusionPolicy

        try:
            import lerobot  # noqa: F401

            pytest.skip("lerobot installed")
        except ImportError:
            pass

        with pytest.raises(RuntimeError, match="LeRobot not installed"):
            LeRobotDiffusionPolicy("data/checkpoints/diffusion/greet")
