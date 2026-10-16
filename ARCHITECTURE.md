# Optigo — Architecture & Backend Reference

**Verified directly against source (re-audited on 2026-10-16 through Phase D of `feat/road-edges`). This file is the ground truth.**

Related docs: `README.md` (overview + API reference, tracked) · `backend/README.md` · `future-ideas.md` (tracked; Ideas 1–2) · `handoff.md` (frontend handoff, gitignored) · `plan.md` (phase status) · `log.md` (work log) · `REPO.md` (access/run).

## Structure
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           FastAPI app, CORS, route handlers, error → HTTP status handlers
│   ├── graph.py          Supabase client (keepalive-tuned), graph builder, Dijkstra, road leg grouping, fare calc
│   ├── railradar.py      RailRadar client: live station board + corridor model + relevance filter
│   ├── alternatives.py   Shared alternatives engine: backing (Idea 1) & forward switching (Idea 2)
│   └── cabs.py           Cab provider layer: calibrated fares & deep links (Uber, Ola, Rapido, Auto)
├── scripts/
│   ├── capture_boards.py Live RailRadar board capture script with quota pacing
│   └── seed_warm_nodes.py One-shot Overpass fetcher & bidirectional road_edges SQL generator
├── tests/
│   ├── test_railradar.py              29 tests
│   ├── test_routing_errors.py         20 tests (fixture graph, Supabase mocked)
│   ├── test_phase_b_railradar.py      12 tests (all 8 corridor journeys + edge cases)
│   ├── test_phase_c_alternatives.py    8 tests (backing, switching, cap, filters, endpoint)
│   ├── test_cabs.py                   11 tests (fare models, road distance, deep links, endpoint)
│   └── test_road_edges.py             11 tests (snapshots, road=true, leg grouping, walk cap, edge cases)
├── requirements.txt       the pin list (root requirements.txt forwards here)
└── .env                   (gitignored — never committed)
sql-schema/
├── seed.sql                        Canonical 24-node, 26-edge base schema & data
├── migration_road_edges.sql        Forward migration: railway_edges, road_edges, compatibility view `edges`, warm-node columns/RPC
├── rollback_road_edges.sql         Clean transactional rollback with warm-node CSV backup warning
├── warm_nodes.csv                  Reviewable CSV for warm nodes (source, confidence, osm_id)
└── seed_warm_nodes_and_roads.sql   Generated SQL for warm nodes + bidirectional road_edges
frontend/                  Next.js 16 — see "Frontend" and "For the frontend (Himesh)" below
```

## Database Schema & Safe Migration (`sql-schema/`)

1. **`nodes` table:**
   - Original columns: `id`, `name`, `location` (`GEOMETRY(Point, 4326)`), `type`.
   - Added in `migration_road_edges.sql`:
     - `tier` (`'hot' | 'warm'`, default `'hot'`)
     - `kind` (`'rail' | 'metro' | 'bus_depot' | 'bus_stop' | 'auto_stand'`, default `'rail'`)
     - `source` (`TEXT`, default `'seed'`, e.g. `'osm_overpass'`)
     - `confidence` (`'high' | 'medium' | 'low'`, default `'high'`)
     - `osm_id` (`BIGINT`, nullable)
2. **`railway_edges` table & `edges` compatibility view:**
   - The original `edges` table is renamed to `railway_edges`.
   - A read-compatible SQL view `CREATE OR REPLACE VIEW edges AS SELECT id, from_node, to_node, mode, distance, time, cost, road_name FROM railway_edges;` keeps existing callers (`supabase.table("edges").select("*")`) working with zero code changes.
3. **`road_edges` table:**
   - Columns: `id`, `from_node`, `to_node`, `distance` (km), `distance_source` (`'estimated' | 'osrm' | 'surveyed'`, default `'estimated'`), `road_name`, `UNIQUE (from_node, to_node)`.
   - Stores bidirectional rows (`(u, v)` and `(v, u)`) explicitly, generated via $k = 3$ nearest neighbours within $3.0\text{ km}$ ($\text{haversine} \times 1.30$) plus a nearest-hot-node connectivity guarantee.
4. **PostGIS RPCs:**
   - `get_nodes_with_coords()`: **Unchanged 5-column return signature** `(id, name, lat, lng, type)` filtering `WHERE tier = 'hot'`. Protects default `/nodes` and `lat,lng` nearest-station lookups from seeing warm nodes.
   - `get_all_nodes_with_coords()`: Extended RPC returning `(id, name, lat, lng, type, tier, kind, source, confidence, osm_id)`, called **only** when `include_warm=true` or `road=true`.
5. **Data Attribution (OpenStreetMap / ODbL):**
   - Warm node coordinates and stop names extracted from OpenStreetMap via Overpass (`source = 'osm_overpass'`) are © OpenStreetMap contributors and licensed under the Open Database License (**ODbL**). Any UI screen or exported dataset displaying warm nodes must credit *"© OpenStreetMap contributors (ODbL)"*.

## Endpoints (actual, from `main.py`)

**6** endpoints: `/health`, `/test`, `/nodes`, `/route`, `/compare`, `/cabs/estimate`.

### `GET /health`
Returns `{"status": "ok"}`.

### `GET /nodes?include_warm=false`
- Default (`include_warm=false`): Calls `graph.list_nodes(include_warm=False)` → `fetch_nodes()` (`get_nodes_with_coords`). Returns the 24 hot stations sorted by id: `[{"id", "name", "lat", "lng", "type"}]`.
- Opt-in (`include_warm=true`): Calls `graph.list_nodes(include_warm=True)` → `fetch_all_nodes()` (`get_all_nodes_with_coords`). Returns hot + warm nodes with `{"id", "name", "lat", "lng", "type", "tier", "kind", "source", "confidence"}`.

### `GET /route?source&target&weight&road=false`
- `source`, `target`: integer node ID or `"lat,lng"` string, default `"1"` / `"5"`.
- `weight`: `time` (default) · `distance` · `cost` · `convenient` (`convenient` is valid **only** when `road=true`; returns 422 when `road=false`).
- `road`: `false` (default) uses `edges` + `get_nodes_with_coords`; `true` uses `railway_edges` + `road_edges` + `get_all_nodes_with_coords`.
- Response shape (`road=false`): `{"path": [...], "edges": [...], "totals": {"distance", "time", "cost", "real_fare"}}`.

### `GET /compare?source&target&live=false&prefer_seat=false&road=false`
- Calls `graph.compare_routes(src, tgt, road=road)`.
- When `road=false` (default): returns **exactly 3 routes** (`optimized_for` in `["time", "distance", "cost"]`), byte-identical to the legacy contract.
- When `road=true`: returns **4 routes** (`optimized_for` in `["time", "distance", "cost", "convenient"]`), groups consecutive road edges into single legs, prices cab legs via `cabs.py`, and includes `road_legs` + `convenience_score` (on the `convenient` candidate).
- If `live=true` or `prefer_seat=true`: annotates each candidate with `railradar.annotate_route_with_live_status(route, limit=3)` and (when `prefer_seat=true`) `alternatives.annotate_route_with_alternatives(route, prefer_seat=True)`.

### `GET /cabs/estimate?pickup_lat&pickup_lng&dropoff_lat&dropoff_lng`
- Also accepts station IDs helper: `?source_station_id=1&target_station_id=6`.
- Calls `cabs.get_all_cab_estimates(...)`.
- Returns side-by-side fare estimates, ETAs, and universal deep links for **Uber** (Auto, Go, Premier), **Ola** (Auto, Mini, Prime Sedan), **Rapido** (Bike, Auto), and **Auto Rickshaw** (metered).
- Returns 422 if neither coordinate quartet nor station ID pair is provided.

### Error responses
`graph.py` raises `RoutingError` subclasses; `main.py` maps them to JSON `{"detail": "...", "error": "<ClassName>"}`:

| Case | Error | Status |
|---|---|---|
| node id not in graph | `UnknownNode` | 404 |
| no path between the nodes | `NoPath` | 404 |
| `source == target` | `SameNode` | 400 |
| bad `weight` (or `weight=convenient` with `road=false`) | FastAPI `Literal` / `InvalidWeight` | 422 |
| invalid `source`/`target` (neither integer nor `"lat,lng"`) | `HTTPException` | 422 |
| Supabase transport error (stale connection, unreachable) after one retry | `UpstreamError` | 502 |
| any other unexpected exception | propagates | 500 |

## `graph.py` — routing logic & road-aware extensions

### Named Constants (top of `graph.py`)
| Constant | Value | Meaning |
|---|---|---|
| `WALK_SPEED_KMH` | `5.0` | Walking speed in km/h (12 min/km) |
| `MAX_WALK_EDGE_KM` | `1.0` | Road edges $\le 1.0\text{ km}$ allow walking; $> 1.0\text{ km}$ require cab/auto |
| `MAX_TOTAL_WALK_KM` | `1.5` | Maximum cumulative walking distance per route (km) |
| `MAX_WALK_CAP_ITERATIONS` | `5` | Maximum re-runs removing longest walking edge when `MAX_TOTAL_WALK_KM` is exceeded |
| `CAB_PICKUP_WAIT_MIN` | `4.0` | Pickup/hailing wait added **once per grouped cab leg** (see 3–5 min `eta_minutes` in `cabs.py`); walking legs get no wait |
| `TRANSFER_PENALTY_MIN` | `8.0` | Penalty in equivalent minutes per mode change in convenience score |
| `WARM_NODE_BOARDING_PENALTY_MIN` | `5.0` | Extra uncertainty penalty (min) when boarding at a `tier='warm'` node |
| `WALK_PENALTY_MULTIPLIER` | `2.0` | Walking effort multiplier (1 min walk = 2 min perceived effort) |
| `CONVENIENT_K_PATHS` | `10` | Number of shortest simple paths (by time) scored for `convenient` and `time` (`road=true`) |

### Core Mechanics
- **Default path (`road=False`):** `build_graph()` calls `fetch_nodes()` and `fetch_edges()` once, builds the `nx.DiGraph`, and runs 3 searches (`time`, `distance`, `fare_approx`), picking the `cost` winner by `real_fare`. Works whether or not the SQL migration has been applied.
- **Road-aware path (`road=True`):**
  1. **One fetch per table:** `build_graph(road=True)` calls `fetch_all_nodes()`, `fetch_railway_edges()`, and `fetch_road_edges()` once and shares the graph across all 4 searches (`time`, `distance`, `cost`, `convenient`).
  2. **Per-edge Dijkstra weights:** Road edges $\le 1.0\text{ km}$ have `mode="walking"` ($5\text{ km/h}$, `fare_weight=0`); road edges $> 1.0\text{ km}$ have `mode="cab"` ($25\text{ km/h}$, marginal `fare_weight = distance * 18.22`). Scheduled `train` and `metro` edges are never overwritten by `road_edges`.
  3. **Walking-cap post-check (`_find_path_with_walk_cap`):** After Dijkstra finds a path, if total walking exceeds `MAX_TOTAL_WALK_KM` (`1.5 km`), the longest walking edge in that path is removed (or upgraded to `cab` if it is a cut-edge) and Dijkstra re-runs, at most `MAX_WALK_CAP_ITERATIONS` (`5`) times.
  4. **Contiguous leg grouping & pricing (`_route_result(..., road=True)`):** Consecutive road edges of the same mode (`cab` or `walking`) are merged into **one road leg**:
     - For `cab` legs: `CAB_PICKUP_WAIT_MIN` (`4.0 min`) is added **once** to the leg's travel time, the leg is priced **once** on its summed distance via `cabs.metered_auto_fare(leg_dist)` (so the ₹27 base fare is never double-counted across hops), and `cab_estimates` from `cabs.get_all_cab_estimates(..., road_km_override=leg_dist)` are attached.
     - For `walking` road legs: no pickup wait is added, `cost = 0`, and `cab_estimates` is omitted.
     - Every road leg carries `"distance_source": "estimated"`, `"time_source": "estimated"`, and `"fare_source": "estimated"`, plus `"via": [...]` when $>1$ road hop was merged.
  5. **Convenient route (`shortest_path_convenient`):** Generates up to `CONVENIENT_K_PATHS` (`10`) simple paths via `nx.shortest_simple_paths(G, source, target, weight="time")`, scores each with `_convenience_score()`, and returns the minimum with `"convenience_score"` attached.

## `railradar.py` — live data integration (rewritten 2026-09-23)

Station live-board integration (m-Indicator style). One RailRadar call per boarding station, filtered down to the trains that actually carry the passenger along the first train leg of the route.

**Station codes** — `STATION_CODES` maps normalized graph names to RailRadar codes: Vashi `VSH`, Sanpada `SNCR`, Juinagar `JNJ`, Nerul `NEU`, Seawoods-Darave `SWDK`, Belapur CBD `BEPR`, Kharghar `KHAG`, Mansarovar `MANR`, Khandeshwar `KNDS`, Panvel `PNVL`, Targhar `TRGR`, Bamandongri `BMDR`, Kharkopar `KARP`. Sagar Sangam uses internal token `SGSG` (`NOT_IN_RAILRADAR = {"SGSG"}`).

**Corridor model** — `CORRIDORS`: `harbour`, `trans-harbour`, `trans-harbour-vashi`, `uran-nerul`, `uran-belapur`.

**Rate limits:** 10 requests/minute, 1,000/month on the sandbox key (60s memory + disk cache in `backend/.cache/railradar`).

## `alternatives.py` — shared alternatives engine (added 2026-10-05, Phase C)

Implements Idea 1 (Railway Backing, `kind="back"`) and Idea 2 (Forward Switching, `kind="switch"`) under `?prefer_seat=true` using `ORIGIN_STATIONS = {"PNVL", "BEPR", "NEU", "VSH"}`, a 4-minute transfer buffer at Belapur CBD (3 minutes elsewhere), and a 15-minute max extra time threshold.

## `cabs.py` — cab provider layer (updated 2026-10-16)

- **Haversine & Road Distance:** Straight-line GPS distance × `ROAD_TORTUOSITY_FACTOR = 1.30` (or exact `road_km_override` when pricing grouped road legs from `graph.py`), driving speed `URBAN_SPEED_KMH = 25.0`.
- **Tariff Constants & Providers:**
  - **Auto Rickshaw (`AutoRickshawProvider`):** `AUTO_BASE_FARE_INR = 27.0` for the first `AUTO_BASE_DISTANCE_KM = 1.5` km, plus `AUTO_PER_KM_RATE_INR = 18.22`/km thereafter. Labelled *"Estimated from published MMRTA tariff cards (₹27 base + ₹18.22/km; reported, official card pending)"* (press-reported revision w.e.f. `01.09.2026`; prior published MMRTA card w.e.f. `01.02.2025` was ₹26.00 + ₹17.14/km; the earlier ₹28 + ₹18.66/km in code was the 2022 black-and-yellow taxi card).
  - **Uber India (`UberProvider`):** Uber Auto, Uber Go, Uber Premier.
  - **Ola Cabs (`OlaProvider`):** Ola Auto, Ola Mini, Ola Prime Sedan.
  - **Rapido (`RapidoProvider`):** Rapido Bike, Rapido Auto.
- Every estimate object carries `"estimated": true` and `"fare_source": "estimated"`.

**Tests:** `test_railradar.py` (29), `test_routing_errors.py` (20), `test_phase_b_railradar.py` (12), `test_phase_c_alternatives.py` (8), `test_cabs.py` (11), `test_road_edges.py` (11). **91 tests total**, stdlib `unittest`, 100% offline fixture-backed (~0.2s).

---

## For the frontend (Himesh)

Default API behaviour (`GET /nodes`, `GET /compare`, `GET /route` without the new query params) is **100% unchanged and byte-identical**. When you opt into the new road/warm-node features, here is what changes:

1. **`GET /compare?source=...&target=...&road=true` returns 4 candidates (instead of 3):**
   - `optimized_for` values are `["time", "distance", "cost", "convenient"]`.
   - The 4th candidate (`optimized_for: "convenient"`) includes a top-level numeric `"convenience_score"` field (lower = more convenient).
2. **Merged road legs in `edges` (and `road_legs`):**
   - Consecutive road edges of the same mode (`"cab"` or `"walking"`) are merged into a single leg object.
   - Because multi-hop road segments are merged into one leg, **`route.edges.length` can be shorter than `route.path.length - 1`**. When a road leg merges 2 or more hops, it includes `"via": ["Intermediate Stop Name", ...]`.
   - Every road leg in `route.edges` (and duplicated in `route.road_legs` for convenience) carries:
     - `"distance"`, `"time"`, `"cost"`
     - `"distance_source": "estimated"`, `"time_source": "estimated"`, `"fare_source": "estimated"`
     - `"cab_estimates": [...]` — **attached only on `"cab"` legs** (never on `"walking"` legs). Contains the 8 provider tier estimates from `cabs.py` (`Auto Rickshaw`, `Rapido`, `Ola`, `Uber`) with deep links and `fare_low`/`fare_high`.
   - Scheduled `"train"` and `"metro"` edges inside `route.edges` keep their existing shape `{"from": ..., "to": ..., "mode": "train"|"metro"}`.
3. **`GET /nodes?include_warm=true` adds 4 metadata fields per node:**
   - Returns both hot stations and warm nodes (bus stops / auto stands), adding:
     - `"tier"`: `"hot" | "warm"`
     - `"kind"`: `"rail" | "metro" | "bus_depot" | "bus_stop" | "auto_stand"`
     - `"source"`: `"seed" | "osm_overpass" | ...`
     - `"confidence"`: `"high" | "medium" | "low"`
   - If you display warm nodes sourced from OpenStreetMap (`source === "osm_overpass"`), include `"© OpenStreetMap contributors (ODbL)"` in map attribution.

---

## Setup & Tests
```bash
# Run offline test suite (91 tests, no network or keys required)
env -i PATH="$PATH" SUPABASE_URL="http://localhost:54321" SUPABASE_KEY="dummy" PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
```

