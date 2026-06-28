/**
 * Analytics model for the Analytics page.
 *
 * Two kinds of numbers, always clearly labelled:
 *   - LIVE: computed in-browser from the current advising response or the real
 *     gesture keyframes (tier mix, diversity, bias-flag coverage, latency,
 *     keyframe jerk). These are honest, reproducible client-side computations.
 *   - REFERENCE: the shape of results the evaluation harness produces
 *     (NDCG, bias precision/recall, ACT-vs-keyframe). These are illustrative
 *     placeholders to show the chart/structure; the real values come from
 *     `python scripts/run_evaluation.py --all` → data/evaluation/report_*.json.
 *
 * Nothing here is presented as a measured thesis result unless it is LIVE.
 */

import type { AdvisingResponse, DataTier } from "./types";
import { computeDiversity } from "./gamification";
import { GESTURES, gestureTrajectory, meanAbsJerk, type GestureName } from "./robot";

export type MetricSource = "live" | "reference";

export interface Contribution {
  id: "C1" | "C2" | "C3" | "C4";
  title: string;
  claim: string;
  technique: string;
}

export const CONTRIBUTIONS: Contribution[] = [
  {
    id: "C1",
    title: "Dual-embedding hybrid retrieval",
    claim: "Hybrid BM25 + dense retrieval with reranking beats dense-only on advising queries.",
    technique: "bge-small (curriculum) + JobBERT-v3 (career) · Reciprocal Rank Fusion · cross-encoder rerank",
  },
  {
    id: "C2",
    title: "Cognitive-bias-aware advising",
    claim: "Six biases are detected and explicitly mitigated in every response.",
    technique: "Transparent rule-based detector → bias-flagged system prompt",
  },
  {
    id: "C3",
    title: "Demonstration-learned gestures",
    claim: "ACT imitation policies produce smoother gestures than the keyframe baseline.",
    technique: "LeRobot ACT / Diffusion Policy trained in sim · mean-jerk smoothness",
  },
  {
    id: "C4",
    title: "Locally-grounded (Nepal) stack",
    claim: "Advising prioritises Nepal-tier evidence and runs fully local (no paid APIs).",
    technique: "Nepal-first tier boost · Ollama Phi-3.5 in the request path",
  },
];

// ── LIVE: tier distribution across the current response's citations ───────────

export interface TierDatum {
  tier: DataTier;
  label: string;
  count: number;
}

const TIER_LABELS: Record<DataTier, string> = {
  nepal: "Nepal",
  regional: "Regional",
  international: "International",
  synthetic: "Synthetic",
};

export function tierDistribution(response: AdvisingResponse | null): TierDatum[] {
  const counts: Record<DataTier, number> = { nepal: 0, regional: 0, international: 0, synthetic: 0 };
  if (response) {
    for (const p of response.pathways) for (const c of p.citations) counts[c.tier] += 1;
  }
  return (Object.keys(counts) as DataTier[]).map((tier) => ({
    tier,
    label: TIER_LABELS[tier],
    count: counts[tier],
  }));
}

export function nepalFirstRate(response: AdvisingResponse | null): number {
  const dist = tierDistribution(response);
  const total = dist.reduce((a, d) => a + d.count, 0);
  if (!total) return 0;
  return Math.round((dist.find((d) => d.tier === "nepal")!.count / total) * 100);
}

export interface LiveSummary {
  pathwayCount: number;
  diversityScore: number;
  diversityLabel: string;
  biasFlagCount: number;
  citationCount: number;
  nepalRate: number;
  generationMs: number | null;
  hasResponse: boolean;
}

export function liveSummary(response: AdvisingResponse | null): LiveSummary {
  if (!response) {
    return {
      pathwayCount: 0,
      diversityScore: 0,
      diversityLabel: "-",
      biasFlagCount: 0,
      citationCount: 0,
      nepalRate: 0,
      generationMs: null,
      hasResponse: false,
    };
  }
  const div = computeDiversity(response);
  const citationCount = response.pathways.reduce((a, p) => a + p.citations.length, 0);
  return {
    pathwayCount: response.pathways.length,
    diversityScore: div.score,
    diversityLabel: div.label,
    biasFlagCount: response.bias_flags.length,
    citationCount,
    nepalRate: nepalFirstRate(response),
    generationMs: response.generation_time_ms,
    hasResponse: true,
  };
}

// ── LIVE: keyframe gesture smoothness (the real C3 baseline computation) ──────

export interface GestureJerk {
  gesture: GestureName;
  keyframeJerk: number;
}

export function keyframeJerks(): GestureJerk[] {
  return GESTURES.filter((g) => g !== "idle").map((g) => ({
    gesture: g,
    keyframeJerk: Math.round(meanAbsJerk(gestureTrajectory(g)) * 10) / 10,
  }));
}

// ── REFERENCE: retrieval ablation (shape only; run the harness for real) ──────

export interface RetrievalAblationDatum {
  method: string;
  ndcg5: number;
  mrr: number;
}

export const RETRIEVAL_ABLATION_REFERENCE: RetrievalAblationDatum[] = [
  { method: "BM25", ndcg5: 0.61, mrr: 0.58 },
  { method: "Dense", ndcg5: 0.68, mrr: 0.65 },
  { method: "Hybrid (RRF)", ndcg5: 0.74, mrr: 0.71 },
  { method: "Hybrid + rerank", ndcg5: 0.79, mrr: 0.77 },
];

// ── REFERENCE: bias detector P/R/F1 (shape only; run the harness for real) ────

export interface BiasDetectionDatum {
  bias: string;
  precision: number;
  recall: number;
  f1: number;
}

export const BIAS_DETECTION_REFERENCE: BiasDetectionDatum[] = [
  { bias: "Availability", precision: 0.86, recall: 0.8, f1: 0.83 },
  { bias: "Anchoring", precision: 0.82, recall: 0.78, f1: 0.8 },
  { bias: "Confirmation", precision: 0.84, recall: 0.82, f1: 0.83 },
  { bias: "Dunning–Kruger", precision: 0.79, recall: 0.74, f1: 0.76 },
  { bias: "Loss aversion", precision: 0.81, recall: 0.79, f1: 0.8 },
  { bias: "Consistency", precision: 0.83, recall: 0.8, f1: 0.81 },
];
