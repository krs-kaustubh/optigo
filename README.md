# Optigo

**One App, Every Route, Optimized for You**

A multimodal journey-planning engine for **Navi Mumbai** that finds optimal routes across train, metro, and walking — ranked by time, distance, or fare — and shows the live suburban-train board for the leg you'd actually board. Built as a PBL-Mini Project (KJSIT, SY Engineering).

> [!NOTE]
> **Status (2026-09-23):** backend audited, fixed and tested (48 tests); frontend has one working screen wired to the real API (pick stations → 3 route cards). Live train status is implemented in the backend and is the next thing to surface in the UI.
> Demo deadline: **Oct 9, 2026** (final).

---

## How It Works

Optigo models Navi Mumbai's transit network as a **directed graph** — stations are nodes, rail/metro/walking connections are edges — stored in Supabase and loaded into NetworkX per request.

`GET /compare` returns **three candidates**:

1. **Fastest** — Dijkstra on edge `time`.
2. **Shortest** — Dijkstra on edge `distance`.
3. **Cheapest** — whichever of *fastest*, *shortest*, or a third **fare-approximation** search (Dijkstra on per-edge slab fare) has the lowest real slab fare. It is often the same path as one of the first two; the frontend labels such duplicates.

With `live=true`, each route with a train leg also gets the **live station board** for its first boarding station, filtered to trains that actually carry you towards where you alight (correct line, direction, branch; no arrivals that terminate there; no long-distance expresses).

```
┌─────────────┐   GET /nodes · GET /compare?source=11&target=1&live=true
│  Frontend   │──────────────────────────────────────────────┐
│  Next.js 16 │                                              ▼
└─────────────┘                                     ┌──────────────┐
                                                    │   FastAPI    │
                                                    │   main.py    │
                                                    └──────┬───────┘
                                                           │
                                ┌──────────────────────────┼──────────────────┐
                                ▼                          ▼                  ▼
                          ┌──────────┐              ┌────────────┐     ┌────────────┐
                          │ graph.py │              │railradar.py│     │  Supabase  │
                          │ NetworkX │              │ live board │     │  Postgres  │
                          │ Dijkstra │              │ + corridor │     │  + PostGIS │
                          │ fare calc│              │   filter   │     └────────────┘
                          └──────────┘              └────────────┘
```

---

## Network Coverage

**24 stations** across 3 lines, 26 directed edges in the DB (reverse edges are added in code):

| Line | Stations | Edges |
|---|---|---|
| **Harbour Rail** (Vashi–Panvel) | Vashi → Sanpada → Juinagar → Nerul → Seawoods-Darave → Belapur CBD → Kharghar → Mansarovar → Khandeshwar → Panvel | 9 train |
| **Uran Branch** (via Sagar Sangam) | Seawoods-Darave → Sagar Sangam, Belapur CBD → Sagar Sangam → Targhar → Bamandongri → Kharkopar | 5 train |
| **Metro Line 1** (Belapur–Pendhar) | Belapur CBD → RBI → Belpada → Utsav Chowk → Kendriya Vihar → Kharghar Village → Central Park → Pethpada → Amandoot → Pethali-Taloja → Pendhar | 10 metro |
| **Walking** | Belpada ↔ Kharghar | 2 walking |

**Interchange:** Belapur CBD (rail ↔ metro) · **Walk transfer:** Kharghar (rail) ↔ Belpada (metro)

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 · FastAPI · uvicorn |
| Routing | NetworkX (Dijkstra) |
| Database | Supabase (Postgres + PostGIS) |
| Live train data | RailRadar API (sandbox: 10 req/min, 1,000 req/month) |
| Frontend | Next.js 16 · React 19 · Tailwind 4 · TypeScript |
| Tests | Python `unittest` (no network) |
| Hosting (planned) | Vercel (frontend) + Render (backend) |

---

## Repo Structure

```
optigo/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI routes, CORS, error → HTTP status mapping
│   │   ├── graph.py           Supabase client, graph build, Dijkstra, fare slabs, RoutingError types
│   │   └── railradar.py       RailRadar live board, corridor model, direction filter
│   ├── tests/
│   │   ├── test_railradar.py        28 tests — corridor logic, filtering, sorting, cache
│   │   └── test_routing_errors.py   20 tests — validation, error codes, /nodes, Supabase retry
│   ├── requirements.txt       the pin list
│   └── .env                   (gitignored) SUPABASE_URL, SUPABASE_KEY, RAILRADAR_API_KEY
├── frontend/
│   ├── app/page.tsx           the one screen: pickers, optimise-for, 3 route cards
│   ├── app/components/RouteCard.tsx
│   └── lib/api.ts, lib/routes.ts   typed API client + pure helpers
├── sql-schema/                Supabase seed SQL (DDL, nodes, edges, RPC, fixes)
├── requirements.txt           forwards to backend/requirements.txt
├── future-ideas.md            design notes for features not built yet
└── README.md                  ← you are here
```

