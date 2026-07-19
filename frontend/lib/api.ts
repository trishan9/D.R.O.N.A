/**
 * D.R.O.N.A. backend client (REST + WebSocket).
 *
 * The advising request path is LOCAL-ONLY on the backend (Ollama); this client
 * only ever talks to the FastAPI app in drona/api/app.py. No PII is sent - the
 * request mirrors the session-scoped, identity-free AdviseRequest schema.
 */

import type {
  AdviseRequest,
  AdvisingResponse,
  HealthResponse,
  StreamEvent,
} from "./types";

const ENV_API_URL =
  process.env.NEXT_PUBLIC_DRONA_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

/**
 * Resolve the backend base URL: device-local preference override (set on the
 * Preferences page, persisted in localStorage) wins over the build-time env
 * default. Read at call time so changing the preference takes effect live.
 */
export function apiBaseUrl(): string {
  if (typeof window !== "undefined") {
    try {
      const raw = window.localStorage.getItem("drona.session.v1");
      if (raw) {
        const override = (JSON.parse(raw) as { prefs?: { apiUrl?: string } })?.prefs?.apiUrl?.trim();
        if (override) return override.replace(/\/$/, "");
      }
    } catch {
      /* fall through to env default */
    }
  }
  return ENV_API_URL;
}

function wsBaseUrl(): string {
  return apiBaseUrl().replace(/^http/, "ws");
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${apiBaseUrl()}/health`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return (await res.json()) as HealthResponse;
}

/** Thesis evaluation results (GET /evaluation - notebook 04/05 artifacts). */
export interface AblationRow {
  method: string;
  ndcg5?: number;
  mrr?: number;
  recall5?: number;
  precision5?: number;
}
export interface BiasRow {
  bias: string;
  precision: number;
  recall: number;
  f1: number;
}
export interface PolicyRow {
  policy: string;
  success_rate: number;
  mean_jerk: number;
  mean_path?: number;
  mean_apex_err?: number;
}
export interface VerdictRow {
  component: string;
  candidates: string;
  winner: string;
  evidence: string;
}
export interface EvaluationData {
  available: boolean;
  generated?: string;
  c1_ablation?: AblationRow[];
  c2_per_type?: BiasRow[];
  c2_macro_f1?: number;
  c3_policies?: PolicyRow[];
  c4?: { nepal_citation_ratio?: number; target_met?: boolean };
  verdict?: VerdictRow[];
  llm?: {
    base_model?: string;
    base_eval_loss?: number;
    final_eval_loss?: number;
    curve?: { step: number; eval_loss: number }[];
  };
  /**
   * System-level validation (scripts/run_validation.py). Unlike C1-C4, which
   * score components, these score the ADVICE: is it grounded, and does it
   * actually counter the bias? `ablation_delta` is the controlled comparison
   * (mitigation ON minus OFF) - positive values mean the debiasing works.
   */
  validation?: {
    generated?: string;
    n_queries?: number;
    source?: string;
    hallucination?: {
      n_responses?: number;
      n_pathways?: number;
      grounded_pathway_rate?: number;
      hallucinated_citation_rate?: number;
      fully_grounded_response_rate?: number;
      mean_citations_per_pathway?: number;
    };
    bias_mitigation_on?: BiasMitigationRow;
    bias_mitigation_off?: BiasMitigationRow | null;
    ablation_delta?: Record<string, number> | null;
  };
}

export interface BiasMitigationRow {
  n_responses?: number;
  mean_pathway_diversity?: number;
  multi_pathway_rate?: number;
  mean_hedge_frequency?: number;
  counter_recommendation_rate?: number;
  refusal_rate?: number;
  bias_flag_coverage?: number;
  nepal_first_rate?: number;
}

export interface NameCount {
  name: string;
  count: number;
}

export interface SkillGapRow {
  skill: string;
  demand: number;
  covered: boolean;
  taught: number;
  gap: number;
}

/** Aggregates over the real ingested corpus (curriculum, pathways, postings). */
export interface CorpusStats {
  available: boolean;
  totals?: {
    modules: number;
    pathways: number;
    postings: number;
    total_credits: number;
    distinct_skills_demanded: number;
    employers: number;
  };
  modules_by_programme?: NameCount[];
  modules_by_year?: NameCount[];
  postings_by_tier?: NameCount[];
  pathways_by_tier?: NameCount[];
  top_employers?: NameCount[];
  top_locations?: NameCount[];
  top_skills_demanded?: NameCount[];
  skill_gap?: SkillGapRow[];
  skill_coverage_rate?: number;
}

export async function getCorpusStats(signal?: AbortSignal): Promise<CorpusStats> {
  const res = await fetch(`${apiBaseUrl()}/corpus/stats`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`Corpus stats fetch failed: ${res.status}`);
  return (await res.json()) as CorpusStats;
}

export async function getEvaluation(signal?: AbortSignal): Promise<EvaluationData> {
  const res = await fetch(`${apiBaseUrl()}/evaluation`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`Evaluation fetch failed: ${res.status}`);
  return (await res.json()) as EvaluationData;
}

/** Synchronous advising (no streaming). Used as a fallback when WS is blocked. */
export async function advise(req: AdviseRequest, signal?: AbortSignal): Promise<AdvisingResponse> {
  const res = await fetch(`${apiBaseUrl()}/advise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Advising failed (${res.status}): ${detail}`);
  }
  return (await res.json()) as AdvisingResponse;
}

export interface StreamHandlers {
  onNode?: (node: string, label: string) => void;
  onResult?: (response: AdvisingResponse) => void;
  onError?: (detail: string) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

/**
 * Stream an advising request over the websocket. Returns a cancel function.
 *
 * Protocol (drona/api/app.py): client sends one AdviseRequest JSON, the server
 * streams {event:"node"} progress events then {event:"result"} (or {event:"error"}).
 */
export function streamAdvise(req: AdviseRequest, handlers: StreamHandlers): () => void {
  let closed = false;
  const ws = new WebSocket(`${wsBaseUrl()}/ws/advise`);

  ws.onopen = () => {
    handlers.onOpen?.();
    ws.send(JSON.stringify(req));
  };

  ws.onmessage = (ev) => {
    let data: StreamEvent;
    try {
      data = JSON.parse(ev.data) as StreamEvent;
    } catch {
      handlers.onError?.("Malformed event from server");
      return;
    }
    if (data.event === "node") handlers.onNode?.(data.node, data.label);
    else if (data.event === "result") handlers.onResult?.(data.response);
    else if (data.event === "error") handlers.onError?.(data.detail);
  };

  ws.onerror = () => {
    if (!closed) handlers.onError?.("WebSocket connection error");
  };

  ws.onclose = () => {
    closed = true;
    handlers.onClose?.();
  };

  return () => {
    closed = true;
    try {
      ws.close();
    } catch {
      /* noop */
    }
  };
}
