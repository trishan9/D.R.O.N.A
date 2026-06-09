# Model Card — `diffusion-gesture-policy`

**Architecture:** Diffusion Policy (visuomotor action diffusion) via LeRobot
**Task:** upper-body social gesture generation for a 6-DOF arm (C3 **ablation** vs ACT)
**Version:** 0.1.0  **Created:** 2026-06-09
**License:** MIT (adapter/weights); LeRobot Apache-2.0
**References:** Chi et al. 2023 (Diffusion Policy, arXiv:2303.04137); Capuano et al. 2025 (LeRobot tutorial)

## Training data
Same `LeRobotDataset` v2 demonstrations as `act-gesture-policy`
(`drona.interaction.lerobot_dataset`), so the ACT-vs-Diffusion comparison is
controlled (identical data, different policy class).

## Intended use
Serve as the **ablation comparison** to ACT for the C3 contribution — does the
policy-learning choice matter, and which is smoother on this small-demonstration
regime? Exposed via `drona.interaction.diffusion_policy` behind `BasePolicy`, and
selectable through `make_diffusion_or_keyframe`.

## Out of scope
- Production gesture serving (ACT is the primary policy); this exists for the study.
- Object manipulation / safety-critical motion.

## Hyperparameters (default)
- diffusion steps: 100 (train) / 16 (inference, DDIM-style)
- obs/action horizons per LeRobot Diffusion defaults; T4-sized batch
- fps: `DEFAULT_FPS` (matches `lerobot_dataset`)

## Evaluation
- **Harness:** `drona.interaction.sim_eval`; reported alongside ACT and keyframe in
  `notebooks/08_lerobot_diffusion_policy.ipynb` and `10_end_to_end_eval.ipynb`.
- **Metrics:** success rate, mean jerk, path length, apex error (same as ACT).
- **Status:** train on Colab T4 (`notebooks/08`), copy checkpoint, run `sim_eval`.

## Known limitations
- Diffusion sampling is slower at inference than ACT — relevant for real-time
  gesture latency; quantified in the ablation.
- Simulation-trained; Colab-only training (exceeds 4 GB VRAM).

## How to run
Train: `notebooks/08_lerobot_diffusion_policy.ipynb` (Colab T4). Compare against ACT
and keyframe in `notebooks/10_end_to_end_eval.ipynb`.
