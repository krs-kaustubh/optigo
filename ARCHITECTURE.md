# Optigo — Architecture & Backend Reference

**Verified directly against source (commit `3f8b4d8d`, then re-audited on 2026-09-23 with every finding fixed), not against prior docs. This file is the ground truth; the READMEs were brought in line with it on 2026-09-23.**

Related docs: `README.md` (overview + API reference, tracked) · `backend/README.md` · `future-ideas.md` (tracked; Ideas 1–2) · `handoff.md` (frontend handoff, gitignored) · `plan.md` (phase status) · `log.md` (work log) · `REPO.md` (access/run).

## Structure
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           FastAPI app, CORS, route handlers, error → HTTP status handlers
│   ├── graph.py          Supabase client (keepalive-tuned), graph builder, Dijkstra, fare calc, error types
│   ├── railradar.py      RailRadar client: live station board + corridor model + relevance filter
│   ├── alternatives.py   Shared alternatives engine: backing (Idea 1) & forward switching (Idea 2)
│   └── cabs.py           Cab provider layer: calibrated fares & deep links (Uber, Ola, Rapido, Auto)
├── tests/
│   ├── test_railradar.py              29 tests
│   ├── test_routing_errors.py         20 tests (fixture graph, Supabase mocked)
│   ├── test_phase_b_railradar.py      12 tests (all 8 corridor journeys + edge cases)
│   ├── test_phase_c_alternatives.py    8 tests (backing, switching, cap, filters, endpoint)
│   └── test_cabs.py                   11 tests (fare models, road distance, deep links, endpoint)
├── requirements.txt       the pin list (root requirements.txt forwards here)
└── .env                   (gitignored — never committed)
frontend/                  Next.js 16 — see "Frontend" below
```

## Endpoints (actual, from `main.py`)

**5** endpoints: `/health`, `/nodes`, `/route`, `/compare`, `/cabs/estimate`.

### `GET /health`
Returns `{"status": "ok"}`.

### `GET /nodes`
All stations sorted by id: `[{"id", "name", "lat", "lng", "type"}]`. `type` is the DB label (`rail`, `metro`, `rail_junction`, `rail_metro_uran_interchange`, `rail_uran_origin`). Backed by `graph.list_nodes()` → one Supabase RPC call.

### `GET /route?source&target&weight`
- `source`, `target`: int, default 1 / 5
- `weight`: `time` (default) · `distance` · `cost` — validated as a `Literal`; anything else is a 422 from FastAPI
- Calls `graph.shortest_path()`
- Response shape: `{"path": [...], "edges": [...], "totals": {"distance", "time", "cost", "real_fare"}}` — totals are **nested**, not flat top-level keys.
- Note: `weight=cost` optimizes on the legacy static `cost` column of the edges table, not on `real_fare`.

### `GET /compare?source&target&live&prefer_seat`
- Calls `graph.compare_routes()`.
- If `live=true` or `prefer_seat=true`: calls `railradar.annotate_route_with_live_status(route, limit=3)` on each route.
- If `prefer_seat=true`: calls `alternatives.annotate_route_with_alternatives(route, prefer_seat=True)` on each route.
- Always returns exactly 3 routes on success (they may share the same path; see below). Never returns `[]`.

### `GET /cabs/estimate?pickup_lat&pickup_lng&dropoff_lat&dropoff_lng`
- Also accepts station IDs helper: `?source_station_id=1&target_station_id=6`.
- Calls `cabs.get_all_cab_estimates(...)`.
- Returns side-by-side fare estimates, ETAs, and universal deep links for **Uber** (Auto, Go, Premier), **Ola** (Auto, Mini, Prime Sedan), **Rapido** (Bike, Auto), and **Auto Rickshaw** (metered).
- Returns 422 if neither coordinate quartet nor station ID pair is provided.

### Error responses (added 2026-09-23)
`graph.py` raises `RoutingError` subclasses; `main.py` maps them to JSON `{"detail": "...", "error": "<ClassName>"}`:

| Case | Error | Status |
|---|---|---|
| node id not in graph | `UnknownNode` | 404 |
| no path between the nodes | `NoPath` | 404 |
| `source == target` | `SameNode` | 400 |
| bad `weight` (via `/route`) | FastAPI `Literal` validation | 422 |
| non-integer `source`/`target` | FastAPI validation | 422 |
| Supabase transport error (stale connection, unreachable) after one retry | `UpstreamError` | 502 |
| any other unexpected exception | propagates | 500 |

Previously `/route` returned a bare 500 for bad weight or unknown node, and `/compare` swallowed every exception (including Supabase outages) into an empty `[]` with HTTP 200.

## `graph.py` — routing logic

- Exceptions: `RoutingError` → `InvalidWeight`, `UnknownNode`, `SameNode`, `NoPath`. `build_graph()` validates `weight`; `_find_path()` validates endpoints and converts `NetworkXNoPath`. `UpstreamError` wraps Supabase transport failures.
- Supabase client (module-level, created at import from `SUPABASE_URL`/`SUPABASE_KEY`) uses a custom `httpx.Client` with `keepalive_expiry=15s`, because Supabase closes idle connections and reusing a stale pooled connection raised `httpx.RemoteProtocolError: Server disconnected` (seen 2026-09-23 as sporadic 500s on the first request after a pause). `fetch_nodes()`/`fetch_edges()` also retry once on transport errors via `_with_reconnect()`.

- `fare_for_distance(km, mode)` — slab lookup. `TRAIN_FARE_SLABS = [(10,5),(20,10),(25,15),(30,20),(inf,30)]`, `METRO_FARE_SLABS = [(2,10),(4,15),(6,20),(8,25),(10,30),(inf,40)]`. Walking = ₹0.
- `fetch_nodes()` / `fetch_edges()` — pull from Supabase on every request, no cache. `compare_routes()` calls each **once** and shares the graph across its three searches (was three builds / six round trips before 2026-09-23).
- `build_graph(weight="time")` — builds a NetworkX `DiGraph`; every edge carries `distance`, `time`, `cost`, `fare_weight` (per-edge slab fare) and a `weight` mirror of the requested attribute; adds reverse edges automatically for `bus`, `cab`, `train`, `metro`, `walking`.
- `shortest_path(source, target, weight, graph=None)` — one Dijkstra run on the requested weight; pass `graph=(G, NODES)` to reuse a built graph. Float totals are rounded to 2 decimals (`11.8`, not `11.799999999999997`).
- `shortest_path_cost_approx(source, target, graph=None)` — a **separate**, only-partially-used Dijkstra run that weights edges by per-edge `fare_for_distance()` (not cumulative per-mode slabs — the function's own docstring flags this as an approximation).
- `compare_routes(source, target)`:
  1. Runs `shortest_path()` for `time` and `distance` — **two real Dijkstra runs**, not three.
  2. Runs `shortest_path_cost_approx()` as a third candidate (`fare_approx`).
  3. The `"cost"` result is whichever of the **three** candidates (time, distance, fare_approx) has the lowest `real_fare`, so it can be the `fare_approx` path (confirmed: Belapur CBD → Pendhar returns train→walk→metro with fare ₹35 as the cost route, distinct from the ₹40 metro-only time/distance routes). Ties go to `time`, then `distance`.
  4. Returns exactly 3 route dicts tagged `optimized_for`. Two or all three often share the same path — the frontend must expect duplicates.
  5. Raises `RoutingError` for bad input and lets data-source errors propagate (no more silent `[]`).
  6. Builds the graph once (two Supabase round trips) per call.

> Earlier docs described 3 independent Dijkstra runs returning three distinct optimal paths; the 2026-09-23 audit draft of this doc then over-corrected and said the cost route is always a copy of the time/distance path. Neither is right — see step 3.

## `railradar.py` — live data integration (rewritten 2026-09-23)

Station live-board integration (m-Indicator style). One RailRadar call per boarding station, filtered down to the trains that actually carry the passenger along the first train leg of the route.

**Station codes** — `STATION_CODES` maps normalized graph names to RailRadar codes, all verified against the live API on 2026-09-23: Vashi `VSH`, Sanpada `SNCR`, Juinagar `JNJ`, Nerul `NEU`, Seawoods-Darave `SWDK` (the old `SWDV` is an inactive record that returns an empty board), Belapur CBD `BEPR`, Kharghar `KHAG`, Mansarovar `MANR`, Khandeshwar `KNDS`, Panvel `PNVL`, Targhar `TRGR`, Bamandongri `BMDR`, Kharkopar `KARP`. Sagar Sangam is not a RailRadar station (no passenger halt); it has the internal token `SGSG` so it can sit on a corridor, and boarding there yields `reason: station_not_in_railradar`. Metro stations are not in the map.

**Corridor model** — `CORRIDORS` lists ordered station codes per line, with `@MUMBAI`, `@THANE`, `@URAN` anchors standing for termini outside the graph (CSMT, Vadala Road, Goregaon, Thane, Uran, ...). Derived from actual boards:
- `harbour`: @MUMBAI → Vashi → Sanpada → Juinagar → Nerul → Seawoods → Belapur → Kharghar → Mansarovar → Khandeshwar → Panvel
- `trans-harbour`: @THANE → Juinagar → ... → Panvel (Thane–Panvel/Nerul trains **skip Sanpada and Vashi**)
- `trans-harbour-vashi`: @THANE → Sanpada → Vashi
- `uran-nerul`: Nerul → Seawoods → Sagar Sangam → Targhar → Bamandongri → Kharkopar → @URAN
- `uran-belapur`: Belapur → Sagar Sangam → Targhar → Bamandongri → Kharkopar → @URAN

`train_serves(source, destination, boarding, alighting)` returns the corridor name if a train running source→destination stops at boarding strictly before alighting in its direction of travel, else `None`. This excludes wrong-direction trains, trains terminating at the boarding station (arrivals), trains that short-turn before the alighting station, and trains on other branches.

**Functions**
- `get_station_live_board(code, hours=2)` — `GET /v1/stations/{code}/live`, Bearer auth. RailRadar only accepts `hours` ∈ {2,4,6,8}. Cached per station for 60s (both in memory and in `backend/.cache/railradar` to survive server reloads in dev). Enforces a 10 call/min client rate limit and caches upstream 429 errors for 60s. Raises on missing key / HTTP error.
- `first_train_leg(route)` — finds the first run of consecutive `train` edges; boarding = its first station, alighting = the farthest station of that run still on one corridor with the boarding station (i.e. where you'd have to change trains). A route ending in metro/walking therefore uses the train alighting station, not the route's final node.
- `select_relevant_trains(board, boarding_code, alighting_code, limit)` — keeps only `train.type == "EMU"`, only trains with a departure at the boarding station, only trains passing `train_serves`; normalizes timestamps to IST; applies symmetric midnight wrap; classifies trains whose departure has passed (>1m before board timestamp) as `departed`; sorts by expected departure; returns last 2 departed + first `limit` upcoming.
- `annotate_route_with_live_status(route, limit=5)` — sets `live_trains` and `live_status` on the route dict (main.py passes `limit=3`).

**Response shape**
```json
"live_trains": [{
  "train_number": "98184", "route_name": "Panvel - Mumbai CSMT Local",
  "towards": "Mumbai CSMT", "destination_code": "CSMT", "line": "harbour",
  "departure_time": "18:37", "expected_departure": "2026-09-23T18:37:00+05:30",
  "platform": "2", "status": "scheduled|upcoming|departed|not-started|at-station",
  "delay_minutes": null
}],
"live_status": {
  "applicable": true, "reason": "ok",
  "boarding_station": "Panvel", "alighting_station": "Vashi",
  "boarding_code": "PNVL", "alighting_code": "VSH", "line": "harbour",
  "trains_on_board": 51, "relevant_trains": 16, "not_suburban": 9, "not_serving_route": 26,
  "board_time": "2026-09-23T18:32:59+05:30", "quota_remaining": 823
}
```
`live_status.reason` ∈ `ok` · `no_relevant_trains` · `no_train_leg` (`applicable: false`, e.g. all-metro route — UI should show "not applicable") · `station_not_in_railradar` · `api_key_missing` · `fetch_failed` · `parse_failed` (adds `error`: exception class name). Failures are never silent: `live_trains` is `[]` and the reason says why. `delay_minutes` is `null` for trains RailRadar is not yet tracking, not `0`. `platform` may be `null`.

**Rate limits (observed from response headers):** 10 requests/minute, 1,000/month on the sandbox key.

## `alternatives.py` — shared alternatives engine (added 2026-10-05, Phase C)

Implements Idea 1 (Railway Backing) and Idea 2 (Forward Switching) from `future-ideas.md` under `?prefer_seat=true`:
- **Backing (`kind="back"`):** Board a train in the reverse direction to an originating terminus (e.g. Khandeshwar → Panvel), boarding a fresh originating train with guaranteed seating. Requires a valid ticket/pass for the detour (advisory note attached).
- **Forward Switching (`kind="switch"`):** Board direct train, alight at an intermediate origin/junction station (e.g. Belapur CBD), and switch to a fresh originating train starting there.

**Core Mechanics:**
- `ORIGIN_STATIONS = {"PNVL", "BEPR", "NEU", "VSH"}`: Suburban originating stations.
- `find_pivots(b_code, a_code, corridor, max_pivots=2)`: Discovers candidate stations strictly behind (backing) or strictly between (switching), sorted by proximity and capped at 2.
- `compute_alternatives(route, boards, prefer_seat, threshold_minutes=15, transfer_buffer_minutes=3)`:
  - Uses pre-fetched boards (`hours=4`).
  - Matches train numbers across station boards to extract real scheduled/expected times (falling back to edge times if train record absent on downstream board).
  - Enforces minimum transfer buffer: **4 minutes** at Belapur CBD (`BEPR`), **3 minutes** elsewhere.
  - Sorts candidate origin trains by expected departure to pair earliest feasible Leg 2.
  - Computes `extra_minutes` against the earliest upcoming direct train.
  - Discards alternatives exceeding the 15-minute delay threshold; returns max 2 alternatives sorted by extra time.
- `annotate_route_with_alternatives(route_result, prefer_seat=True)`: Fetches missing pivot boards using the cached `get_station_live_board(hours=4)` and attaches `live_alternatives` and `live_alternatives_status`.

**Response Shape:**
```json
"live_alternatives": [{
  "kind": "switch|back",
  "seat": true,
  "via": "Belapur CBD",
  "via_code": "BEPR",
  "leg1": {
    "train_number": "98090", "route_name": "Panvel - Mumbai CSMT Local",
    "departure_time": "18:24", "expected_departure": "2026-10-05T18:24:00+05:30", "platform": "3"
  },
  "leg2": {
    "train_number": "98184", "route_name": "Belapur CBD - Mumbai CSMT Local",
    "departure_time": "18:37", "expected_departure": "2026-10-05T18:37:00+05:30", "platform": "2"
  },
  "direct": {
    "train_number": "98090", "departure_time": "18:24", "expected_departure": "2026-10-05T18:24:00+05:30"
  },
  "extra_minutes": 8,
  "note": "Switch at Belapur CBD to a train originating there — likely seat."
}],
"live_alternatives_status": {
  "applicable": true, "reason": "ok",
  "pivots_checked": ["BEPR"], "alternatives_found": 1, "calls_used": 1
}
```

## `cabs.py` — cab provider layer (added 2026-10-05, Phase E)

Implements the aggregator comparison pattern (industry standard for Google Maps / Citymapper):
- **Haversine & Road Distance:** Straight-line GPS distance expanded with a 1.30x road tortuosity factor for Navi Mumbai's urban grid; estimates travel time using a 25 km/h urban speed model.
- **Provider Rate Cards:**
  - **Auto Rickshaw:** Official MMRTA Navi Mumbai metered auto rate (₹28 for first 1.5 km, ₹18.66/km thereafter).
  - **Uber India:** Uber Auto (Base ₹30 + ₹16/km), Uber Go (Base ₹60 + ₹15/km), Uber Premier (Base ₹80 + ₹19/km).
  - **Ola Cabs:** Ola Auto (Base ₹30 + ₹15.5/km), Ola Mini (Base ₹60 + ₹14.5/km), Ola Prime Sedan (Base ₹85 + ₹18.5/km).
  - **Rapido:** Rapido Bike (Base ₹25 + ₹9/km, 15% faster traffic transit), Rapido Auto (Base ₹30 + ₹15/km).
- **Universal One-Tap Deep Links:**
  - Uber: `https://m.uber.com/ul/?action=setPickup&client_id=optigo&pickup[latitude]=...&dropoff[latitude]=...`
  - Ola: `https://book.olacabs.com/?lat=...&lng=...&drop_lat=...&drop_lng=...`
  - Rapido: `rapido://ride?pickup_lat=...&drop_lat=...`
