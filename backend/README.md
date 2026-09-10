# Optigo Backend

FastAPI routing engine for Navi Mumbai multimodal transit. Computes optimal routes across train, metro, and walking using NetworkX (Dijkstra) with live data from Supabase and real-time train status from RailRadar.

> Project-wide overview, network map, schema DDL, and roadmap → [root README](../README.md)

---

## Architecture

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           FastAPI app, CORS, all route handlers
│   ├── graph.py           Supabase client, graph builder, Dijkstra, fare calc
│   └── railradar.py       RailRadar API client: local trains, live status
├── requirements.txt
└── .env                   (gitignored — never committed)
```

### File Breakdown

**`main.py`** — FastAPI app with CORS middleware. Defines 4 endpoints (`/health`, `/route`, `/compare`, `/nodes`). Never touches the database directly — delegates to `graph.py` and `railradar.py`.

**`graph.py`** — Core routing logic:
- `fetch_nodes()` / `fetch_edges()` — pull live data from Supabase on every request (no cache)
- `build_graph(weight)` — constructs a NetworkX `DiGraph`, adds bidirectional edges for train/metro/walking/bus/cab
- `fare_for_distance(km, mode)` — slab-based fare lookup (train and metro have separate slab tables)
- `shortest_path(source, target, weight)` — single Dijkstra run
- `compare_routes(source, target)` — runs Dijkstra 3× (time, distance, cost) and returns all candidates

**`railradar.py`** — RailRadar API integration:
- `get_local_trains(city)` — fetches all suburban trains for a city (default: Mumbai)
- `find_relevant_trains(station_names, all_trains, limit)` — substring-matches route names against station names
- `get_train_live(train_number)` — live status for a single train (delay, current location, next halt)
- `annotate_route_with_live_status(route_result, limit)` — attaches live delay data to a route dict; best-effort, swallows per-train errors

### Request Flow

```
GET /compare?source=6&target=23&live=true
        │
        ▼
    main.py
        │
        ├──► graph.compare_routes(6, 23)
        │       │
        │       ├──► fetch_nodes()  ──► Supabase RPC get_nodes_with_coords()
        │       ├──► fetch_edges()  ──► Supabase table select
        │       ├──► build_graph()  ──► NetworkX DiGraph
        │       └──► nx.shortest_path() × 3  (time, distance, cost)
        │
        └──► railradar.annotate_route_with_live_status() × 3
                │
                ├──► get_local_trains("Mumbai")  ──► RailRadar API
                ├──► find_relevant_trains()       (substring match)
                └──► get_train_live()             ──► RailRadar API (per train)
```

---

## Setup

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

Key packages: `fastapi`, `uvicorn`, `networkx`, `supabase`, `python-dotenv`, `requests`

### 2. Environment variables

Create `backend/.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-secret-key
RAILRADAR_API_KEY=your-railradar-key
```

| Variable | Source | Notes |
|---|---|---|
| `SUPABASE_URL` | Dashboard → Settings → API → Project URL | |
| `SUPABASE_KEY` | Same page → `secret` key | Server-side only. Not the anon/public key. |
| `RAILRADAR_API_KEY` | [railradar.in](https://railradar.in) | Free sandbox: 1,000 requests/month |

> [!CAUTION]
> `.env` is gitignored. Never commit API keys. If you accidentally do, rotate them immediately.

### 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## API Endpoints

### `GET /health`

```bash
curl http://localhost:8000/health
```
```json
{"status": "ok"}
```

---

### `GET /route`

Single optimal route.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `source` | int | ✅ | — | Source node ID |
| `target` | int | ✅ | — | Target node ID |
| `weight` | str | — | `"time"` | `time` · `distance` · `cost` |

```bash
curl "http://localhost:8000/route?source=6&target=23&weight=time"
```

```json
{
  "path": ["Belapur CBD", "RBI", "Belpada", "Utsav Chowk", "..."],
  "edges": [
    {"from": "Belapur CBD", "to": "RBI", "mode": "metro", "distance": 1.0, "time": 2}
  ],
  "total_distance": 10.2,
  "total_time": 22,
  "real_fare": 40,
  "optimized_for": "time"
}
```

---

### `GET /compare`

Three candidates — one optimized for each of time, distance, cost.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `source` | int | ✅ | — | Source node ID |
| `target` | int | ✅ | — | Target node ID |
| `live` | bool | — | `false` | Attach RailRadar live train data |

```bash
curl "http://localhost:8000/compare?source=6&target=23&live=true"
```

Returns an array of 3 route objects. When `live=true`, each includes:

```json
{
  "optimized_for": "time",
  "path": ["Belapur CBD", "RBI", "..."],
  "total_distance": 10.2,
  "total_time": 22,
  "real_fare": 40,
  "live_trains": [
    {
      "train_number": "98001",
      "route_name": "Mumbai CSMT - Panvel Local",
      "status": "running",
      "delay_minutes": 5
    }
  ]
}
```

---

### `GET /nodes`

All stations with decoded lat/lng.

```bash
curl http://localhost:8000/nodes
```

---

## Fare Calculation

Fares use cumulative distance slabs — **not** the static `cost` column in the edges table (that's legacy, ignored by `compare_routes()`).

```python
# graph.py
TRAIN_FARE_SLABS = [(10, 5), (20, 10), (25, 15), (30, 20), (float("inf"), 30)]
METRO_FARE_SLABS = [(2, 10), (4, 15), (6, 20), (8, 25), (10, 30), (float("inf"), 40)]
```

`fare_for_distance(km, mode)` walks the slab list and returns the first matching price. Walking = ₹0.

> [!IMPORTANT]
> Slabs are user-estimated. Not yet verified against official fare charts.

---

## RailRadar Integration

**Endpoint pattern:** `https://api.railradar.in/v1/...` with `Bearer` token auth.

**Real API response shapes** (confirmed against live API, not docs):

`get_local_trains("Mumbai")`:
```json
{"success": true, "data": {"98001": "Mumbai CSMT - Panvel Local", "...": "..."}, "meta": {...}}
```
→ `data` is a **dict** `{train_number: route_name}`, not a list of objects.

`get_train_live("98001")`:
```json
{"success": true, "data": {"status": "running", "delayMinutes": 5, "currentLocation": "...", "nextHalt": "...", "route": [...]}, "meta": {...}}
```
→ `status` and `delayMinutes` are nested under `data`, not top-level.

**Rate limit:** Free sandbox tier = 1,000 requests/month. `annotate_route_with_live_status` caps at `limit=3` trains per route to conserve quota.

---

## CORS

Currently hardcoded in `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Before deploying:** add your production frontend domain to `allow_origins`, or switch to an env-variable approach.

---

## Test Node IDs

| Station | ID |
|---|---|
| Belapur CBD | 6 |
| Pendhar | 23 |
| Kharkopar | 14 |
| Panvel | 11 |

**Quick smoke test:**
```bash
# Should return 3 routes, all-metro via RBI is time/distance optimal
curl "http://localhost:8000/compare?source=6&target=23"
```

---

## Development Notes

- `graph.py` fetches from Supabase on **every request** — no in-memory cache. Fine for demo scale; will need caching for production traffic.
- All bidirectional modes (train, metro, walking, bus, cab) automatically get reverse edges in `build_graph()`.
- `compare_routes()` returns a **list of dicts**, not a single dict — important for wiring in `main.py`.
- RailRadar annotation is best-effort — if the API is down or a train fetch fails, the route still returns, just without `live_trains`.
