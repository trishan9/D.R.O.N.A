"""
WS3 smoke tests - interaction policy layer.

Tests run without MuJoCo, LeRobot, or any robotics hardware.
The StubEnv and KeyframePolicy paths are exercised; MuJoCo/ACT paths
are tested via import-isolation guards.

Run with:  pytest tests/test_ws3_interaction.py -v
"""

from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

import numpy as np
import pytest

from drona.contracts import GestureType, InteractionAction, InteractionActionResult
from drona.interaction.act_policy import (
    KeyframePolicy,
    PolicyRouter,
    trajectory_path_length,
    trajectory_smoothness,
)
from drona.interaction.demonstration import (
    DOF,
    GESTURE_KEYFRAMES,
    REST_POSE,
    DemonstrationDataset,
    DemonstrationEpisode,
    DemonstrationFrame,
    clamp_joints,
    interpolate_keyframes,
    record_keyframe_episode,
)
from drona.interaction.gesture_dispatcher import (
    GestureDispatcher,
    make_action,
    make_dispatcher,
)
from drona.interaction.mujoco_env import StubEnv, make_env


# ── DemonstrationFrame / Episode / Dataset ────────────────────────────────────

class TestDemonstrationFrame:
    def test_roundtrip_serialization(self) -> None:
        q = np.array([0.1, -0.2, 0.3, -0.1, 0.0, 0.0], dtype=np.float32)
        frame = DemonstrationFrame(
            episode_index=0,
            frame_index=5,
            timestamp=0.25,
            observation_state=q,
            action=q * 0.9,
            gesture_label="greet",
        )
        d = frame.to_dict()
        frame2 = DemonstrationFrame.from_dict(d)
        assert frame2.episode_index == 0
        assert frame2.frame_index == 5
        assert frame2.gesture_label == "greet"
        np.testing.assert_allclose(frame2.observation_state, q, atol=1e-5)

    def test_to_dict_has_required_keys(self) -> None:
        q = REST_POSE.copy()
        frame = DemonstrationFrame(
            episode_index=0, frame_index=0, timestamp=0.0,
            observation_state=q, action=q, gesture_label="idle",
        )
        d = frame.to_dict()
        for key in ("episode_index", "frame_index", "timestamp",
                    "observation_state", "action", "gesture_label", "is_terminal"):
            assert key in d, f"Missing key: {key}"


class TestDemonstrationEpisode:
    def test_add_frame_increments_count(self) -> None:
        ep = DemonstrationEpisode(episode_index=0, gesture_label="nod")
        q = REST_POSE.copy()
        ep.add_frame(obs=q, action=q, timestamp=0.0)
        ep.add_frame(obs=q, action=q, timestamp=0.05)
        assert ep.n_frames == 2

    def test_mark_terminal_sets_flag(self) -> None:
        ep = DemonstrationEpisode(episode_index=0, gesture_label="idle")
        q = REST_POSE.copy()
        ep.add_frame(obs=q, action=q, timestamp=0.0)
        ep.mark_terminal()
        assert ep.frames[-1].is_terminal

    def test_duration_computed_correctly(self) -> None:
        ep = DemonstrationEpisode(episode_index=0, gesture_label="greet")
        q = REST_POSE.copy()
        for i in range(5):
            ep.add_frame(obs=q, action=q, timestamp=i * 0.05)
        assert abs(ep.duration_seconds - 0.2) < 1e-5


class TestDemonstrationDataset:
    def test_empty_dataset(self) -> None:
        ds = DemonstrationDataset()
        assert ds.total_frames == 0
        assert ds.gesture_counts == {}

    def test_add_episode(self) -> None:
        ds = DemonstrationDataset()
        ep = DemonstrationEpisode(episode_index=0, gesture_label="nod")
        q = REST_POSE.copy()
        ep.add_frame(obs=q, action=q, timestamp=0.0)
        ds.add_episode(ep)
        assert len(ds.episodes) == 1
        assert ds.total_frames == 1

    def test_jsonl_roundtrip(self, tmp_path: Path) -> None:
        ds = DemonstrationDataset()
        ep = record_keyframe_episode("idle", episode_index=0, dt=0.1)
        ds.add_episode(ep)
        path = tmp_path / "test.jsonl"
        ds.save_jsonl(path)
        ds2 = DemonstrationDataset.load_jsonl(path)
        assert ds2.total_frames == ds.total_frames
        assert ds2.episodes[0].gesture_label == "idle"

    def test_gesture_counts(self) -> None:
        ds = DemonstrationDataset()
        for label in ("greet", "greet", "nod"):
            ep = DemonstrationEpisode(episode_index=0, gesture_label=label)
            ds.add_episode(ep)
        counts = ds.gesture_counts
        assert counts["greet"] == 2
        assert counts["nod"] == 1


# ── Keyframe interpolation ─────────────────────────────────────────────────────

