/**
 * Anti-bias gamification logic (pure functions).
 *
 * The proposal's core HCI contribution is that the UI actively *counters*
 * cognitive biases rather than reinforcing them. These helpers turn an
 * AdvisingResponse + the student's exploration behaviour into:
 *
 *   - a pathway-diversity score        (counters availability/anchoring)
 *   - exploration badges               (rewards breadth, not commitment)
 *   - a skill-tree                     (shows the curriculum graph, not a ladder)
 *   - a counter-recommendation pick    (counters confirmation bias)
 *   - reversibility classification     (counters loss-aversion / over-commitment)
 *
 * Everything is deterministic and side-effect free so it can be unit-reasoned
 * about and matches the backend's transparency philosophy.
 */

import type {
  AdvisingResponse,
  DataTier,
  PathwayRecommendation,
} from "./types";

// ── Pathway diversity (anti-anchoring) ────────────────────────────────────────

export interface DiversityScore {
  /** 0–100. Higher = more diverse set of pathways surfaced. */
  score: number;
  pathwayCount: number;
  distinctTiers: number;
  tierBreakdown: Record<DataTier, number>;
  label: "narrow" | "moderate" | "broad";
}

export function computeDiversity(response: AdvisingResponse): DiversityScore {
  const tierBreakdown: Record<DataTier, number> = {
    nepal: 0,
    regional: 0,
    international: 0,
    synthetic: 0,
  };
  for (const p of response.pathways) {
    for (const c of p.citations) tierBreakdown[c.tier] += 1;
  }
  const distinctTiers = (Object.keys(tierBreakdown) as DataTier[]).filter(
    (t) => tierBreakdown[t] > 0,
  ).length;
  const pathwayCount = response.pathways.length;

  // Weight: pathway count (anti single-option anchoring) + tier spread.
  const countScore = Math.min(pathwayCount / 3, 1) * 60;
  const tierScore = (distinctTiers / 3) * 40; // synthetic excluded from the cap intent
  const score = Math.round(Math.min(countScore + tierScore, 100));

  const label = score >= 70 ? "broad" : score >= 40 ? "moderate" : "narrow";
  return { score, pathwayCount, distinctTiers, tierBreakdown, label };
}

// ── Exploration tracking + badges (rewards breadth) ───────────────────────────

export interface ExplorationState {
  pathwaysViewed: Set<string>;
  citationsOpened: number;
  comparedPathways: boolean;
  viewedCounterRecommendation: boolean;
  queriesAsked: number;
}

export function emptyExploration(): ExplorationState {
  return {
    pathwaysViewed: new Set(),
    citationsOpened: 0,
    comparedPathways: false,
    viewedCounterRecommendation: false,
    queriesAsked: 0,
  };
}

export interface Badge {
  id: string;
  title: string;
  description: string;
  icon: "compass" | "scale" | "search" | "shuffle" | "globe" | "sparkles";
  earned: boolean;
}

export function computeBadges(
  exploration: ExplorationState,
  response: AdvisingResponse | null,
): Badge[] {
  const distinctTiers = response ? computeDiversity(response).distinctTiers : 0;
  return [
    {
      id: "explorer",
      title: "Explorer",
      description: "Viewed 3+ different pathways instead of fixating on one.",
      icon: "compass",
      earned: exploration.pathwaysViewed.size >= 3,
    },
    {
      id: "comparer",
      title: "Side-by-Side Thinker",
      description: "Compared pathways head-to-head before deciding.",
      icon: "scale",
      earned: exploration.comparedPathways,
    },
    {
      id: "evidence",
      title: "Evidence Seeker",
      description: "Opened citations to check what each claim is grounded in.",
      icon: "search",
      earned: exploration.citationsOpened >= 3,
    },
    {
      id: "openminded",
      title: "Open Mind",
      description: "Considered the counter-recommendation that challenges your stated interest.",
      icon: "shuffle",
      earned: exploration.viewedCounterRecommendation,
    },
    {
      id: "global-local",
      title: "Local & Global",
      description: "Saw pathways grounded in both Nepali and international evidence.",
      icon: "globe",
      earned: distinctTiers >= 2,
    },
    {
      id: "curious",
      title: "Curious",
      description: "Asked more than one question this session.",
      icon: "sparkles",
      earned: exploration.queriesAsked >= 2,
    },
  ];
}

// ── Skill tree (curriculum graph, not a ranked ladder) ────────────────────────

export interface SkillNode {
  id: string;
  label: string;
  /** "have" = declared/completed; "target" = needed by a pathway; "both". */
  status: "have" | "target" | "both";
  pathways: string[];
}