Local-only docs (gitignored, present in the working copy): `ARCHITECTURE.md` (ground truth for how the code behaves), `plan.md` (build-day plan and phase status), `log.md` (chronological work log), `REPO.md` (access and run notes).

---

## Setup

### Backend

```bash
# from the repo root
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # forwards to backend/requirements.txt
```

Create `backend/.env`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-secret-key
RAILRADAR_API_KEY=your-railradar-key
```

| Variable | Where to get it |
|---|---|
| `SUPABASE_URL` | Supabase Dashboard → Project Settings → API → Project URL |
| `SUPABASE_KEY` | Same page → `secret` key (server-side, not the anon key) |
| `RAILRADAR_API_KEY` | [railradar.in](https://railradar.in) — free sandbox tier |

Run:
```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload --port 8000
```
Swagger UI: http://127.0.0.1:8000/docs

> If your terminal is the Flatpak VS Code integrated terminal, it runs inside a sandbox with a different Python. Either run from a system terminal, or prefix the command with `flatpak-spawn --host`.

Tests (no network, Supabase and RailRadar are mocked):
```bash
cd backend && ../.venv/bin/python -m unittest discover -s tests -v
```

### Frontend

```bash
cd frontend
npm install
npm run dev            # Turbopack; if it exits silently, use: npm run dev:webpack
```
Opens at http://localhost:3000. The backend URL defaults to `http://localhost:8000`; override with `NEXT_PUBLIC_API_URL`.

Shareable links run a search on load: `http://localhost:3000/?from=11&to=1&for=cost`.

### CORS

The backend allows `http://localhost:3000` only. A frontend on any other origin fails with "Cannot reach the backend". Update `allow_origins` in `backend/app/main.py` before deploying.

---

## API Reference

### `GET /health`
```json
{ "status": "ok" }
```

### `GET /nodes`
All stations, sorted by id.
```json
[{ "id": 1, "name": "Vashi", "lat": 19.0632517, "lng": 72.9988553, "type": "rail" }, ...]
```

### `GET /route?source&target&weight`

| Param | Type | Default | Description |
|---|---|---|---|
| `source` | int | 1 | Source node ID |
| `target` | int | 5 | Target node ID |
| `weight` | `time` · `distance` · `cost` | `time` | Edge attribute to minimise (`cost` = legacy static column, not the slab fare) |

```json
{
  "path": ["Panvel", "Khandeshwar", "...", "Vashi"],
  "edges": [{ "from": "Panvel", "to": "Khandeshwar", "mode": "train" }, ...],
  "totals": { "distance": 19, "time": 34, "cost": 45, "real_fare": 10 }
}
```
Totals are **nested** under `totals`; `real_fare` is the slab fare, `cost` the legacy column.

### `GET /compare?source&target&live`

| Param | Type | Default | Description |
|---|---|---|---|
| `source` | int | 1 | Source node ID |
| `target` | int | 5 | Target node ID |
| `live` | bool | `false` | Attach the live train board to routes with a train leg |

Returns **exactly 3** route objects (same shape as `/route`) each with `optimized_for` ∈ `time` · `distance` · `cost`. Two or all three may share the same path.

With `live=true` each route also has:
```json
"live_trains": [{
  "train_number": "98184", "route_name": "Panvel - Mumbai CSMT Local",
  "towards": "Mumbai CSMT", "destination_code": "CSMT", "line": "harbour",
  "departure_time": "18:37", "expected_departure": "2026-09-23T18:37:00+05:30",
  "platform": "2", "status": "scheduled", "delay_minutes": null
}],
"live_status": {
  "applicable": true, "reason": "ok",
  "boarding_station": "Panvel", "alighting_station": "Vashi",
  "boarding_code": "PNVL", "alighting_code": "VSH", "line": "harbour",
  "trains_on_board": 51, "relevant_trains": 16, "board_time": "2026-09-23T18:32:59+05:30"
}
```
`live_status.reason` ∈ `ok` · `no_relevant_trains` · `no_train_leg` (all-metro route, `applicable: false`) · `station_not_in_railradar` · `api_key_missing` · `fetch_failed`. Up to 2 recently departed + 3 upcoming trains, sorted by expected departure.