class TestInterpolateKeyframes:
    def test_empty_keyframes(self) -> None:
        result = interpolate_keyframes([])
        assert result == []

    def test_single_keyframe(self) -> None:
        kf = [([0.0] * DOF, 0.5)]
        result = interpolate_keyframes(kf, dt=0.1)
        # 0.5s / 0.1s = 5 steps
        assert len(result) == 5

    def test_output_arrays_have_correct_dof(self) -> None:
        kf = GESTURE_KEYFRAMES["greet"]
        result = interpolate_keyframes(kf, dt=0.05)
        for q, t in result:
            assert q.shape == (DOF,)

    def test_timestamps_monotonically_increasing(self) -> None:
        kf = GESTURE_KEYFRAMES["nod"]
        result = interpolate_keyframes(kf, dt=0.05)
        times = [t for _, t in result]
        assert all(times[i] <= times[i + 1] for i in range(len(times) - 1))

    def test_clamp_applied_to_output(self) -> None:
        kf = [([99.0] * DOF, 0.1)]  # out-of-range angles
        result = interpolate_keyframes(kf, dt=0.1)
        for q, _ in result:
            assert np.all(q <= math.pi + 1e-5)


class TestRecordKeyframeEpisode:
    @pytest.mark.parametrize("gesture", list(GESTURE_KEYFRAMES.keys()))
    def test_all_gestures_produce_episodes(self, gesture: str) -> None:
        ep = record_keyframe_episode(gesture, episode_index=0, dt=0.1)
        assert ep.n_frames > 0
        assert ep.gesture_label == gesture

    def test_episode_frames_have_correct_shape(self) -> None:
        ep = record_keyframe_episode("greet", episode_index=0, dt=0.1)
        for frame in ep.frames:
            assert frame.observation_state.shape == (DOF,)
            assert frame.action.shape == (DOF,)

    def test_last_frame_is_terminal(self) -> None:
        ep = record_keyframe_episode("nod", episode_index=0, dt=0.1)
        assert ep.frames[-1].is_terminal

    def test_unknown_gesture_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown gesture"):
            record_keyframe_episode("spin_360", episode_index=0)


# ── StubEnv ───────────────────────────────────────────────────────────────────

class TestStubEnv:
    def test_reset_returns_rest_pose(self) -> None:
        env = StubEnv()
        obs = env.reset()
        np.testing.assert_allclose(obs, REST_POSE, atol=1e-5)

    def test_step_returns_obs_of_correct_shape(self) -> None:
        env = StubEnv()
        env.reset()
        action = np.zeros(DOF, dtype=np.float32)
        obs, done = env.step(action)
        assert obs.shape == (DOF,)
        assert isinstance(done, bool)

    def test_trajectory_records_steps(self) -> None:
        env = StubEnv()
        env.reset()
        for _ in range(5):
            env.step(REST_POSE.copy())
        assert len(env.trajectory) == 5

    def test_reset_clears_trajectory(self) -> None:
        env = StubEnv()
        env.reset()
        env.step(REST_POSE.copy())
        env.reset()
        assert len(env.trajectory) == 0

    def test_joint_limits_enforced(self) -> None:
        env = StubEnv()
        env.reset()
        big = np.ones(DOF) * 99.0
        obs, _ = env.step(big)
        assert np.all(obs <= math.pi + 1e-3)

    def test_make_env_returns_stub_without_mujoco(self) -> None:
        env = make_env(prefer_mujoco=False)
        assert isinstance(env, StubEnv)


# ── KeyframePolicy ────────────────────────────────────────────────────────────

class TestKeyframePolicy:
    def test_unknown_gesture_raises(self) -> None:
        with pytest.raises(ValueError):
            KeyframePolicy("spin_dance")

    @pytest.mark.parametrize("gesture", list(GESTURE_KEYFRAMES.keys()))
    def test_all_gestures_initialise(self, gesture: str) -> None:
        policy = KeyframePolicy(gesture)
        assert policy.total_frames > 0

    def test_select_action_returns_correct_shape(self) -> None:
        policy = KeyframePolicy("greet")
        obs_dict = {"observation.state": REST_POSE.copy()}
        action = policy.select_action(obs_dict)
        assert action.shape == (DOF,)

    def test_policy_completes_after_all_frames(self) -> None:
        policy = KeyframePolicy("idle", dt=0.1)
        obs_dict = {"observation.state": REST_POSE.copy()}
        for _ in range(policy.total_frames):
            policy.select_action(obs_dict)
        assert policy.is_complete

    def test_reset_restarts_from_beginning(self) -> None:
        policy = KeyframePolicy("nod", dt=0.1)
        obs_dict = {"observation.state": REST_POSE.copy()}
        # consume some frames
        for _ in range(3):
            policy.select_action(obs_dict)
        policy.reset()
        # After reset, the first action should match frame 0
        first_after_reset = policy.select_action(obs_dict)
        policy2 = KeyframePolicy("nod", dt=0.1)
        first_fresh = policy2.select_action(obs_dict)
        np.testing.assert_allclose(first_after_reset, first_fresh, atol=1e-5)

    def test_policy_name_includes_gesture(self) -> None:
        policy = KeyframePolicy("farewell")
        assert "farewell" in policy.name


