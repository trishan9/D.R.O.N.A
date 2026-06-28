"use client";

/**
 * App-wide session store (React context + localStorage).
 *
 * Holds the student's session-scoped profile, the most recent advising
 * response, exploration progress (for anti-bias gamification), a query history,
 * and device-local UI preferences. State flows across pages so the Advisor's
 * result powers Pathways, Skills, Achievements, and Analytics.
 *
 * PRIVACY: everything here is DEVICE-LOCAL (browser localStorage) and never sent
 * anywhere except the PII-free AdviseRequest the user explicitly submits. There
 * is no server-side account or persistence. A nickname/avatar is an optional,
 * self-chosen label - not identity, never transmitted.
 */

import * as React from "react";

import type { AdvisingResponse, ProfileDraft } from "./types";
import { emptyExploration, type ExplorationState } from "./gamification";

const STORAGE_KEY = "drona.session.v1";

export interface QueryHistoryItem {
  id: string;
  query: string;
  ts: number;
  summary: string;
  pathwayCount: number;
  biasCount: number;
  refusal: boolean;
  generationMs: number | null;
}

export interface AppPrefs {
  /** Optional, self-chosen display name (device-local label, not identity). */
  displayName: string;
  /** Seed for the generated avatar (no photo, no PII). */
  avatarSeed: string;
  /** Optional backend override; empty = use NEXT_PUBLIC_DRONA_API_URL default. */
  apiUrl: string;
  /** rosbridge websocket URL for live ROS2 control. */
  rosbridgeUrl: string;
}

export function newProfile(): ProfileDraft {
  return {
    session_id: typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`,
    year_of_study: null,
    completed_modules: [],
    declared_interests: [],
    declared_skills: [],
    self_assessed_skill_levels: {},
    aspirations: [],
    aspiration_geography: "any",
    max_pathways: 3,
    require_local_first: true,
  };
}

function defaultPrefs(): AppPrefs {
  return { displayName: "", avatarSeed: "drona", apiUrl: "", rosbridgeUrl: "ws://localhost:9090" };
}

interface PersistShape {
  profile: ProfileDraft;
  response: AdvisingResponse | null;
  exploration: { pathwaysViewed: string[]; citationsOpened: number; comparedPathways: boolean; viewedCounterRecommendation: boolean; queriesAsked: number };
  history: QueryHistoryItem[];
  prefs: AppPrefs;
}

interface AppStore {
  profile: ProfileDraft;
  response: AdvisingResponse | null;
  exploration: ExplorationState;
  history: QueryHistoryItem[];
  prefs: AppPrefs;
  hydrated: boolean;
  setProfile: (p: ProfileDraft | ((prev: ProfileDraft) => ProfileDraft)) => void;
  resetProfile: () => void;
  setResponse: (r: AdvisingResponse | null) => void;
  recordQuery: (query: string, r: AdvisingResponse) => void;
  bumpExploration: (fn: (e: ExplorationState) => ExplorationState) => void;
  markPathwayViewed: (title: string) => void;
  clearHistory: () => void;
  setPrefs: (p: Partial<AppPrefs>) => void;
  resetAll: () => void;
}

const Ctx = React.createContext<AppStore | null>(null);

function loadPersisted(): Partial<PersistShape> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as PersistShape) : null;
  } catch {
    return null;
  }
}

export function AppStoreProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfileState] = React.useState<ProfileDraft>(newProfile);
  const [response, setResponseState] = React.useState<AdvisingResponse | null>(null);
  const [exploration, setExploration] = React.useState<ExplorationState>(emptyExploration);
  const [history, setHistory] = React.useState<QueryHistoryItem[]>([]);
  const [prefs, setPrefsState] = React.useState<AppPrefs>(defaultPrefs);
  const [hydrated, setHydrated] = React.useState(false);

  // Hydrate from localStorage after mount (avoids SSR hydration mismatch).
  React.useEffect(() => {
    const data = loadPersisted();
    if (data) {
      if (data.profile) setProfileState({ ...newProfile(), ...data.profile });
      if (data.response) setResponseState(data.response);
      if (data.exploration) {
        setExploration({
          pathwaysViewed: new Set(data.exploration.pathwaysViewed ?? []),
          citationsOpened: data.exploration.citationsOpened ?? 0,
          comparedPathways: data.exploration.comparedPathways ?? false,
          viewedCounterRecommendation: data.exploration.viewedCounterRecommendation ?? false,
          queriesAsked: data.exploration.queriesAsked ?? 0,
        });
      }
      if (data.history) setHistory(data.history);
      if (data.prefs) setPrefsState({ ...defaultPrefs(), ...data.prefs });
    }
    setHydrated(true);
  }, []);

  // Persist on any change (after hydration).
  React.useEffect(() => {
    if (!hydrated || typeof window === "undefined") return;
    const shape: PersistShape = {
      profile,
      response,
      exploration: {
        pathwaysViewed: Array.from(exploration.pathwaysViewed),
        citationsOpened: exploration.citationsOpened,
        comparedPathways: exploration.comparedPathways,
        viewedCounterRecommendation: exploration.viewedCounterRecommendation,
        queriesAsked: exploration.queriesAsked,
      },
      history,
      prefs,
    };
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(shape));
    } catch {
      /* quota / private mode - non-fatal */
    }
  }, [profile, response, exploration, history, prefs, hydrated]);

  const setProfile: AppStore["setProfile"] = (p) =>
    setProfileState((prev) => (typeof p === "function" ? (p as (x: ProfileDraft) => ProfileDraft)(prev) : p));

  const bumpExploration: AppStore["bumpExploration"] = (fn) =>
    setExploration((e) => fn({ ...e, pathwaysViewed: new Set(e.pathwaysViewed) }));

  const markPathwayViewed: AppStore["markPathwayViewed"] = (title) =>
    bumpExploration((e) => {
      e.pathwaysViewed.add(title);
      return e;
    });

  const recordQuery: AppStore["recordQuery"] = (query, r) => {
    setResponseState(r);
    setHistory((h) =>
      [
        {
          id: r.query_id || `${Date.now()}`,
          query,
          ts: Date.now(),
          summary: r.summary,
          pathwayCount: r.pathways.length,
          biasCount: r.bias_flags.length,
          refusal: r.refusal,
          generationMs: r.generation_time_ms,
        },
        ...h,
      ].slice(0, 50),
    );
  };

  const value: AppStore = {
    profile,
    response,
    exploration,
    history,
    prefs,
    hydrated,
    setProfile,
    resetProfile: () => setProfileState(newProfile()),
    setResponse: setResponseState,
    recordQuery,
    bumpExploration,
    markPathwayViewed,
    clearHistory: () => setHistory([]),
    setPrefs: (p) => setPrefsState((prev) => ({ ...prev, ...p })),
    resetAll: () => {
      setProfileState(newProfile());
      setResponseState(null);
      setExploration(emptyExploration());
      setHistory([]);
      setPrefsState(defaultPrefs());
    },
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): AppStore {
  const ctx = React.useContext(Ctx);
  if (!ctx) throw new Error("useStore must be used within <AppStoreProvider>");
  return ctx;
}