- **Output:** Returns all ride tiers sorted by lowest fare first, tagged `estimated: true` with disclaimer.

**Tests:** `backend/tests/test_railradar.py` (29), `backend/tests/test_routing_errors.py` (20), `backend/tests/test_phase_b_railradar.py` (12), `backend/tests/test_phase_c_alternatives.py` (8), `backend/tests/test_cabs.py` (11). **80 tests total**, stdlib `unittest`, 100% offline fixture-backed (runtime ~0.15s). Run from `backend/`: `python -m unittest discover -s tests -v`.

## CORS
Hardcoded in `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```
No prod origin set yet — needs updating before deploy.

## Fare Slabs (unverified against official notification)
- Train: 0–10km ₹5, 11–20km ₹10, 21–25km ₹15, 26–30km ₹20, 31+km ₹30
- Metro: 0–2km ₹10, 2–4km ₹15, 4–6km ₹20, 6–8km ₹25, 8–10km ₹30, 10+km ₹40

## Setup
```bash
# from the repo root
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # root file forwards to backend/requirements.txt
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
```
The pin list lives only in `backend/requirements.txt`; the root `requirements.txt` is a one-line `-r backend/requirements.txt` so the two cannot drift. The repo `.venv` was rebuilt on 2026-09-23 on Python 3.12 (the old one pointed at a removed 3.13 interpreter) and is now gitignored.

