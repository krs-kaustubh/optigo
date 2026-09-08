# Optigo

**One App, Every Route, Optimized for You**

A multimodal journey-planning platform (app + web) that finds the most optimal route between two points based on *your* constraints — time, cost, or distance — instead of defaulting to one fixed suggestion. Launching first in **Navi Mumbai**.

Built as a Final PBL-Mini Project.

---

## Table of Contents

- [The Problem](#the-problem)
- [The Idea](#the-idea)
- [Repo Structure](#repo-structure)
- [Tech Stack](#tech-stack)
- [Current Status](#current-status)
- [Backend](#backend)
- [Frontend](#frontend)
- [Full Feature Set (Vision)](#full-feature-set-vision)
- [Known Issues](#known-issues)
- [Roadmap](#roadmap)
- [Timeline](#timeline)
- [License](#license)

---

## The Problem

Getting around a city today means juggling separate apps — one for cabs, one for metro, one for buses, one for maps — and manually comparing them yourself. There's no single system that says: *"Given your priorities, here are all your real options, ranked."*

## The Idea

Optigo treats a city's transport network like a graph — stations, bus stops, auto stands, and taxi hubs are **nodes**; routes between them are **edges**. The engine scans this graph and surfaces multiple viable paths, each scored on time, cost, and distance.

**Positioning:** *Google Maps + Chalo + Splitwise of urban mobility — one app that finds, compares, books, and tracks every way to get where you're going.*

---

## Repo Structure

```
optigo/
├── backend/                FastAPI + NetworkX routing engine
│   └── app/
│       ├── main.py         API routes: /health, /route, /compare
│       └── graph.py        Fetches nodes/edges from Supabase, builds graph, runs Dijkstra
├── frontend/                Next.js web client (in progress — currently default scaffold)
├── sql-schema/              Supabase seed SQL: schema, node inserts, edge inserts, helper function
├── requirements.txt         Backend deps (dev copy, kept in sync with backend/requirements.txt)
└── README.md                you are here — single source of truth for setup + docs
```

> This file replaces the previous `README.md` + `readme.md` + `technical_documnetation.md` at root and `frontend/README.md` — all backend/frontend setup, architecture, and API docs now live here in one place.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 (TypeScript, Tailwind), React 19 — React Native planned later |
| Backend | FastAPI (Python) |
| Database | Supabase (Postgres + PostGIS) |
| Routing engine | NetworkX (Dijkstra) |
| Maps | Mapbox |
| Hosting | Vercel (frontend) + Render (backend) |

---

## Current Status

**Backend — live and functional.** Real Navi Mumbai transit data (23 stations, 23 routes across three lines: the Vashi–Panvel Harbour rail corridor, the Uran-Ulwe branch via Sagar Sangam junction cut off at Kharkopar, and the Belapur–Pendhar Metro Line 1) is stored in Supabase and served through a working `/route` and `/compare` API. CORS middleware is already configured for `http://localhost:3000`.

**Frontend — not yet built.** Currently default `create-next-app` boilerplate (Next 16.2.12 / React 19.2.4), no UI wired to the backend.

**Fare/time data — estimated**, not yet sourced from official Central Railway or Navi Mumbai Metro fare charts. Flagged for verification before any public demo.

---

## Backend

FastAPI service that computes optimal multimodal routes over a real Navi Mumbai transit graph, using NetworkX (Dijkstra) with data stored in Supabase (Postgres + PostGIS).

### Setup

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

### Request flow

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

`graph.py` fetches fresh data from Supabase on every request via `fetch_nodes()`/`fetch_edges()` — nothing is hardcoded. `main.py` never touches the database directly; it only calls `shortest_path()`/`compare_routes()`. Each edge carries `mode`, `distance`, `time`, and `cost`, plus a generic `weight` attribute copied from whichever of the three is currently selected — that's what Dijkstra actually minimizes. All edge types (`bus`, `cab`, `train`, `metro`) are added to the graph in both directions.

### Database schema

Two tables in Supabase (Postgres + PostGIS) — full seed SQL lives in [`sql-schema/`](sql-schema/):

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

### Current data — Phase-1 scope

23 real stations across three Navi Mumbai transit lines:

1. **Main Harbour Rail corridor**: Vashi → Sanpada → Juinagar → Nerul → Seawoods-Darave → Belapur CBD → Kharghar → Mansarovar → Khandeshwar → Panvel
2. **Uran-Ulwe branch**: feeders from both Nerul and Belapur CBD converge at Sagar Sangam junction, then continue Targhar → Bamandongri → Kharkopar (Phase-1 cutoff — Nhava Sheva/Dronagiri/Uran excluded)
3. **Belapur–Pendhar Metro Line 1**: Belapur CBD → Belpada → Utsav Chowk → Kendriya Vihar → Kharghar Village → Central Park → Pethpada → Amandoot → Pethali-Taloja → Pendhar

No Turbhe/Thane branch included in this phase.

**Data caveat:** `time`/`cost`/`distance` values are estimates derived from published fares (₹5 flat suburban fare, ₹40 end-to-end metro fare split proportionally across hops) and rider review text — not sourced from official Central Railway or Navi Mumbai Metro fare charts. Verify before any public-facing demo.

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

### API reference

**`GET /health`** — Liveness check.
```json
{"status": "ok"}
```

**`GET /route`** — Single shortest path between two nodes, optimized for one metric.

| Param | Type | Default | Description |
|---|---|---|---|
| `source` | int | 1 | Origin node ID |
| `target` | int | 5 | Destination node ID |
| `weight` | string | `"time"` | One of `time`, `cost`, `distance` |

Example: `GET /route?source=1&target=11&weight=cost`
```json
{
  "path": ["Vashi", "Sanpada", "..."],
  "edges": [{"from": "Vashi", "to": "Sanpada", "mode": "train"}, ...],
  "totals": {"distance": 18.3, "time": 34, "cost": 45}
}
```

**`GET /compare`** — Runs the same source/target through all three optimization weights (`time`, `cost`, `distance`) and returns all results together.

| Param | Type | Default | Description |
|---|---|---|---|
| `source` | int | 1 | Origin node ID |
| `target` | int | 5 | Destination node ID |

Example: `GET /compare?source=1&target=23` → array of three route objects (same shape as `/route`), each with an added `"optimized_for"` field.

### Error handling

`nx.shortest_path` raises if no path exists between the given nodes; `compare_routes` swallows that exception per-weight so it returns whatever succeeds rather than failing the whole request. Inputs are raw integer node IDs — no validation that the ID exists, and no way to query by station name yet. A bad `source`/`target` currently returns a raw NetworkX/FastAPI error rather than a clean 404.

### Testing & linting

Nothing set up yet. Recommend `pytest` with a `backend/tests/` folder — good first targets: graph construction (`build_graph` produces the right node/edge count), shortest-path correctness on the known corridor, and specifically the flat-fare aggregation (a multi-hop train journey should total the flat fare, not sum per-hop).

### Deployment guidance (not started)

Containerize with a Dockerfile installing `backend/requirements.txt`, copying `backend/app/`, running via `uvicorn`.

---

## Frontend

`frontend/app/page.tsx` and `layout.tsx` are the **unmodified `create-next-app` defaults** — Next.js logo, "edit page.tsx to get started" placeholder text, links to Vercel templates. No custom components, no calls to the backend yet.

### Setup

```bash
cd frontend
npm install
npm run dev
```
Opens at `http://localhost:3000`. `npm run lint` (ESLint) is configured but nothing custom has been added yet.

### Not yet done, in order

1. A form component accepting `source`, `target`, `weight`
2. `fetch()` call to `/route` or `/compare`
3. Render the returned `path`/`edges`/`totals` as a readable itinerary
4. Mapbox visualization of the route
5. Error state for failed calls or no-route-found

### Deployment guidance

`npm run build`, deploy to Vercel per the confirmed tech stack. Point API calls at the deployed backend URL, not `localhost`.

---

## Full Feature Set (Vision)

| # | Feature | Description |
|---|---|---|
| 1 | Unified Ticketing | Book across rail, metro, bus, and auto/cab providers in one place |
| 2 | Multi-Factor Comparison | Compare routes by time, fuel/fiscal cost, and emissions |
| 3 | Graph-Based Route Engine | Node-edge model connecting all transit hubs in an area |
| 4 | Offline Ticket Wallet | Store trip tickets offline, like Google Wallet |
| 5 | Emergency Location Sharing | Share live location with trusted contacts during a trip |
| 6 | AI Trip Assistant | Suggests and adjusts your plan on the fly |
| 7 | 3D Space Mapping | Indoor maps for malls, parking lots, parks |
| 8 | Local Travel Guides | Hire vetted local guides (85/15 revenue split) |
| 9 | Accessibility & Equity Pricing | Discounted fares for PWD, women, elderly |
| 10 | Advance Journey Planning | Web-first trip planning tools |
| 11 | Live Transit Radar | Real-time map view of moving vehicles |
| 12 | Public Vehicle Status | Live delays/crowding/ETAs, consolidated |

The current build covers the foundation for #2 and #3. Everything else is roadmap, planned for after the initial submission.

**Architecture notes for later phases:**
- **Plan Mode vs. Live Mode**: Feature #10 (Advance Planning) is a web-first, "before you leave" experience; most of the rest (#3, #11, #12) are real-time, on-the-go tools. Structuring the product around these two modes could make both UX and engineering cleaner.
- **Shared Live Data Engine**: Features #11 (Radar) and #12 (Status) depend on the same live-location/schedule feeds, just presented differently — worth building as one backend with two frontends.
- **Data partnerships are a dependency, not just a UI feature**: live radar/status for buses, autos, and cabs needs GPS feeds from operators or crowdsourced data, unlike rail data which has more established public feeds.
- Checked for a public API/MCP for live Mumbai local train status (m-Indicator, Where is my Train, NTES, RailRadar) — none currently expose one publicly. Revisit if that changes.

---

## Known Issues

1. Fare-zone edge case: boarding directly at certain intermediate stations may show incorrect fare totals — not yet fully verified across all edges.
2. No true trade-off frontier yet — for a given source/target, `/compare` currently returns one path per weight, not multiple distinct alternative routes (e.g. train vs. direct cab vs. bus+train combo) unless the graph naturally forks.
3. Root `.gitignore` malformed (literal `\n` characters instead of real line breaks) — currently harmless since the `frontend`/`backend` subfolder `.gitignore` files correctly cover what matters, but should be fixed.

---

## Roadmap

1. Frontend: source/destination form → `/compare` → render results → Mapbox
2. Verify fare/time data against official sources
3. Add station-name-based lookups instead of requiring raw integer IDs
4. Add emissions as a 4th comparison metric
5. Add multi-objective optimization (minimize time *and* cost jointly, not just one at a time)
6. Add caching for repeated route queries once query volume matters
7. Post-submission: ML layer for dynamic edge weights (delay prediction, crowding), eventually reinforcement learning for adaptive routing

---

## Timeline

- **Sep 11, 2026** — showable web demo
- **Oct 9, 2026** — final submission

## License

Not yet decided.
