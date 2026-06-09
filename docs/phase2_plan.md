# Phase 2 Plan — Hardware + Study (future work)

Phase 2 is the portion the proposal explicitly defers. The Phase 1 system is built
so that each Phase 2 item is a **swap or an add-on**, not a redesign.

## Scope

| Item | What changes | What does NOT change |
|---|---|---|
| **Physical SO-100 arm** | Replace the sim `arm_interface` backend with the real driver; the `policy_node` `ExecuteGesture` action stays identical | Advising logic, policies, contracts, ROS2 interface |
| **Live student user study** | Recruit BSc students; run robot-vs-traditional advising sessions; collect Likert/engagement measures (with ethics approval + consent) | The analysis harness (`evaluation/stats.py`) is already built |
| **Multilingual Nepali code-switch** | Promote Qwen2.5-3B path; add Nepali/Romanised-Nepali handling in prompt + retrieval | The fallback client wiring already exists |

## Why these are Phase 2 (not skipped)

- **Hardware**: the GTX-1650 laptop and project timeline make sim-validation the
  responsible Phase-1 target; the SO-100 swap is a clean ROS2 driver change.
- **User study**: requires ethics-board approval and PII-handling review, which is
  out of scope for a software-only Phase-1 deliverable. Zero PII is collected now.
- **Multilingual production**: needs a Nepali advising eval set and native-speaker
  review to claim quality; the architecture supports it today.

## Sim-to-real handoff (already in place)

- `policy_node` consumes a clean `drona_msgs/action/ExecuteGesture` interface.
- The same `/drona/joint_states` stream drives `StubEnv`, the URDF in Gazebo/Isaac,
  and (Phase 2) the SO-100 — see `notebooks/11_sim_to_real_handoff.ipynb` and
  `docs/ros2_topics_actions.md`.
- Swapping in the real arm means implementing one driver node that subscribes to
  the gesture command and publishes real joint states; no advising/policy code changes.

## Study design sketch (for when ethics approval lands)

- **Conditions**: D.R.O.N.A. embodied advising vs traditional (text-only) advising.
- **Measures**: decision diversity, perceived helpfulness, engagement, bias-shift.
- **Analysis**: `compare_conditions()` (Welch t / Mann-Whitney + Cohen's d + bootstrap
  CI) for between-subjects; `paired_comparison()` for pre/post within-subjects.
- **N**: powered for a medium effect (d≈0.5) — the harness reports effect size and
  CI, not just p-values, per HRI best practice (Bartneck et al. 2020).

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Real arm dynamics differ from sim | Domain-randomised demonstrations; keyframe fallback always available |
| Ethics approval delay | Phase 1 ships fully without it; study is decoupled |
| Nepali NLP quality | Native-speaker review gate before any multilingual claim |
