import type { Edge, Mode, Route, Weight } from "./api";

/** A run of consecutive edges with the same mode, e.g. "train Panvel → Kharghar (3 stops)". */
export interface Segment {
  mode: Mode;
  from: string;
  to: string;
  stops: number; // number of edges in the run
}

export function segments(edges: Edge[]): Segment[] {
  const out: Segment[] = [];
  for (const e of edges) {
    const last = out[out.length - 1];
    if (last && last.mode === e.mode && last.to === e.from) {
      last.to = e.to;
      last.stops += 1;
    } else {
      out.push({ mode: e.mode, from: e.from, to: e.to, stops: 1 });
    }
  }
  return out;
}

export const WEIGHT_LABEL: Record<Weight, string> = {
  time: "Fastest",
  distance: "Shortest",
  cost: "Cheapest",
};

export const MODE_LABEL: Record<Mode, string> = {
  train: "Train",
  metro: "Metro",
  walking: "Walk",
  bus: "Bus",
  cab: "Cab",
};

/** Same station sequence => same journey, even if tagged differently. */
export function samePath(a: Route, b: Route): boolean {
  return a.path.length === b.path.length && a.path.every((s, i) => s === b.path[i]);
}

/**
 * Put the user's chosen optimisation first, keep backend order for the rest,
 * and mark routes whose path duplicates an earlier card.
 */
export function orderRoutes(routes: Route[], preferred: Weight): (Route & { duplicateOf?: Weight })[] {
  const ordered = [...routes].sort((a, b) => Number(b.optimized_for === preferred) - Number(a.optimized_for === preferred));
  return ordered.map((r, i) => {
    const earlier = ordered.slice(0, i).find((o) => samePath(o, r));
    return earlier ? { ...r, duplicateOf: earlier.optimized_for } : r;
  });
}

export function formatMinutes(min: number): string {
  if (min < 60) return `${Math.round(min)} min`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h} h ${m} min` : `${h} h`;
}
