# Model Card - `act-gesture-policy`

**Architecture:** ACT (Action Chunking Transformer) via LeRobot
**Task:** upper-body social gesture generation for a 6-DOF arm (greet, nod, point, listen, farewell, idle)
**Version:** 0.1.0  **Created:** 2026-06-09
**License:** MIT (adapter/weights); LeRobot Apache-2.0
**References:** Zhao et al. 2023 (ACT, arXiv:2304.13705); Capuano et al. 2025 (LeRobot tutorial, arXiv:2510.12403)

## Training data
Demonstration trajectories collected/scripted in simulation and converted to the
`LeRobotDataset` v2 format by `drona.interaction.lerobot_dataset`. Joint names match
the policy/URDF convention (`j0_base_yaw` … `j5_gripper`). Demonstrations are
domain-randomised around keyframe apex poses to provide smooth supervision.

## Intended use
Generate smooth, temporally-consistent gesture trajectories at inference time for
the embodied advising layer (C3), exposed through the ROS2 `ExecuteGesture` action.
Drop-in for `KeyframePolicy` via the `BasePolicy` interface.

## Out of scope
- Manipulation / grasping of real objects (gestures only).
- Safety-critical motion without a real-robot safety layer (Phase 2 driver).

## Hyperparameters (default)
- chunk_size: 100, kl_weight: 10, dim_model: 512, n_heads: 8
- epochs: tuned on Colab T4; batch sized to T4 16 GB
- fps: `DEFAULT_FPS` (matches `lerobot_dataset`)

## Evaluation
- **Harness:** `drona.interaction.sim_eval` (`compare_policies`) + `notebooks/07,10`.
- **Metrics:** success rate (apex/rest tolerance), mean **jerk** (smoothness),
  path length, apex error.
- **Baseline:** `KeyframePolicy` (linear interpolation). ACT is expected to achieve
  **lower jerk** than the keyframe baseline - the C3 claim.
- **Status:** train on Colab T4 (`notebooks/07_lerobot_act_training.ipynb`), then
  copy the checkpoint to `data/checkpoints/` and run `sim_eval` to fill numbers.

## Known limitations
- Trained primarily in simulation; sim-to-real gap addressed in Phase 2.
- Small demonstration set → limited gesture vocabulary.
- 4 GB-VRAM laptop cannot train this; training is Colab-only by design.

## How to run
Train: `notebooks/07_lerobot_act_training.ipynb` (Colab T4). Evaluate/compare:
`notebooks/10_end_to_end_eval.ipynb` or `notebooks/11_sim_to_real_handoff.ipynb`.
