# Optigo Backend

FastAPI routing engine for Navi Mumbai multimodal transit. Computes route candidates across train, metro, and walking using NetworkX (Dijkstra) on a graph stored in Supabase, and attaches the live suburban-train board from RailRadar, filtered to the trains that actually serve the route.

> Project-wide overview, network map, schema DDL, and roadmap → [root README](../README.md). Behavioural ground truth → `ARCHITECTURE.md` (local, gitignored).

---

## Architecture

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           FastAPI app, CORS, route handlers, RoutingError/UpstreamError → HTTP status
│   ├── graph.py          Supabase client, graph builder, Dijkstra, fare calc, error types
│   └── railradar.py      RailRadar client: live station board + corridor-based relevance filter
├── tests/
│   ├── test_railradar.py         corridor logic, filtering, sorting, cache (no network)
│   └── test_routing_errors.py    validation, HTTP codes, /nodes, Supabase retry (fixture graph)
├── requirements.txt      the pin list (root requirements.txt forwards here)
└── .env                  (gitignored — never committed)
```

### `main.py`
Four endpoints: `/health`, `/nodes`, `/route`, `/compare`. Never touches the database directly. Two exception handlers turn `RoutingError` subclasses into 400/404 and `UpstreamError` into 502, all with a JSON body `{"detail", "error"}`. `weight` is a `Literal`, so an invalid value is a 422 from FastAPI.

### `graph.py`
- **Supabase client** is created at import from `SUPABASE_URL` / `SUPABASE_KEY`, with a custom `httpx.Client` whose idle connections expire after 15 s. Supabase closes idle connections server-side; without this, the first request after a pause failed with `Server disconnected`.
- `fetch_nodes()` / `fetch_edges()` — one RPC + one table select per request, no cache, retried once on transport errors, then `UpstreamError`.
- `list_nodes()` — the `/nodes` payload.
- `build_graph(weight="time")` — NetworkX `DiGraph`; every edge carries `distance`, `time`, `cost`, `fare_weight` (per-edge slab fare) and a `weight` mirror; reverse edges added for bus/cab/train/metro/walking.
- `fare_for_distance(km, mode)` — slab lookup; walking = ₹0.
- `shortest_path(source, target, weight, graph=None)` — one Dijkstra run; validates weight and endpoints; float totals rounded to 2 dp.
- `shortest_path_cost_approx(source, target, graph=None)` — Dijkstra on `fare_weight` (approximate: real fare is cumulative per mode, not additive).
- `compare_routes(source, target)` — builds the graph **once**, runs the three searches, returns `time`, `distance`, and `cost` = the candidate with the lowest `real_fare` (which may be the approximation path). Raises instead of returning `[]`.
- Errors: `RoutingError` → `InvalidWeight`, `UnknownNode`, `SameNode`, `NoPath`; `UpstreamError` for Supabase failures.

### `railradar.py`
- `STATION_CODES` — graph station name → RailRadar code, all verified against the API (Seawoods-Darave is `SWDK`; Sagar Sangam has no RailRadar station).
- `CORRIDORS` — ordered station lists per line with `@MUMBAI` / `@THANE` / `@URAN` anchors for termini outside the graph: `harbour`, `trans-harbour` (Thane trains skip Sanpada and Vashi), `trans-harbour-vashi`, `uran-nerul`, `uran-belapur`.
- `train_serves(source, destination, boarding, alighting)` — corridor name if a train stops at boarding strictly before alighting in its direction of travel, else `None`.
- `first_train_leg(route)` — boarding station and the alighting station of the first contiguous train run, bounded to one corridor.
- `get_station_live_board(code, hours=2)` — `GET /v1/stations/{code}/live` (RailRadar accepts `hours` ∈ {2,4,6,8}); cached 60 s per station so one `/compare?live=true` costs one call.
- `select_relevant_trains(board, boarding, alighting, limit)` — EMU only, must depart from boarding, must pass `train_serves`; sorted by expected departure; last 2 departed + first `limit` upcoming.
- `annotate_route_with_live_status(route, limit=5)` — sets `live_trains` and `live_status` (see root README for shapes and reasons). Failures are never silent.

### Request flow

```
GET /compare?source=11&target=1&live=true
        │
        ▼
    main.py ──► graph.compare_routes(11, 1)
        │           ├──► build_graph()  ──► Supabase RPC get_nodes_with_coords() + select edges  (once)
        │           ├──► shortest_path(time), shortest_path(distance), shortest_path_cost_approx()
        │           └──► 3 route dicts
        │
        └──► railradar.annotate_route_with_live_status(route, limit=3)  × 3
                    ├──► first_train_leg(route)            boarding = Panvel, alighting = Vashi
                    ├──► get_station_live_board("PNVL")    RailRadar (cached; 1 HTTP call for all 3 routes)
                    └──► select_relevant_trains(...)       Panvel→CSMT/Vadala/Goregaon locals only
