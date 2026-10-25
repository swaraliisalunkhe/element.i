import type {
  AgentEvent, ApiErrorBody, BugReport, Journey, Run, RunCreate, TestWithResult,
} from "./types";
import { EVENT_TYPES } from "./types";
import { mockBug, mockEvents, mockJourney, mockRun, mockRuns, mockTest } from "@/mocks/mock-data";

const rawBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const API_BASE = (
  rawBase.startsWith("http://") || rawBase.startsWith("https://")
    ? rawBase
    : `https://${rawBase}`
).replace(/\/+$/, "");
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch (err: unknown) {
    const detail = err instanceof Error ? err.message : String(err);
    throw new Error(`Cannot reach the backend at ${API_BASE} (${detail}). Ensure the backend is running and CORS is configured.`);
  }
  let body: unknown = null;
  try { body = await res.json(); } catch { /* handled below */ }
  if (!res.ok) {
    const msg = (body as ApiErrorBody | null)?.error?.message;
    throw new Error(msg ?? `The backend returned HTTP ${res.status}.`);
  }
  // Successful responses are bare objects per the contracts; tolerate a {data, error} wrapper just in case.
  if (body && typeof body === "object" && "data" in body && !("id" in body)) {
    return (body as { data: T }).data;
  }
  return body as T;
}

const later = <T,>(v: T) => new Promise<T>((r) => setTimeout(() => r(v), 150));

export const listRuns = (): Promise<Run[]> => (USE_MOCKS ? later(mockRuns) : request("/api/runs"));
export const getRun = (id: string): Promise<Run> => (USE_MOCKS ? later(mockRun) : request(`/api/runs/${id}`));
export const getJourneys = (id: string): Promise<Journey[]> => (USE_MOCKS ? later([mockJourney]) : request(`/api/runs/${id}/journeys`));
export const getTests = (id: string): Promise<TestWithResult[]> => (USE_MOCKS ? later([mockTest]) : request(`/api/runs/${id}/tests`));
export const getBugs = (id: string): Promise<BugReport[]> => (USE_MOCKS ? later([mockBug]) : request(`/api/runs/${id}/bugs`));

export const createRun = (payload: RunCreate): Promise<Run> =>
  USE_MOCKS ? later(mockRun) : request("/api/runs", { method: "POST", body: JSON.stringify(payload) });

/** Evidence `url` already starts with /api/evidence/, or is a data URI in mock mode. */
export const evidenceSrc = (url: string): string => {
  if (url.startsWith("data:") || url.startsWith("blob:") || url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  return `${API_BASE}${url}`;
};

export interface StreamHandlers {
  onEvent: (e: AgentEvent) => void;
  onEnd: () => void;          // stream_end received: refetch run, tests and bugs
  onConnectionLost: () => void;
  onConnectionRestored: () => void;
}

/** Subscribe to GET /api/runs/{id}/stream. Returns an unsubscribe function. */
export function subscribeRunEvents(runId: string, h: StreamHandlers): () => void {
  if (USE_MOCKS) {
    let i = 0;
    const t = setInterval(() => {
      if (i < mockEvents.length) h.onEvent(mockEvents[i++]);
      else { clearInterval(t); h.onEnd(); }
    }, 700);
    return () => clearInterval(t);
  }
  const es = new EventSource(`${API_BASE}/api/runs/${runId}/stream`);
  let closed = false;
  const close = () => { closed = true; es.close(); };

  for (const type of EVENT_TYPES) {
    es.addEventListener(type, (m) => {
      try { h.onEvent(JSON.parse((m as MessageEvent).data) as AgentEvent); } catch { /* ignore malformed */ }
    });
  }
  es.addEventListener("stream_end", () => { close(); h.onEnd(); });
  es.onopen = () => h.onConnectionRestored();
  es.onerror = () => { if (!closed) h.onConnectionLost(); }; // the browser reconnects with Last-Event-ID
  return close;
}
