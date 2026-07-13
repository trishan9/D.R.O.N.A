/**
 * TypeScript mirrors of the D.R.O.N.A. Pydantic contracts
 * (drona/contracts/__init__.py and drona/api/schemas.py).
 *
 * Kept deliberately in sync with the backend wire format produced by
 * `AdvisingResponse.model_dump(mode="json")`. If the contracts change,
 * update this file.
 */

export type DataTier = "nepal" | "regional" | "international" | "synthetic";

export type Confidence = "low" | "medium" | "high";

export type AspirationGeography = "nepal" | "regional" | "international" | "any";

export type BiasType =
  | "availability_heuristic"
  | "anchoring"
  | "confirmation"
  | "dunning_kruger"
  | "loss_aversion"
  | "consistency";

export interface RetrievalCitation {
  source_type: "curriculum" | "job_posting" | "career_pathway" | "report" | "synthetic";
  source_id: string;
  tier: DataTier;
  excerpt: string;
  relevance_score: number;
}

export interface PathwayRecommendation {
  pathway_title: string;
  rationale: string;
  matched_softwarica_modules: string[];
  local_market_evidence: string | null;
  international_context: string | null;
  next_concrete_steps: string[];
  citations: RetrievalCitation[];
  confidence: Confidence;
}

export interface BiasFlag {
  bias_type: BiasType;
  detected_signal: string;
  mitigation_applied: string;
}

export interface AdvisingResponse {
  timestamp: string;
  frame_id: string;
  query_id: string;
  summary: string;
  pathways: PathwayRecommendation[];
  bias_flags: BiasFlag[];
  refusal: boolean;
  refusal_reason: string | null;
  speak_text: string;
  requires_human_followup: boolean;
  generation_time_ms: number | null;
}

/** Softwarica bachelor programmes the platform supports. */
export type Programme = "software_engineering" | "ethical_hacking" | "csai";

export const PROGRAMME_LABELS: Record<Programme, string> = {
  software_engineering: "Software Engineering (formerly Computing)",
  ethical_hacking: "Ethical Hacking & Cybersecurity",
  csai: "CS with Artificial Intelligence",
};

/** Matches drona/api/schemas.py::AdviseRequest (PII-free, session-scoped). */
export interface AdviseRequest {
  query_text: string;
  session_id?: string | null;
  programme?: Programme;
  year_of_study?: number | null;
  completed_modules: string[];
  declared_interests: string[];
  declared_skills: string[];
  self_assessed_skill_levels: Record<string, number>;
  aspirations: string[];
  aspiration_geography: AspirationGeography;
  max_pathways: number;
  require_local_first: boolean;
}

/**
 * Session-scoped profile the UI builds. Never persisted, never identity-linked.
 * Combined with the chat query_text to form an AdviseRequest.
 */
export interface ProfileDraft {
  session_id: string;
  programme: Programme;
  year_of_study: number | null;
  completed_modules: string[];
  declared_interests: string[];
  declared_skills: string[];
  self_assessed_skill_levels: Record<string, number>;
  aspirations: string[];
  aspiration_geography: AspirationGeography;
  max_pathways: number;
  require_local_first: boolean;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  llm_available: boolean;
  orchestrator: string;
  vector_backend: string;
}

/** Streaming events from WS /ws/advise (drona/api/streaming.py). */
export type StreamEvent =
  | { event: "node"; node: string; label: string }
  | { event: "result"; response: AdvisingResponse }
  | { event: "error"; detail: string };