```

---

## Setup

```bash
# from the repo root
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`backend/.env`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-secret-key
RAILRADAR_API_KEY=your-railradar-key
```

| Variable | Source | Notes |
|---|---|---|
| `SUPABASE_URL` | Dashboard → Settings → API → Project URL | |
| `SUPABASE_KEY` | Same page → `secret` key | Server-side only. Not the anon key. |
| `RAILRADAR_API_KEY` | [railradar.in](https://railradar.in) | Sandbox: 10 req/min, 1,000 req/month |

> [!CAUTION]
> `.env` is gitignored. Never commit API keys. If you do, rotate them.

Run:
```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload --port 8000
```
Swagger UI: http://127.0.0.1:8000/docs · ReDoc: http://127.0.0.1:8000/redoc

> Flatpak VS Code terminal? It has its own Python. Use a system terminal or `flatpak-spawn --host ../.venv/bin/uvicorn app.main:app --reload --port 8000`.

Tests:
```bash
cd backend
../.venv/bin/python -m unittest discover -s tests -v
```

---

## API

Full reference with response shapes and the error table is in the [root README](../README.md#api-reference). Summary:

| Endpoint | Returns |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `GET /nodes` | all stations `[{id, name, lat, lng, type}]` |
| `GET /route?source&target&weight` | one route `{path, edges, totals}` |
| `GET /compare?source&target&live` | exactly 3 routes tagged `optimized_for`; with `live=true` also `live_trains` + `live_status` |

Errors: 404 `UnknownNode` / `NoPath`, 400 `SameNode`, 422 validation, 502 `UpstreamError`.

---

## Fare Calculation

Cumulative distance slabs per mode — **not** the static `cost` column (legacy; only `/route?weight=cost` uses it as a weight).

```python
TRAIN_FARE_SLABS = [(10, 5), (20, 10), (25, 15), (30, 20), (float("inf"), 30)]
METRO_FARE_SLABS = [(2, 10), (4, 15), (6, 20), (8, 25), (10, 30), (float("inf"), 40)]
```

> [!IMPORTANT]
> Slabs are user-estimated. Not yet verified against official fare charts.

---

## RailRadar Integration

- Base `https://api.railradar.in/v1`, `Authorization: Bearer <key>`.
- Used endpoint: `GET /stations/{code}/live?hours=2` → `{"success", "data": {"trains": [{"train": {number, name, type, source, destination}, "stop": {arrival, departure, platform}, "live": {type, expectedDepartureTime, delayMinutes}}]}, "meta": {timestamp}}`.
- `live.type` values seen: `scheduled`, `upcoming`, `departed`, `not-started`. `train.type` for locals is `EMU`.
- Station search (used once to verify codes): `GET /lookup/search/stations?q=...`.
- Rate limits from response headers: `x-ratelimit-limit-min: 10`, `x-ratelimit-limit-month: 1000`.
- Everything about which trains are relevant is decided locally by the corridor model; RailRadar is only asked for the raw board.

---

## CORS

```python
allow_origins=["http://localhost:3000"]
```
A frontend on any other origin fails. Add the production domain (or switch to an env variable) before deploying.

---

## Test Node IDs

| Station | ID |
|---|---|
| Vashi | 1 |
| Belapur CBD | 6 |
| Panvel | 11 |
| Kharkopar | 14 |
| Pendhar | 23 |
| RBI | 24 |

Smoke test:
```bash
curl "http://localhost:8000/compare?source=11&target=1&live=true"
```
Expect 3 routes; the train routes' `live_trains` should contain only Panvel→CSMT / Vadala Road / Goregaon locals.

---

## Development Notes

- Supabase is hit on every request (2 calls per `/compare`). Fine for demo scale; add caching before real traffic.
- `compare_routes()` returns a **list** of 3 dicts; duplicates by path are normal.
- `/route?weight=cost` minimises the legacy `cost` column, not the slab fare.
- RailRadar failures are reported in `live_status.reason`, never swallowed; `live_trains` is `[]` in that case.
- Known gap: Sagar Sangam is a graph node but not a RailRadar station; boarding there gives `station_not_in_railradar`.
