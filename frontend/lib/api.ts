/**
 * D.R.O.N.A. backend client (REST + WebSocket).
 *
 * The advising request path is LOCAL-ONLY on the backend (Ollama); this client
 * only ever talks to the FastAPI app in drona/api/app.py. No PII is sent — the
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
