# Demo Video Script - D.R.O.N.A.

A shot-by-shot script for the project demonstration video (~8–10 min). Recording is
the student's job; this is the storyboard, narration, and exact commands. Target
audience: examiners. Show, don't tell - every claim is demonstrated live.

> Tip: record terminal + browser + (sim/robot) as three sources; cut between them.

---

## 0. Cold open (0:00–0:30)

- **Visual:** title card "D.R.O.N.A. - bias-aware robotic academic advising".
- **Narration:** "D.R.O.N.A. helps Nepali computing students explore career
  pathways, grounded in local data, while actively countering cognitive bias - and
  delivers it through an embodied robot."
- **Cut to:** the running frontend dashboard.

## 1. The problem (0:30–1:15)

- **Visual:** slide - anchoring/availability bias in career choice ("my friend earns
  Rs 80k at Leapfrog").
- **Narration:** state the four contributions (C1–C4) in one sentence each.

## 2. System start-up (1:15–2:15)

- **Visual:** terminal. Run, narrating each:

```bash
docker compose up -d            # Postgres + Ollama
python scripts/ingest_data.py   # build the Nepal-first knowledge base
python scripts/run_api.py       # FastAPI advising service (local-only LLM)
cd frontend && npm run dev       # Next.js dashboard
```

- **Narration:** "Everything runs locally - no student query ever leaves the
  machine (C4)."

## 3. Advising walkthrough - C1 + C2 (2:15–4:30)

- **Visual:** browser. Build a session profile (interests, year, skills) - note "no
  name, no email; session-scoped, zero PII".
- **Action:** ask a *biased* query: *"My friend earns Rs 80,000 at Leapfrog - how do
  I get exactly that job?"*
- **Show:**
  - Streaming response over websocket.
  - **Bias flags** panel lighting up (availability + anchoring) - open it, show the
    named, falsifiable signal.
  - **Multiple pathways** (anti-anchoring), each with **citations** colour-coded by
    tier; drill into a Nepal-tier citation.
  - The **counter-recommendation** panel revealing the non-obvious option.
  - **Reversibility tags** on next steps (loss-aversion mitigation).
- **Narration:** tie each UI element to C1 (grounded pathways) and C2 (bias
  mitigation). Show the **diversity meter** and **skill tree**.

## 4. Retrieval under the hood - C1 (4:30–5:30)

- **Visual:** open `notebooks/04_retrieval_ablations.ipynb`; run the C1 cell.
- **Show:** hybrid vs dense NDCG@5 / MRR table - hybrid wins.
- **Narration:** "BM25 + dense + RRF + reranking - quantified, not asserted."

## 5. The robot - C3 (5:30–7:30)

- **Visual:** Ubuntu box. Build + launch sim:

```bash
cd ros2_ws && colcon build --symlink-install && source install/setup.bash
ros2 launch drona_bringup drona_system.launch.py use_rviz:=true
# In another terminal - drive a gesture through the action server:
ros2 action send_goal /drona/execute_gesture_action \
  drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback
```

- **Show:** the URDF arm in RViz/Gazebo performing *greet*, *nod*, *point*; the
  action **feedback streaming** in the terminal.
- **Cut to:** `notebooks/07` / `10` - ACT-vs-keyframe jerk comparison.
- **Narration:** "ACT imitation learning yields smoother motion than the scripted
  baseline (C3); the same interface drives a real SO-100 in Phase 2."

## 6. Evaluation (7:30–8:45)

- **Visual:** terminal.

```bash
python scripts/run_evaluation.py --all
```

- **Show:** the C1–C4 summary; open the saved JSON report.
- **Narration:** mention the bias-mitigation metrics and the scipy.stats harness
  ("ready for the Phase-2 user study").

## 7. Close (8:45–9:30)

- **Visual:** architecture mermaid diagram (`docs/architecture.md`).
- **Narration:** recap C1–C4, the local-first ethics stance, and the clean
  sim-to-real path. "Phase 1 is complete and runnable; only the physical arm swap
  and the live study remain."
- **End card:** repo URL + author.

---

## Capture checklist

- [ ] 1080p, terminal font ≥ 16pt, browser zoom 110%.
- [ ] Pre-pull Ollama models (`ollama pull phi3.5`) before recording.
- [ ] Pre-populate ChromaDB so retrieval cells show real numbers.
- [ ] Have the Ubuntu/ROS2 box ready with the workspace built.
- [ ] Keep each command on screen long enough to read.
