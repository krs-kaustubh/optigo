# Optigo Backend

FastAPI service that computes optimal multimodal routes over a real Navi Mumbai transit graph, using NetworkX (Dijkstra) with data stored in Supabase (Postgres + PostGIS).

> Project-wide overview, roadmap, and vision live in the [root README](../README.md). This file covers everything you need to run and work on the backend specifically.

---

## Setup

**1. Install dependencies**
```bash
cd backend
pip install -r requirements.txt
```

**2. Environment variables**

Create `backend/.env` (already gitignored — never commit this):
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-secret-key
```
Get both from Supabase dashboard → **Project Settings → API**:
- `SUPABASE_URL` — Project URL (also visible on the project overview page)
- `SUPABASE_KEY` — the **secret** key (`sb_secret_...`), not the publishable/anon key. This is a privileged server-side key — never expose it client-side or commit it.

**3. Run the server**
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive API docs (Swagger UI): `http://127.0.0.1:8000/docs`

---

## Architecture

```
backend/
├── app/
│   ├── main.py      FastAPI routes: /health, /route, /compare + CORS middleware
│   └── graph.py     Fetches nodes/edges from Supabase, builds NetworkX graph, runs Dijkstra
├── requirements.txt
└── .env             (gitignored, not committed)
```

**Request flow:**
```
Client (browser/curl)
    │  GET /route?source=1&target=7&weight=time
    ▼
Uvicorn (ASGI server, listens on the port)
    ▼
FastAPI (main.py) — matches route, extracts query params
    ▼
graph.py — build_graph() fetches fresh nodes/edges from Supabase, constructs NetworkX DiGraph
    ▼
nx.shortest_path() — runs Dijkstra with the chosen weight
    ▼
JSON response — path / edges / totals
```

`graph.py` fetches fresh data from Supabase on every request via `fetch_nodes()`/`fetch_edges()` — nothing is hardcoded. `main.py` never touches the database directly; it only calls `shortest_path()`/`compare_routes()`. Each edge carries `mode`, `distance`, `time`, and `cost`, plus a generic `weight` attribute copied from whichever of the three is currently selected — that's what Dijkstra actually minimizes. All edge types (`bus`, `cab`, `train`, `metro`) are added to the graph in both directions. CORS middleware is already configured, currently allowing `http://localhost:3000`.

---

## Database Schema

Two tables in Supabase (Postgres + PostGIS) — full seed SQL lives in [`../sql-schema/`](../sql-schema/):

```sql
create extension if not exists postgis;

create table nodes (
    id serial primary key,
    name text not null,
    location geometry(Point, 4326) not null,
    type text not null
);

create table edges (
    id serial primary key,
    from_node int not null references nodes(id),
    to_node int not null references nodes(id),
    mode text not null
        check (mode in ('walking', 'bike', 'car', 'bus', 'train', 'metro')),
    distance double precision not null check (distance >= 0),
    time double precision not null check (time >= 0),
    cost double precision not null default 0 check (cost >= 0),
    road_name text
);
```

`location` is stored as native PostGIS geometry, not plain lat/lng floats — this enables real geospatial queries (nearest-node, radius search) in later phases. Point order for inserts is **(lng, lat)**, not (lat, lng) — a common PostGIS gotcha.

A helper function decodes geometry back into plain coordinates for the backend to consume:
```sql
create or replace function get_nodes_with_coords()
returns table(id int, name text, lat double precision, lng double precision, type text)
language sql
as $$
  select id, name, ST_Y(location) as lat, ST_X(location) as lng, type
  from nodes;
$$;
```

RLS (Row Level Security) is currently **disabled** on both tables. This is safe for now because the backend connects using the secret key, which bypasses RLS regardless, and the data itself (station names/coordinates/costs) is non-sensitive. Enable RLS if the frontend ever queries Supabase directly instead of going through this API.

---

## Current Data — Phase-1 Scope

23 real stations across three Navi Mumbai transit lines:

1. **Main Harbour Rail corridor**: Vashi → Sanpada → Juinagar → Nerul → Seawoods-Darave → Belapur CBD → Kharghar → Mansarovar → Khandeshwar → Panvel
2. **Uran-Ulwe branch**: feeders from both Nerul and Belapur CBD converge at Sagar Sangam junction, then continue Targhar → Bamandongri → Kharkopar (Phase-1 cutoff — Nhava Sheva/Dronagiri/Uran excluded)
3. **Belapur–Pendhar Metro Line 1**: Belapur CBD → Belpada → Utsav Chowk → Kendriya Vihar → Kharghar Village → Central Park → Pethpada → Amandoot → Pethali-Taloja → Pendhar

