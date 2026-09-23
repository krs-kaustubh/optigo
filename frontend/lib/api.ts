/**
 * Typed client for the Optigo FastAPI backend.
 *
 * Shapes mirror backend/app/graph.py and backend/app/railradar.py exactly
 * (see ARCHITECTURE.md). The API base URL comes from NEXT_PUBLIC_API_URL and
 * defaults to the local uvicorn port.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export type Mode = "train" | "metro" | "walking" | "bus" | "cab";
export type Weight = "time" | "distance" | "cost";
export const WEIGHTS: Weight[] = ["time", "distance", "cost"];

export interface Station {
  id: number;
  name: string;
  lat: number;
  lng: number;
  type?: string | null;
}

export interface Edge {
  from: string;
  to: string;
  mode: Mode;
}

export interface Totals {
  distance: number; // km
  time: number; // minutes
  cost: number; // legacy static column, not shown
  real_fare: number; // rupees, slab-based
}

export interface LiveTrain {
  train_number: string | null;
  route_name: string;
  towards: string;
  destination_code: string;
  line: string;
  departure_time: string | null;
  expected_departure: string | null;
  platform: string | null;
  status: "scheduled" | "upcoming" | "departed" | "not-started" | string;
  delay_minutes: number | null;
}

export interface LiveStatus {
  applicable: boolean;
  reason:
    | "ok"
    | "no_relevant_trains"
    | "no_train_leg"
    | "station_not_in_railradar"
    | "api_key_missing"
    | "fetch_failed"
    | string;
  boarding_station?: string;
  alighting_station?: string;
  boarding_code?: string | null;
  alighting_code?: string | null;
  line?: string | null;
  trains_on_board?: number;
  relevant_trains?: number;
  board_time?: string | null;
  error?: string;
}

export interface Route {
  path: string[];
  edges: Edge[];
  totals: Totals;
  optimized_for: Weight;
  live_trains?: LiveTrain[];
  live_status?: LiveStatus;
}

/** Error raised for non-2xx responses; `detail` is the backend's message. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, detail: string, code: string | null = null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    // fetch() rejects for both a down server and a CORS refusal (the backend only allows http://localhost:3000).
    throw new ApiError(
      0,
      `Cannot reach the backend at ${API_URL}. Is uvicorn running, and does its CORS allow ${
        typeof window === "undefined" ? "this origin" : window.location.origin
      }?`,
    );
  }
  if (res.ok) return (await res.json()) as T;

  let detail = `${res.status} ${res.statusText}`;
  let code: string | null = null;
  try {
    const body = (await res.json()) as { detail?: unknown; error?: string };
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) {
      // FastAPI validation errors
      detail = body.detail
        .map((d: { msg?: string; loc?: unknown[] }) => `${(d.loc ?? []).slice(-1)[0]}: ${d.msg}`)
        .join("; ");
    }
    code = body.error ?? null;
  } catch {
    /* non-JSON body; keep the status text */
  }
  throw new ApiError(res.status, detail, code);
}

export function fetchStations(): Promise<Station[]> {
  return request<Station[]>("/nodes");
}

export function compareRoutes(
  source: number,
  target: number,
  opts: { live?: boolean; signal?: AbortSignal } = {},
): Promise<Route[]> {
  const params = new URLSearchParams({ source: String(source), target: String(target) });
  if (opts.live) params.set("live", "true");
  return request<Route[]>(`/compare?${params}`, { signal: opts.signal });
}