### Errors

All 4xx/5xx bodies are `{"detail": "<message>", "error": "<Type>"}`.

| Case | Status | `error` |
|---|---|---|
| node id not in graph | 404 | `UnknownNode` |
| no path between nodes | 404 | `NoPath` |
| `source == target` | 400 | `SameNode` |
| bad `weight` / non-integer id | 422 | FastAPI validation |
| Supabase unreachable (after one retry) | 502 | `UpstreamError` |

---

## Fare Logic

Fares are cumulative per-mode distance slabs in `graph.py`, **not** the static `cost` column (legacy; only `/route?weight=cost` still uses it as a Dijkstra weight).

| Train (Harbour/Uran) | | Metro (Line 1) | |
|---|---|---|---|
| 0–10 km | ₹5 | 0–2 km | ₹10 |
| 11–20 km | ₹10 | 2–4 km | ₹15 |
| 21–25 km | ₹15 | 4–6 km | ₹20 |
| 26–30 km | ₹20 | 6–8 km | ₹25 |
| 31+ km | ₹30 | 8–10 km | ₹30 |
| | | 10+ km | ₹40 |

Walking is free.

> [!IMPORTANT]
> Slabs are user-estimated — not yet verified against official Central Railway / NMMC Metro notifications.

---

## Database Schema

Two tables in Supabase (Postgres + PostGIS); full SQL in `sql-schema/`.

```sql
create table nodes (id serial primary key, name text not null,
                    location geometry(Point, 4326) not null, type text not null);
create table edges (id serial primary key,
                    from_node int not null references nodes(id),
                    to_node   int not null references nodes(id),
                    mode text not null check (mode in ('walking','bike','car','bus','train','metro')),
                    distance double precision not null check (distance >= 0),
                    time     double precision not null check (time >= 0),
                    cost     double precision not null default 0 check (cost >= 0),
                    road_name text);
```
`get_nodes_with_coords()` decodes the geometry to `lat`/`lng`. Point order for inserts is `(lng, lat)`.

---

## Example Queries

```bash
curl "http://localhost:8000/nodes"
curl "http://localhost:8000/route?source=6&target=23&weight=time"
curl "http://localhost:8000/compare?source=6&target=23"
curl "http://localhost:8000/compare?source=11&target=1&live=true"
```

**Node IDs:** Vashi = `1`, Belapur CBD = `6`, Panvel = `11`, Kharkopar = `14`, Pendhar = `23`, RBI = `24`

**Known results:**
- **Belapur CBD → Pendhar:** fastest/shortest = all-metro via RBI (10.2 km, 28 min, ₹40); cheapest = train + walk + metro via Kharghar (11.8 km, 37 min, ₹35). Live status: not applicable for the metro-only routes.
- **Panvel → Vashi:** fastest/cheapest = 9-stop train (19 km, 34 min, ₹10); shortest = train + metro + walk + train (18.6 km, 41 min, ₹20). Live board shows only Panvel→CSMT / Vadala Road / Goregaon locals.
- **Belapur CBD → Kharkopar:** all three the same route via Sagar Sangam (9 km, ₹5). Live board shows only Belapur–Uran locals.

---

## Roadmap

- [x] Graph engine with Dijkstra (NetworkX)
- [x] Supabase migration (nodes, edges, PostGIS), real chainage distances
- [x] Fare slab logic (per-mode cumulative)
- [x] 3-candidate compare (`/compare`)
- [x] RailRadar live board with correct line/direction filtering (`/compare?live=true`)
- [x] Proper error responses (404/400/422/502) and Supabase reconnect
- [x] Frontend: station pickers → 3 route cards (Phase 2)
- [ ] Frontend: live train board on cards, "not applicable" for metro-only (Phase 3)
- [ ] Bus (NMMT/Chalo) and Navi Mumbai Metro live data — research (Phase 4; no public API known)
- [ ] Railway "backing" suggestion — see `future-ideas.md` Idea 1
- [ ] CORS: set production origin before deploy
- [ ] Verify fare slabs against official notifications
- [ ] Deploy: Vercel (frontend) + Render (backend)
- [ ] Optional: slab-aware DP for exact cost optimality; map UI

---

## License

Unlicensed — academic project.