No Turbhe/Thane branch included in this phase.

**Data caveat:** `time`/`cost`/`distance` values are estimates derived from published fares (₹5 flat suburban fare, ₹40 end-to-end metro fare split proportionally across hops) and rider review text — not sourced from official Central Railway or Navi Mumbai Metro fare charts. Verify before any public-facing demo.

---

## API Reference

### `GET /health`
Liveness check.
```json
{"status": "ok"}
```

### `GET /route`
Single shortest path between two nodes, optimized for one metric.

| Param | Type | Default | Description |
|---|---|---|---|
| `source` | int | 1 | Origin node ID |
| `target` | int | 5 | Destination node ID |
| `weight` | string | `"time"` | One of `time`, `cost`, `distance` |

**Example:** `GET /route?source=1&target=11&weight=cost`
```json
{
  "path": ["Vashi", "Sanpada", "..."],
  "edges": [{"from": "Vashi", "to": "Sanpada", "mode": "train"}, ...],
  "totals": {"distance": 18.3, "time": 34, "cost": 45}
}
```

### `GET /compare`
Runs the same source/target through all three optimization weights (`time`, `cost`, `distance`) and returns all results together.

| Param | Type | Default | Description |
|---|---|---|---|
| `source` | int | 1 | Origin node ID |
| `target` | int | 5 | Destination node ID |

**Example:** `GET /compare?source=1&target=23` → array of three route objects (same shape as `/route`), each with an added `"optimized_for"` field.

### Error handling
`nx.shortest_path` raises if no path exists between the given nodes; `compare_routes` swallows that exception per-weight so it returns whatever succeeds rather than failing the whole request. Inputs are raw integer node IDs — no validation that the ID exists, and no way to query by station name yet. A bad `source`/`target` currently returns a raw NetworkX/FastAPI error rather than a clean 404.

---

## Node ID Reference

| ID | Name | Line |
|---|---|---|
| 1 | Vashi | Main corridor |
| 2 | Sanpada | Main corridor |
| 3 | Juinagar | Main corridor |
| 4 | Nerul | Main corridor / Uran feeder |
| 5 | Seawoods-Darave | Main corridor |
| 6 | Belapur CBD | Main corridor / Uran feeder / Metro interchange |
| 7 | Sagar Sangam | Uran branch junction |
| 8 | Kharghar | Main corridor |
| 9 | Mansarovar | Main corridor |
| 10 | Khandeshwar | Main corridor |
| 11 | Panvel | Main corridor |
| 12 | Targhar | Uran branch |
| 13 | Bamandongri | Uran branch |
| 14 | Kharkopar | Uran branch (cutoff) |
| 15 | Belpada | Metro |
| 16 | Utsav Chowk | Metro |
| 17 | Kendriya Vihar | Metro |
| 18 | Kharghar Village | Metro |
| 19 | Central Park | Metro |
| 20 | Pethpada | Metro |
| 21 | Amandoot | Metro |
| 22 | Pethali-Taloja | Metro |
| 23 | Pendhar | Metro |

---

## Known Issues

- Fare-zone edge case: boarding directly at certain intermediate stations may show incorrect fare totals — not yet fully verified across all edges.
- No true trade-off frontier yet — for a given source/target, `/compare` currently returns one path per weight, not multiple distinct alternative routes (e.g. train vs. direct cab vs. bus+train combo) unless the graph naturally forks.

## Testing & Linting

Nothing set up yet.
- No tests exist. Recommend `pytest` with a `backend/tests/` folder — good first targets: graph construction (`build_graph` produces the right node/edge count), shortest-path correctness on the known corridor, and specifically the flat-fare aggregation (a multi-hop train journey should total the flat fare, not sum per-hop).

## Deployment (not started)

Containerize with a Dockerfile installing `backend/requirements.txt`, copying `backend/app/`, running via `uvicorn`.

## Roadmap

1. Verify fare/time data against official sources
2. Add station-name-based lookups instead of requiring raw integer IDs
3. Add emissions as a 4th comparison metric
4. Add multi-objective optimization (minimize time *and* cost jointly, not just one at a time)
5. Add caching for repeated route queries once query volume matters
6. Post-submission: ML layer for dynamic edge weights (delay prediction, crowding), eventually reinforcement learning for adaptive routing
