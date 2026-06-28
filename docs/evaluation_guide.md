# Evaluation Guide

D.R.O.N.A. is assessed against four research contributions (C1–C4). This guide explains what each contribution measures, how to run the evaluation, and how to interpret results.

---

## Quick Start

```bash
# Run all contributions
python scripts/run_evaluation.py --c1 --c2 --c3 --c4

# Run specific contributions (e.g. bias detection only)
python scripts/run_evaluation.py --c2

# Output directory (default: data/evaluation/)
python scripts/run_evaluation.py --c1 --c2 --c3 --c4 --output-dir data/evaluation/
```

Results are written to JSON files in the output directory. A human-readable summary is printed to stdout.

---

## C1 - Retrieval Quality

**Claim:** The dual-collection ChromaDB retriever (dense + BM25 + RRF fusion) achieves MRR@10 ≥ 0.6 and nDCG@10 ≥ 0.55 on a held-out relevance-graded query set.

**Method:**
1. A set of ~50 test queries is matched against the ChromaDB index
2. Human-authored relevance labels (3-point scale: 0 = irrelevant, 1 = partial, 2 = highly relevant) are used as ground truth
3. MRR@10 (Mean Reciprocal Rank) and nDCG@10 (normalised Discounted Cumulative Gain) are computed

**Prerequisites:**
- ChromaDB must be populated: `python scripts/ingest_data.py`
- Relevance judgements file: `data/evaluation/relevance_judgements.json`

**Output file:** `data/evaluation/c1_retrieval_quality.json`

```json
{
  "mrr_at_10": 0.68,
  "ndcg_at_10": 0.61,
  "n_queries": 50,
  "nepal_fraction": 0.73
}
```

---

## C2 - Bias Detection Accuracy

**Claim:** The rule-based `BiasDetector` achieves ≥ 85% F1 on five cognitive bias archetypes: anchoring, availability, status quo, overconfidence, and consistency.

**Method:**
1. ~200 synthetic query records from `data/cards/synthetic_advisory.json` are loaded
2. `BiasDetector.detect()` is run on each query
3. Predicted labels are compared against ground-truth `bias_type` metadata
4. Precision, recall, and F1 are computed per bias type and macro-averaged

**No external services required** - bias detection is pure Python rule-based logic.

**Output file:** `data/evaluation/c2_bias_detection.json`

```json
{
  "macro_f1": 0.87,
  "macro_precision": 0.89,
  "macro_recall": 0.85,
  "per_bias": {
    "anchoring":    {"precision": 0.92, "recall": 0.90, "f1": 0.91},
    "availability": {"precision": 0.85, "recall": 0.82, "f1": 0.83},
    "status_quo":   {"precision": 0.88, "recall": 0.84, "f1": 0.86},
    "overconfidence":{"precision": 0.87, "recall": 0.83, "f1": 0.85},
    "consistency":  {"precision": 0.91, "recall": 0.86, "f1": 0.88}
  },
  "n_queries": 200
}
```

---

## C3 - Gesture Smoothness

**Claim:** ACT-trained gesture policies produce lower peak jerk (≤ 30 rad/s³) than the keyframe interpolation baseline.

**Method:**
1. Both `KeyframePolicy` and `ACTPolicy` are rolled out for each gesture in `StubEnv`
2. Joint trajectory jerk (third derivative of position, computed via finite differences) is calculated
3. Peak jerk and RMS jerk are compared across policies

**Prerequisites:**
- ACT checkpoints must exist in `data/checkpoints/` (run `scripts/train_act.py` first)
- Without checkpoints, only the keyframe baseline is measured

**Output file:** `data/evaluation/c3_gesture_smoothness.json`

```json
{
  "gestures": {
    "greet": {
      "keyframe_peak_jerk": 42.3,
      "act_peak_jerk": 18.7,
      "improvement_pct": 55.8
    }
  },
  "overall_improvement_pct": 52.1
}
```

---

## C4 - Nepal Citation Ratio

**Claim:** ≥ 60% of citations in advising responses are sourced from Nepal-tier data (`DataTier.NEPAL`).

**Method:**
1. A set of ~30 test queries is submitted to `AdvisingEngine` (requires Ollama + populated ChromaDB)
2. The `DataTier` of each citation in each response is recorded
3. The fraction of NEPAL-tier citations is computed

**Prerequisites:**
- Ollama running: `ollama serve`
- ChromaDB populated with Nepal job postings and curriculum data

**Output file:** `data/evaluation/c4_nepal_ratio.json`

```json
{
  "nepal_citation_ratio": 0.71,
  "total_citations": 187,
  "nepal_citations": 133,
  "n_responses": 30,
  "n_refusals": 2
}
```

---

## Running in ROS2 Context

The evaluation launch file runs all four nodes and triggers the evaluation harness:

```bash
ros2 launch drona_bringup drona_evaluation.launch.py contributions:=c2,c3
```

C1 and C4 require Ollama + ChromaDB; C2 and C3 run fully offline.

---

## Interpreting Results

| Contribution | Target | Passing threshold |
|-------------|--------|-------------------|
| C1 MRR@10 | ≥ 0.60 | ≥ 0.55 (acceptable) |
| C1 nDCG@10 | ≥ 0.55 | ≥ 0.50 (acceptable) |
| C2 macro-F1 | ≥ 0.85 | ≥ 0.80 (acceptable) |
| C3 peak jerk (ACT) | ≤ 30 rad/s³ | ≤ 50 rad/s³ (acceptable) |
| C4 Nepal ratio | ≥ 0.60 | ≥ 0.50 (acceptable) |

Results below the acceptable threshold indicate a data quality or configuration issue rather than a system failure.
