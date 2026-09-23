import type { Route, Weight } from "@/lib/api";
import { MODE_LABEL, WEIGHT_LABEL, formatMinutes, segments } from "@/lib/routes";

const MODE_STYLE: Record<string, string> = {
  train: "bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-100",
  metro: "bg-purple-100 text-purple-900 dark:bg-purple-900/40 dark:text-purple-100",
  walking: "bg-zinc-200 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-100",
  bus: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100",
  cab: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100",
};

interface Props {
  route: Route;
  highlighted: boolean;
  duplicateOf?: Weight;
}

export default function RouteCard({ route, highlighted, duplicateOf }: Props) {
  const segs = segments(route.edges);
  const { totals } = route;

  return (
    <article
      aria-label={`${WEIGHT_LABEL[route.optimized_for]} route`}
      className={`rounded-lg border p-4 flex flex-col gap-3 ${
        highlighted
          ? "border-black dark:border-white shadow-md"
          : "border-zinc-300 dark:border-zinc-700"
      }`}
    >
      <header className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold leading-tight">{WEIGHT_LABEL[route.optimized_for]}</h2>
          <p className="text-xs text-zinc-500">optimised for {route.optimized_for}</p>
        </div>
        {highlighted && (
          <span className="shrink-0 whitespace-nowrap text-xs rounded bg-black text-white dark:bg-white dark:text-black px-2 py-0.5">
            your pick
          </span>
        )}
      </header>

      <dl className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-zinc-500">Time</dt>
          <dd className="font-medium">{formatMinutes(totals.time)}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Distance</dt>
          <dd className="font-medium">{totals.distance} km</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Fare</dt>
          <dd className="font-medium">₹{totals.real_fare}</dd>
        </div>
      </dl>

      <ol className="flex flex-col gap-1 text-sm">
        {segs.map((s, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${MODE_STYLE[s.mode] ?? ""}`}>
              {MODE_LABEL[s.mode] ?? s.mode}
            </span>
            <span>
              {s.from} → {s.to}
              <span className="text-zinc-500">
                {" "}
                · {s.stops} {s.mode === "walking" ? (s.stops === 1 ? "leg" : "legs") : s.stops === 1 ? "stop" : "stops"}
              </span>
            </span>
          </li>
        ))}
      </ol>

      <details className="text-xs text-zinc-600 dark:text-zinc-400">
        <summary className="cursor-pointer">All {route.path.length} stations</summary>
        <p className="mt-1 leading-relaxed">{route.path.join(" → ")}</p>
      </details>

      {duplicateOf && (
        <p className="text-xs text-zinc-500">Same journey as the {WEIGHT_LABEL[duplicateOf].toLowerCase()} route.</p>
      )}
    </article>
  );
}
