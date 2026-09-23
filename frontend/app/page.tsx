"use client";

import { FormEvent, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ApiError, API_URL, WEIGHTS, compareRoutes, fetchStations, type Route, type Station, type Weight } from "@/lib/api";
import { WEIGHT_LABEL, orderRoutes } from "@/lib/routes";
import RouteCard from "./components/RouteCard";

const DEFAULT_SOURCE = 11; // Panvel
const DEFAULT_TARGET = 1; // Vashi

function parseId(raw: string | null): number | null {
  const n = Number(raw);
  return raw !== null && Number.isInteger(n) && n > 0 ? n : null;
}

/** useSearchParams needs a Suspense boundary for static prerendering. */
export default function Page() {
  return (
    <Suspense fallback={null}>
      <Home />
    </Suspense>
  );
}

function Home() {
  // Shareable links: /?from=11&to=1&for=cost pre-fills the form and runs the search on load.
  const params = useSearchParams();
  const initialFrom = parseId(params.get("from"));
  const initialTo = parseId(params.get("to"));
  const initialWeight = params.get("for");

  const [stations, setStations] = useState<Station[] | null>(null);
  const [stationsError, setStationsError] = useState<string | null>(null);

  const [source, setSource] = useState<number>(initialFrom ?? DEFAULT_SOURCE);
  const [target, setTarget] = useState<number>(initialTo ?? DEFAULT_TARGET);
  const [weight, setWeight] = useState<Weight>(
    initialWeight && (WEIGHTS as string[]).includes(initialWeight) ? (initialWeight as Weight) : "time",
  );

  const [routes, setRoutes] = useState<Route[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async (from: number, to: number) => {
    setLoading(true);
    setError(null);
    try {
      setRoutes(await compareRoutes(from, to));
    } catch (err) {
      setRoutes(null);
      setError(err instanceof ApiError || err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStations()
      .then(setStations)
      .catch((e: unknown) => setStationsError(e instanceof Error ? e.message : String(e)));
  }, []);

  // Run the search once on mount when the URL carried both endpoints.
  const autoSearched = useRef(false);
  useEffect(() => {
    if (autoSearched.current || initialFrom === null || initialTo === null) return;
    autoSearched.current = true;
    void search(initialFrom, initialTo);
  }, [initialFrom, initialTo, search]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const q = new URLSearchParams({ from: String(source), to: String(target), for: weight });
    window.history.replaceState(null, "", `?${q}`);
    void search(source, target);
  }

  const nameOf = (id: number) => stations?.find((s) => s.id === id)?.name ?? `#${id}`;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8 flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-bold">Optigo</h1>
        <p className="text-sm text-zinc-500">Navi Mumbai multimodal route finder · backend {API_URL}</p>
      </header>

      <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] items-end">
        <label className="flex flex-col gap-1 text-sm">
          From
          <StationSelect stations={stations} value={source} onChange={setSource} disabled={!stations} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          To
          <StationSelect stations={stations} value={target} onChange={setTarget} disabled={!stations} />
        </label>
        <button
          type="submit"
          disabled={loading || !stations}
          className="rounded bg-black px-4 py-2 text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          {loading ? "Finding…" : "Find routes"}
        </button>

        <fieldset className="sm:col-span-3 flex flex-wrap gap-4 text-sm">
          <legend className="sr-only">Optimise for</legend>
          <span className="text-zinc-500">Optimise for</span>
          {WEIGHTS.map((w) => (
            <label key={w} className="flex items-center gap-1">
              <input type="radio" name="weight" value={w} checked={weight === w} onChange={() => setWeight(w)} />
              {WEIGHT_LABEL[w]}
            </label>
          ))}
        </fieldset>
      </form>

      {stationsError && (
        <Notice tone="error">
          Could not load the station list: {stationsError}
        </Notice>
      )}
      {error && <Notice tone="error">{error}</Notice>}

      {routes && (
        <section aria-live="polite" className="flex flex-col gap-4">
          <h2 className="text-sm text-zinc-500">
            {nameOf(source)} → {nameOf(target)} · {routes.length} candidates
          </h2>
          <div className="grid gap-4 md:grid-cols-3">
            {orderRoutes(routes, weight).map((r) => (
              <RouteCard
                key={r.optimized_for}
                route={r}
                highlighted={r.optimized_for === weight}
                duplicateOf={r.duplicateOf}
              />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

function StationSelect({
  stations,
  value,
  onChange,
  disabled,
}: {
  stations: Station[] | null;
  value: number;
  onChange: (id: number) => void;
  disabled?: boolean;
}) {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(Number(e.target.value))}
      className="rounded border border-zinc-300 bg-transparent px-2 py-2 dark:border-zinc-700"
    >
      {stations ? (
        stations.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
            {s.type ? ` (${s.type.includes("metro") && !s.type.includes("rail") ? "metro" : "rail"})` : ""}
          </option>
        ))
      ) : (
        <option value={value}>Loading stations…</option>
      )}
    </select>
  );
}

function Notice({ tone, children }: { tone: "error" | "info"; children: React.ReactNode }) {
  const cls =
    tone === "error"
      ? "border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950/40 dark:text-red-100"
      : "border-zinc-300 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900";
  return (
    <p role={tone === "error" ? "alert" : undefined} className={`rounded border px-3 py-2 text-sm ${cls}`}>
      {children}
    </p>
  );
}