export function buildSkillTree(
  response: AdvisingResponse | null,
  have: string[],
): SkillNode[] {
  const haveSet = new Set(have.map((s) => s.trim().toLowerCase()).filter(Boolean));
  const nodes = new Map<string, SkillNode>();

  const ensure = (label: string): SkillNode => {
    const id = label.trim().toLowerCase();
    if (!nodes.has(id)) {
      nodes.set(id, { id, label: label.trim(), status: "target", pathways: [] });
    }
    return nodes.get(id)!;
  };

  for (const h of have) {
    if (!h.trim()) continue;
    const n = ensure(h);
    n.status = "have";
  }

  if (response) {
    for (const p of response.pathways) {
      for (const m of p.matched_softwarica_modules) {
        const n = ensure(m);
        if (!n.pathways.includes(p.pathway_title)) n.pathways.push(p.pathway_title);
        const isHave = haveSet.has(n.id);
        n.status = isHave ? "both" : n.status === "have" ? "both" : "target";
      }
    }
  }

  return Array.from(nodes.values()).sort((a, b) => a.label.localeCompare(b.label));
}

// ── Counter-recommendation (anti-confirmation) ────────────────────────────────

/**
 * Pick the pathway LEAST aligned with the student's declared interests — the
 * one a confirmation-biased reader would skip. Returns null if <2 pathways.
 */
export function selectCounterRecommendation(
  response: AdvisingResponse | null,
  declaredInterests: string[],
): PathwayRecommendation | null {
  if (!response || response.pathways.length < 2) return null;
  const interests = declaredInterests.map((i) => i.toLowerCase()).filter(Boolean);
  if (interests.length === 0) {
    // No stated interest → surface the lowest-confidence pathway as the stretch.
    const order: Record<string, number> = { high: 3, medium: 2, low: 1 };
    return [...response.pathways].sort(
      (a, b) => order[a.confidence] - order[b.confidence],
    )[0];
  }

  const overlap = (p: PathwayRecommendation): number => {
    const hay = (
      p.pathway_title +
      " " +
      p.rationale +
      " " +
      p.matched_softwarica_modules.join(" ")
    ).toLowerCase();
    return interests.reduce((acc, i) => acc + (hay.includes(i) ? 1 : 0), 0);
  };

  return [...response.pathways].sort((a, b) => overlap(a) - overlap(b))[0];
}

// ── Reversibility (anti loss-aversion / over-commitment) ──────────────────────

export type Reversibility = "reversible" | "irreversible";

const IRREVERSIBLE_HINTS = [
  "drop out",
  "quit",
  "leave the program",
  "abroad",
  "migrate",
  "loan",
  "pay for",
  "enroll in a degree",
  "switch major",
  "relocate",
  "sign",
  "commit to",
];

const REVERSIBLE_HINTS = [
  "try",
  "explore",
  "take a course",
  "build a project",
  "join a club",
  "talk to",
  "shadow",
  "read",
  "attend",
  "experiment",
  "prototype",
  "internship",
  "volunteer",
];

export interface ClassifiedStep {
  text: string;
  reversibility: Reversibility;
}

export function classifyStep(step: string): Reversibility {
  const s = step.toLowerCase();
  if (IRREVERSIBLE_HINTS.some((h) => s.includes(h))) return "irreversible";
  if (REVERSIBLE_HINTS.some((h) => s.includes(h))) return "reversible";
  // Default: most concrete advising steps are low-stakes / reversible.
  return "reversible";
}

export function classifySteps(steps: string[]): ClassifiedStep[] {
  return steps.map((text) => ({ text, reversibility: classifyStep(text) }));
}

// ── Tier presentation helpers ─────────────────────────────────────────────────

export const TIER_META: Record<
  DataTier,
  { label: string; className: string; dot: string }
> = {
  nepal: {
    label: "Nepal",
    className: "border-tier-nepal/40 bg-tier-nepal/10 text-tier-nepal",
    dot: "bg-tier-nepal",
  },
  regional: {
    label: "Regional",
    className: "border-tier-regional/40 bg-tier-regional/10 text-tier-regional",
    dot: "bg-tier-regional",
  },
  international: {
    label: "International",
    className: "border-tier-international/40 bg-tier-international/10 text-tier-international",
    dot: "bg-tier-international",
  },
  synthetic: {
    label: "Synthetic",
    className: "border-tier-synthetic/40 bg-tier-synthetic/10 text-tier-synthetic",
    dot: "bg-tier-synthetic",
  },
};

export const BIAS_LABELS: Record<string, string> = {
  availability_heuristic: "Availability heuristic",
  anchoring: "Anchoring",
  confirmation: "Confirmation bias",
  dunning_kruger: "Dunning–Kruger",
  loss_aversion: "Loss aversion",
  consistency: "Consistency bias",
};
