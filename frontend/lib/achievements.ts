/**
 * Gamified progression on top of the anti-bias exploration state. XP, ranks and
 * quests are derived deterministically from what the student actually did
 * (questions asked, pathways viewed, citations opened, badges earned, evidence
 * diversity) - rewarding breadth and scepticism, never fast commitment.
 */

import { computeBadges, computeDiversity, type Badge, type ExplorationState } from "./gamification";
import type { AdvisingResponse } from "./types";

export interface RankTier {
  name: string;
  minXp: number;
  blurb: string;
}

/** Single-player progression ladder (acts as the "leaderboard" rank). */
export const RANKS: RankTier[] = [
  { name: "Curious Newcomer", minXp: 0, blurb: "Just getting started" },
  { name: "Pathway Explorer", minXp: 120, blurb: "Exploring options widely" },
  { name: "Evidence Seeker", minXp: 300, blurb: "Checking what claims rest on" },
  { name: "Bias-Aware Navigator", minXp: 550, blurb: "Seeing past the biases" },
  { name: "Master Advisor", minXp: 850, blurb: "Decides with clear eyes" },
];

export interface Quest {
  id: string;
  label: string;
  hint: string;
  current: number;
  target: number;
  xp: number;
  done: boolean;
}

export interface Progress {
  xp: number;
  level: number;
  rank: RankTier;
  next: RankTier | null;
  pctToNext: number;
  xpIntoLevel: number;
  xpForLevel: number;
  earned: number;
  total: number;
  badges: Badge[];
  diversityScore: number;
}

export function computeProgress(
  ex: ExplorationState,
  response: AdvisingResponse | null,
): Progress {
  const badges = computeBadges(ex, response);
  const earned = badges.filter((b) => b.earned).length;
  const diversityScore = response ? computeDiversity(response).score : 0;

  const xp =
    ex.queriesAsked * 20 +
    ex.pathwaysViewed.size * 12 +
    ex.citationsOpened * 8 +
    (ex.comparedPathways ? 40 : 0) +
    (ex.viewedCounterRecommendation ? 40 : 0) +
    earned * 50 +
    Math.round(diversityScore * 0.5);

  let idx = 0;
  for (let i = 0; i < RANKS.length; i++) if (xp >= RANKS[i].minXp) idx = i;
  const rank = RANKS[idx];
  const next = RANKS[idx + 1] ?? null;

  const floor = rank.minXp;
  const ceil = next ? next.minXp : rank.minXp + 1;
  const xpIntoLevel = xp - floor;
  const xpForLevel = ceil - floor;
  const pctToNext = next ? Math.min(100, Math.round((xpIntoLevel / xpForLevel) * 100)) : 100;

  return {
    xp,
    level: idx + 1,
    rank,
    next,
    pctToNext,
    xpIntoLevel,
    xpForLevel,
    earned,
    total: badges.length,
    badges,
    diversityScore,
  };
}

export function computeQuests(
  ex: ExplorationState,
  response: AdvisingResponse | null,
): Quest[] {
  const earned = computeBadges(ex, response).filter((b) => b.earned).length;
  const defs = [
    { id: "ask", label: "Ask 3 questions", hint: "Explore more than one angle", current: ex.queriesAsked, target: 3, xp: 60 },
    { id: "paths", label: "View 5 pathways", hint: "Don't fixate on the first option", current: ex.pathwaysViewed.size, target: 5, xp: 50 },
    { id: "cite", label: "Open 3 citations", hint: "Check what the advice is grounded in", current: ex.citationsOpened, target: 3, xp: 40 },
    { id: "compare", label: "Compare pathways", hint: "Weigh options side by side", current: ex.comparedPathways ? 1 : 0, target: 1, xp: 40 },
    { id: "counter", label: "See the counter-recommendation", hint: "Consider the option you'd skip", current: ex.viewedCounterRecommendation ? 1 : 0, target: 1, xp: 40 },
    { id: "badges", label: "Earn all 6 badges", hint: "Master every exploration habit", current: earned, target: 6, xp: 100 },
  ];
  return defs.map((q) => ({
    ...q,
    current: Math.min(q.current, q.target),
    done: q.current >= q.target,
  }));
}
