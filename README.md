# Optigo

**One App, Every Route, Optimized for You**

A multimodal journey-planning engine for **Navi Mumbai** that finds optimal routes across train, metro, and walking — ranked by time, cost, or distance. Built as a PBL-Mini Project (KJSIT, SY Engineering).

> [!NOTE]
> Backend is live and functional. Frontend is scaffold-only (`create-next-app`).
> Demo deadline: **Sep 11, 2026** (showable) · **Oct 9, 2026** (final).

---

## How It Works

Optigo models Navi Mumbai's transit network as a **directed graph** — stations are nodes, rail/metro/walking connections are edges. Given a source and destination, it runs Dijkstra three times (optimizing time, distance, and cost separately) and returns three route candidates with real fare calculations.

```
┌─────────────┐     GET /compare?source=6&target=23
│  Frontend   │────────────────────────────────────────────┐
│  (Next.js)  │                                            ▼
└─────────────┘                                   ┌──────────────┐
                                                  │   FastAPI     │
                                                  │   main.py     │
                                                  └──────┬───────┘
                                                         │
                              ┌───────────────────┬──────┴───────┐
                              ▼                   ▼              ▼
                        ┌──────────┐       ┌──────────┐   ┌───────────┐
                        │ graph.py │       │railradar │   │ Supabase  │
                        │ NetworkX │◄─────►│  .py     │   │ Postgres  │
                        │ Dijkstra │       │ live API │   │ + PostGIS │
                        └──────────┘       └──────────┘   └───────────┘
```

---

## Network Coverage

**24 stations** across 3 lines:

| Line | Stations | Edges |
|---|---|---|
| **Harbour Rail** (Vashi–Panvel) | Vashi → Sanpada → Juinagar → Nerul → Seawoods-Darave → Belapur CBD → Kharghar → Mansarovar → Khandeshwar → Panvel | 14 train |
| **Uran Branch** (via Sagar Sangam) | Seawoods-Darave → Sagar Sangam, Belapur CBD → Sagar Sangam → Targhar → Bamandongri → Kharkopar | (included above) |
| **Metro Line 1** (Belapur–Pendhar) | Belapur CBD → RBI → Belpada → Utsav Chowk → Kendriya Vihar → Kharghar Village → Central Park → Pethpada → Amandoot → Pethali-Taloja → Pendhar | 10 metro |
| **Walking** | Belpada ↔ Kharghar (both directions) | 2 walking |

**Interchange node:** Belapur CBD (rail ↔ metro)

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python · FastAPI |
| Routing | NetworkX (Dijkstra) |
| Database | Supabase (Postgres + PostGIS) |
| Live train data | RailRadar API (sandbox tier) |
| Frontend | Next.js 16 · React 19 · Tailwind |
| Hosting (planned) | Vercel (frontend) + Render (backend) |

---

## Repo Structure

```
optigo/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI routes + CORS
│   │   ├── graph.py          # Supabase fetch, graph build, Dijkstra, fare calc
│   │   └── railradar.py      # RailRadar API: live train status
│   ├── requirements.txt
│   └── .env                   # (gitignored) secrets
├── frontend/                   # Next.js — currently create-next-app scaffold
├── sql-schema/                 # Supabase seed SQL
│   ├── nodes-edges             # Table DDL
│   ├── nodes-data              # Station inserts
│   ├── edge-data               # Edge inserts
│   ├── postgres                # get_nodes_with_coords() function
│   ├── update-node-edge-data   # RBI node + topology fixes
│   └── 6. Distance Update      # Real chainage distances
├── requirements.txt            # Root-level deps (kept in sync)
└── README.md                   # ← you are here
```