# ── PolicyRouter ──────────────────────────────────────────────────────────────

class TestPolicyRouter:
    def test_returns_keyframe_when_no_checkpoint(self) -> None:
        router = PolicyRouter(checkpoint_base_dir=None)
        policy = router.get_policy("greet")
        assert isinstance(policy, KeyframePolicy)

    def test_caches_policy(self) -> None:
        router = PolicyRouter()
        p1 = router.get_policy("nod")
        p2 = router.get_policy("nod")
        assert p1 is p2  # same object

    def test_clear_cache(self) -> None:
        router = PolicyRouter()
        router.get_policy("idle")
        router.clear_cache()
        assert len(router._cache) == 0

    def test_nonexistent_checkpoint_falls_back(self, tmp_path: Path) -> None:
        base = tmp_path / "checkpoints"
        base.mkdir()
        # No gesture subdirectory exists
        router = PolicyRouter(checkpoint_base_dir=base)
        policy = router.get_policy("greet")
        assert isinstance(policy, KeyframePolicy)


# ── GestureDispatcher ─────────────────────────────────────────────────────────

class TestGestureDispatcher:
    def _make_dispatcher(self) -> GestureDispatcher:
        env = StubEnv()
        return GestureDispatcher(env=env)

    def test_execute_greet_returns_result(self) -> None:
        dispatcher = self._make_dispatcher()
        action = make_action(GestureType.GREET)
        result = dispatcher.execute(action)
        assert isinstance(result, InteractionActionResult)
        assert result.success

    @pytest.mark.parametrize("gesture", list(GestureType))
    def test_all_gestures_execute_successfully(self, gesture: GestureType) -> None:
        dispatcher = self._make_dispatcher()
        action = make_action(gesture)
        result = dispatcher.execute(action)
        assert result.success, f"{gesture} failed: {result.error_message}"

    def test_result_action_id_matches(self) -> None:
        dispatcher = self._make_dispatcher()
        action = make_action(GestureType.NOD)
        result = dispatcher.execute(action)
        assert result.action_id == action.action_id

    def test_result_has_duration(self) -> None:
        dispatcher = self._make_dispatcher()
        action = make_action(GestureType.IDLE)
        result = dispatcher.execute(action)
        assert result.actual_duration_seconds is not None
        assert result.actual_duration_seconds >= 0.0

    def test_point_gesture_uses_target_direction(self) -> None:
        dispatcher = self._make_dispatcher()
        action = make_action(
            GestureType.POINT,
            target_direction=(1.0, 0.5, 0.0),
        )
        result = dispatcher.execute(action)
        assert result.success
        # Trajectory's j0 should be close to arctan2(0.5, 1.0) ≈ 0.46 rad
        traj = dispatcher.get_trajectory()
        if traj:
            j0_values = [step["action"][0] for step in traj]
            expected_yaw = math.atan2(0.5, 1.0)
            assert any(abs(j0 - expected_yaw) < 0.2 for j0 in j0_values)

    def test_get_trajectory_returns_list(self) -> None:
        dispatcher = self._make_dispatcher()
        action = make_action(GestureType.LISTEN)
        dispatcher.execute(action)
        traj = dispatcher.get_trajectory()
        assert isinstance(traj, list)
        assert len(traj) > 0

    def test_make_action_helper(self) -> None:
        action = make_action(
            GestureType.FAREWELL,
            speech_text="Goodbye!",
            duration_seconds=2.0,
        )
        assert isinstance(action, InteractionAction)
        assert action.gesture == GestureType.FAREWELL
        assert action.speech_text == "Goodbye!"
        assert action.action_id != ""


# ── Trajectory metrics ─────────────────────────────────────────────────────────

class TestTrajectoryMetrics:
    def test_smoothness_empty(self) -> None:
        assert trajectory_smoothness([]) == 0.0

    def test_smoothness_too_short(self) -> None:
        traj = [REST_POSE.copy() for _ in range(3)]
        assert trajectory_smoothness(traj) == 0.0

    def test_smoothness_constant_is_zero(self) -> None:
        traj = [REST_POSE.copy() for _ in range(20)]
        result = trajectory_smoothness(traj)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_smoothness_noisy_is_high(self) -> None:
        rng = np.random.default_rng(42)
        traj = [rng.uniform(-1, 1, DOF).astype(np.float32) for _ in range(20)]
        result = trajectory_smoothness(traj)
        assert result > 0.0

    def test_path_length_zero_for_single_frame(self) -> None:
        assert trajectory_path_length([REST_POSE.copy()]) == 0.0

    def test_path_length_positive_for_motion(self) -> None:
        traj = [REST_POSE.copy(), np.zeros(DOF, dtype=np.float32)]
        length = trajectory_path_length(traj)
        assert length > 0.0