Tests: `cd backend && ../.venv/bin/python -m unittest discover -s tests -v`
`.env` needs `SUPABASE_URL`, `SUPABASE_KEY` (secret key, not anon), `RAILRADAR_API_KEY`.

## Test Node IDs
| Station | ID |
|---|---|
| Vashi | 1 |
| Belapur CBD | 6 |
| Panvel | 11 |
| Kharkopar | 14 |
| Pendhar | 23 |
| RBI | 24 |

## Frontend

`frontend/` on `main` is the untouched `create-next-app` scaffold (Next.js 16.2, React 19, Tailwind 4, TS) — the frontend owner (Himesh) builds here. The Phase 2 reference screen built on 2026-09-23 was reverted from `main` on 2026-09-25 and kept on branch **`frontend-reference`** (commit `647132f`): `lib/api.ts` typed client, `lib/routes.ts` helpers, `RouteCard`, `page.tsx` with pickers/optimise-for/shareable URLs. Everything the frontend needs to know about the API is in `handoff.md` (local, gitignored — share directly).

Constraints the frontend must respect: backend CORS allows `http://localhost:3000` only; display `totals.real_fare` not `totals.cost`; candidates may share a path; `live_status.reason == "no_train_leg"` is "not applicable", not an error.

## Environment gotchas
- Flatpak VS Code's integrated terminal runs in a sandbox with Python 3.13; the repo `.venv` is host Python 3.12. Run backend commands via `flatpak-spawn --host …` or a system terminal. Do not rebuild the venv from inside the sandbox.
- Inside Claude Code's shell, `next dev` (Turbopack) exited silently mid-compile; `next dev --webpack` and `next build && next start` worked.

## Known doc/code mismatches found this pass (all resolved 2026-09-23)
- Prior README described a `/nodes` endpoint that did not exist; it exists now (added 2026-09-23).
- Prior README described flat `total_distance`/`total_time` keys on `/route` — actual response nests them under `"totals"`.
- Prior handoff/log described a fully different `railradar.py` (per-train lookup, `get_local_trains`/`find_relevant_trains`/`get_train_live`, commit `2e48187`). Commit `3f8b4d8` replaced it with a station-live-board version whose direction filter was broken (matched the route's final node against the train's destination/name and fell back to the whole board). Rewritten on 2026-09-23 as described above.
