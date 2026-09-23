# Optigo Frontend

Next.js 16 (app router) · React 19 · Tailwind 4 · TypeScript. One screen that drives the Optigo backend: pick a source and destination, choose what to optimise for, and see the three route candidates.

> Project overview and API reference → [root README](../README.md).

## Run

```bash
npm install
npm run dev            # Turbopack, http://localhost:3000
npm run dev:webpack    # fallback if `next dev` exits silently
npm run build && npm run start
npm run lint
npx tsc --noEmit
```

The backend must be running on `http://localhost:8000` (or set `NEXT_PUBLIC_API_URL`). The backend's CORS list allows **only** `http://localhost:3000`, so run the frontend on that port.

## Structure

```
app/
├── page.tsx                  client component: station pickers (from /nodes), optimise-for radio,
│                             submit, 3 RouteCards, error notice; reads ?from&to&for on load
├── layout.tsx                fonts + metadata
└── components/RouteCard.tsx  one candidate: time / distance / fare, mode segments, station list
lib/
├── api.ts                    typed client — fetchStations(), compareRoutes(); ApiError; all response types
└── routes.ts                 pure helpers — segments(), orderRoutes(), samePath(), formatMinutes(), labels
```

## Behaviour

- **Optimise for** does not change the request; `/compare` always returns all three. It orders the cards (chosen first, tagged "your pick"). A card whose path duplicates an earlier one says "Same journey as the … route".
- **Shareable links:** `/?from=11&to=1&for=cost` pre-fills and runs the search; submitting writes the same params to the URL.
- **Errors** from the backend are shown verbatim (`unknown node id 999`, `source and target are the same node (1)`). A fetch failure shows "Cannot reach the backend at … Is uvicorn running, and does its CORS allow <origin>?" — the same message covers a down server and a CORS refusal.
- **Live status** (`live_trains`, `live_status`) is typed in `lib/api.ts` but not rendered yet — that is Phase 3.

## Verified

`tsc`, `eslint` and `next build` are clean. Headless-Chrome renders against the live backend were checked for: home (24 stations load), Panvel→Vashi, Belapur→Pendhar, same-node and unknown-node errors.