---

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
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
| `RAILRADAR_API_KEY` | [railradar.in](https://railradar.in) — free sandbox tier (1,000 req/month) |

Run the server:
```bash
uvicorn app.main:app --reload --port 8000
```

Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at [http://localhost:3000](http://localhost:3000). Currently default Next.js boilerplate — no Optigo UI yet.

### CORS

Backend currently allows `http://localhost:3000` only. Update `allow_origins` in `backend/app/main.py` before deploying to production.

---

## API Reference

### `GET /health`

Health check.

```json
{ "status": "ok" }
```

### `GET /route`

Single optimal route between two nodes.

| Param | Type | Default | Description |
|---|---|---|---|
| `source` | int | required | Source node ID |
| `target` | int | required | Target node ID |
| `weight` | string | `"time"` | Optimize for `time`, `distance`, or `cost` |

**Response:**
```json
{
  "path": ["Belapur CBD", "RBI", "Belpada", "..."],
  "edges": [
    { "from": "Belapur CBD", "to": "RBI", "mode": "metro", "distance": 1.0, "time": 2 }
  ],
  "total_distance": 10.2,
  "total_time": 22,
  "real_fare": 40
}
```

### `GET /compare`

Three route candidates optimized for time, distance, and cost respectively.

| Param | Type | Default | Description |
|---|---|---|---|
| `source` | int | required | Source node ID |
| `target` | int | required | Target node ID |
| `live` | bool | `false` | Attach RailRadar live delay data to train segments |

**Response:** Array of 3 route objects (same shape as `/route`), each with an `optimized_for` field.

When `live=true`, each route also gets a `live_trains` array:
```json
{
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

### `GET /nodes`

All stations with coordinates (calls `get_nodes_with_coords()` Supabase RPC).

---

## Fare Logic

Fares are calculated per-mode using cumulative distance slabs in `graph.py`, **not** the static `cost` column in the database (that's legacy).

### Train (Harbour/Uran lines)

| Distance | Fare |
|---|---|
| 0 – 10 km | ₹5 |
| 11 – 20 km | ₹10 |
| 21 – 25 km | ₹15 |
| 26 – 30 km | ₹20 |
| 31+ km | ₹30 |

### Metro (Line 1)

| Distance | Fare |
|---|---|
| 0 – 2 km | ₹10 |
| 2 – 4 km | ₹15 |
| 4 – 6 km | ₹20 |
| 6 – 8 km | ₹25 |
| 8 – 10 km | ₹30 |
| 10+ km | ₹40 |

### Walking

Free (₹0).

> [!IMPORTANT]
> These slabs are **user-estimated** — not yet verified against official Central Railway or NMMC Metro fare notifications. Treat as approximate.

---

## Database Schema

Two tables in Supabase (Postgres + PostGIS):

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

Helper function to decode PostGIS geometry into lat/lng:
```sql
create or replace function get_nodes_with_coords()
returns table(id int, name text, lat double precision, lng double precision, type text)
language sql as $$
  select id, name, ST_Y(location) as lat, ST_X(location) as lng, type
  from nodes;
$$;
```

> Point order for inserts is `(lng, lat)`, not `(lat, lng)` — PostGIS convention.

---

## Example Queries

```bash
# Single route, optimize for time
curl "http://localhost:8000/route?source=6&target=23&weight=time"

# Compare all 3 optimization strategies
curl "http://localhost:8000/compare?source=6&target=23"

# Compare with live train delay data
curl "http://localhost:8000/compare?source=6&target=23&live=true"
```

**Test node IDs:** Belapur CBD = `6`, Pendhar = `23`, Kharkopar = `14`, Panvel = `11`

**Known results:**
- **Belapur CBD → Pendhar:** Time/distance optimal = all-metro via RBI (10.2 km, ₹40). Cost optimal = train + walk + metro via Kharghar (11.8 km, ₹35).
- **Belapur CBD → Kharkopar:** All 3 strategies return the same route via Sagar Sangam (9 km, ₹5).

---

## Roadmap

- [x] Graph engine with Dijkstra (NetworkX)
- [x] Supabase migration (nodes, edges, PostGIS)
- [x] Real chainage distances (Harbour, Uran, Metro)
- [x] Fare slab logic (per-mode cumulative)
- [x] 3-candidate compare (`/compare`)
- [x] RailRadar live-status integration (`/compare?live=true`)
- [ ] Frontend: map UI with route visualization
- [ ] CORS: set production origin before deploy
- [ ] Verify fare slabs against official notifications
- [ ] Deploy: Vercel (frontend) + Render (backend)
- [ ] Optional: slab-aware DP for exact cost optimality
- [ ] Optional: officially source metro per-hop distances

---

## License

Unlicensed — academic project.
