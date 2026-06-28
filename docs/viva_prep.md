# Viva Prep - Anticipated Examiner Questions & Answers

Practice answers for the BSc final-project defence. Grouped by theme. Each answer
points to where the claim is evidenced in the repo.

---

## A. Contributions & novelty

**Q1. What are your original contributions?**
Four: **C1** hybrid retrieval (BM25 + dense + RRF + cross-encoder rerank) beats
dense-only on a Nepal-grounded corpus; **C2** a transparent, rule-based cognitive-
bias detector that drives a bias-aware prompt and is *measurably* mitigated in
responses; **C3** ACT imitation-learned gestures that are smoother (lower jerk)
than a keyframe baseline in simulation; **C4** a fully local, open-source,
Nepal-first stack with no paid APIs in the request path. Evidenced in
`notebooks/04,05,07,10` and `drona/evaluation/`.

**Q2. Isn't this just RAG + a robot?**
The novelty is the *integration for bias-aware, locally-grounded advising*: the
Nepal-first tiering (C4), the falsifiable bias mitigation (C2), and the embodied
delivery with a clean sim-to-real seam (C3/Mower et al. 2026). No single existing
system combines these for the Nepali computing-student context.

---

## B. Retrieval (C1)

**Q3. Why hybrid retrieval, not just a vector DB?**
Dense retrieval misses exact lexical matches (company names, module codes); BM25
misses semantics. Reciprocal Rank Fusion (Cormack et al. 2009) combines both, and a
cross-encoder reranker (Nogueira & Cho 2019) fixes ordering. `notebooks/04_retrieval_ablations.ipynb`
quantifies the NDCG@5/MRR gain.

**Q4. Why two embedding models?**
bge-small for curriculum (general semantic) and JobBERT-v3 for jobs (domain-tuned,
Decorte et al. 2025). `notebooks/03_embedding_quality.ipynb` shows JobBERT-v3
separates career queries better - justifying the dual index.

**Q5. How do you know retrieval is relevant without labelled data?**
Synthetic labelled queries (`evaluation/queries.py`) with collection-membership as
a relevance proxy - standard IR practice (TREC/BEIR) when human labels need ethics
approval. This is documented as a limitation, not hidden.

---

## C. Bias (C2)

**Q6. Why rule-based bias detection instead of an LLM classifier?**
**Transparency and falsifiability.** Every detection is a named keyword/regex
pattern an examiner can inspect and challenge; an LLM judge would be a black box and
could itself hallucinate bias. Trade-off: lower recall on paraphrases - measured in
`notebooks/05_bias_detection_eval.ipynb`.

**Q7. How do you *mitigate* bias, not just detect it?**
Multi-pathway output (anti-anchoring), explicit counter-recommendations
(anti-confirmation), reversibility framing (anti loss-aversion, Prospect Theory),
hedged language (anti-overconfidence), and transparent bias flags shown in the UI.
Measured by `drona/evaluation/bias_mitigation.py`.

**Q8. Which biases and why those six?**
Availability, anchoring, confirmation, Dunning–Kruger, loss-aversion, consistency -
drawn from Tversky & Kahneman 1974 and chosen because they are the ones that most
distort *career* decisions (e.g. "my friend earns X", "I already told my parents").

---

## D. Robotics (C3)

**Q9. You have no physical robot - how is C3 valid?**
C3 is a *simulation* contribution in Phase 1 (explicit in the proposal). We measure
jerk, path length, and apex accuracy in MuJoCo/Gazebo and compare ACT vs keyframe
(`sim_eval.py`, `notebooks/07,10`). The ROS2 action interface swaps to the SO-100
unchanged in Phase 2.

**Q10. Why ACT, and why also Diffusion Policy?**
ACT (Zhao et al. 2023) action-chunking gives smooth, temporally-consistent motion
on small datasets. Diffusion Policy (Chi et al. 2023) is the ablation comparison to
show the choice is justified, not arbitrary. Both via LeRobot (Capuano et al. 2025).

**Q11. How does it become a real robot?**
Implement one driver node subscribing to the gesture command and publishing real
joint states; advising/policy/contract code is untouched. See
`notebooks/11_sim_to_real_handoff.ipynb` and `phase2_plan.md`.

---

## E. Stack, ethics & local-first (C4)

**Q12. Why local-only? You have Gemini/Vertex access.**
Data sovereignty, reproducibility, and the guarantee that no student query leaves
the machine. Cloud models are used *offline only* (synthetic data, eval judging),
enforced at startup (`api/app.py`). This is the C4 contribution.

**Q13. How do you handle PII?**
Zero PII: random session UUID, in-memory only, no persistence, no analytics,
contract-enforced (`extra="forbid"`). See `data_ethics.md`.

**Q14. The MeroJob data - did you scrape it?**
No. MeroJob ToS §3.E prohibits scraping. Data is **manually collected** into a JSON
template; scraper stubs are disabled and document the prohibition. See `data_ethics.md` §3.

**Q15. Synthetic data - isn't that circular for fine-tuning?**
It's labelled (`is_synthetic=True`), anchored to real entries, human-reviewed into a
gold set, used only for fine-tune/eval, and never presented to students as evidence.
The base-vs-LoRA ablation (`finetune/ablation.py`) checks it actually helps.

---

## F. Evaluation & rigour

**Q16. How will you prove the robot helps students more than traditional advising?**
The *user study is Phase 2* (needs ethics approval). What ships is the **analysis
harness** (`evaluation/stats.py`): Welch t / Mann-Whitney + Cohen's d + bootstrap CI,
ready for the data. Reporting effect sizes + CIs, not just p-values.

**Q17. What are the system's limitations?**
Synthetic eval labels; rule-based bias detector recall ceiling; sim-only C3;
Phi-3.5-mini capacity; small Nepal corpus dependent on manual collection. All
documented in the cards and notebooks.

---

## G. Engineering

**Q18. Why Pydantic contracts everywhere?**
Single source of truth, runtime validation, and they mirror cleanly to ROS2
`.msg/.action/.srv` - so Phase 2 is a transport change, not a rewrite.

**Q19. How is it reproducible?**
Pinned deps (`pyproject.toml`), Docker Compose for Postgres/Ollama, seeded
stochastic code, Colab-shaped training notebooks, and a JSON evaluation report.

**Q20. Show me it runs.**
`pytest -q` (431 pass), `python scripts/run_evaluation.py --c2 --c3`,
`python scripts/run_api.py` + `cd frontend && npm run dev`, and
`ros2 launch drona_bringup drona_system.launch.py` on the Ubuntu box.
