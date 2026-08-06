# Optigo — Technical Documentation

_Verified against live repo (`krs-kaustubh/optigo`, `main`, commit `7b471c9`), 2026-08-08. Corrects several errors found in a prior Copilot-generated version of this document — corrections are marked ⚠️ where relevant._

---

## 1. Overview

**Optigo** is a minimal route-optimization demo comparing local bus, train, and cab modes for a single Navi Mumbai corridor (New Panvel ↔ Seawoods-Darave-Karawe). It demonstrates weighted graph pathfinding — ranking routes by time, cost, or distance — via a FastAPI backend and a Next.js frontend scaffold.

**Repo layout:**
```
optigo/
├── backend/     FastAPI service: graph modeling and routing
└── frontend/    Next.js app (App Router), currently unmodified scaffold
```

---

## 2. Architecture

**Backend:** `backend/app` exposes REST endpoints that build a directed graph with `networkx` and compute shortest paths. Routing logic lives in `backend/app/graph.py`; the API surface is in `backend/app/main.py`.

**Frontend:** `frontend/app` is the Next.js app directory. It is currently the **unmodified default `create-next-app` output** — no custom components, no calls to the backend. ⚠️ *(A prior version of this doc implied the frontend was a "placeholder UI ready to extend" without noting it's literally untouched boilerplate — worth being precise about, so no one assumes UI work happened that didn't.)*

**Data model:** graph nodes represent stations/stops/hubs; edges encode `mode`, `distance`, `time`, and `cost`. Each edge also gets a generic `weight` attribute, copied from whichever of `distance`/`time`/`cost` is currently selected — this is what Dijkstra actually minimizes.

**Request flow:**
```
Client (browser/curl)
    │  GET /route?source=1&target=7&weight=time
    ▼
Uvicorn (ASGI server, listens on the port)
    ▼
FastAPI (main.py) — matches route, extracts query params
    ▼
graph.py — build_graph() constructs NetworkX DiGraph
    ▼
nx.shortest_path() — runs Dijkstra with the chosen weight
    ▼
JSON response — path / edges / totals
```

---

## 3. Files & important paths

| Purpose | Path |
|---|---|
| Backend entry | `backend/app/main.py` |
| Graph/routing logic | `backend/app/graph.py` |
| Backend deps (root copy — **has** networkx) | `requirements.txt` |
| Backend deps (backend copy — **missing** networkx | `backend/requirements.txt` |
| Frontend entry | `frontend/app/page.tsx` (default scaffold) |
| Frontend layout | `frontend/app/layout.tsx` (default scaffold) |
| Frontend manifest | `frontend/package.json` |

---

## 4. Backend — design & implementation

### Endpoints

| Method & Path | Params | Returns |
|---|---|---|
| `GET /health` | — | `{"status": "ok"}` |
| `GET /route` | `source` (int, default 1), `target` (int, default 5), `weight` (str, default `time`) | Single optimized path for one objective |
| `GET /compare` | `source`, `target` | Array of route results, one per objective (`time`, `cost`, `distance`) |

### `main.py`
```python
from fastapi import FastAPI, Query
from app.graph import shortest_path, compare_routes

app = FastAPI(title="Optigo API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/route")
def get_route(source: int = Query(1), target: int = Query(5), weight: str = Query("time")):
    return shortest_path(source, target, weight)

@app.get("/compare")
def compare(source: int = Query(1), target: int = Query(5)):
    return compare_routes(source, target)
```

### `graph.py` — data model

**`NODES`** — dict of integer id → `{name, lat, lng}`.

**`EDGES`** — list of tuples `(from, to, mode, distance_km, time_min, cost_rs)`. Current corridor (7 nodes, 8 edges):

| From → To | Mode | Time | Cost |
|---|---|---|---|
| New Panvel → Khandeshwar | Bus | 20 min | ₹18 |
| New Panvel → Panvel Station | Bus | 20 min | ₹18 |
| Panvel → Khandeshwar | Train | 5 min | ₹5 |
| Khandeshwar → Mansarowar | Train | 5 min | ₹0 |
| Mansarowar → Kharghar | Train | 6 min | ₹0 |
| Kharghar → Belapur CBD | Train | 7 min | ₹0 |
| Belapur CBD → Seawoods | Train | 5 min | ₹0 |
| New Panvel → Seawoods (direct) | Cab (mocked) | 35 min | ₹250 |

**`build_graph(weight)`** — constructs an `nx.DiGraph`, attaches `mode`/`distance`/`time`/`cost` to each edge, plus a generic `weight` copied from whichever of the three is selected. Bus and cab edges are added in both directions; train edges are one-directional only (Panvel-side → Seawoods-side), modeling the line's actual direction.

**Flat-fare modeling:** real train fare is ₹5 for the entire journey regardless of stops crossed. This is encoded by putting the full ₹5 on the *first* train edge (Panvel → Khandeshwar) and ₹0 on every subsequent train edge, so a Dijkstra path's summed cost comes out flat automatically — no special-case logic needed in the pathfinding itself.
⚠️ *Known limitation, not yet fixed:* boarding directly at Khandeshwar (skipping the Panvel-side edge) currently shows ₹0 fare, since the flat cost only lives on that one edge.

**`shortest_path(source, target, weight)`** — builds the graph, runs `nx.shortest_path(G, source, target, weight="weight")`, then walks the resulting path to sum `distance`/`time`/`cost` and build a human-readable edge list. Returns:
```json
{
  "path": ["New Panvel (Origin - Zudio/Prajapati Oval)", "..."],
  "edges": [{"from": "...", "to": "...", "mode": "bus"}],
  "totals": {"distance": 0, "time": 0, "cost": 0}
}
```

**`compare_routes(source, target)`** — calls `shortest_path()` once per weight (`time`, `cost`, `distance`), tagging each result with `"optimized_for"`. This is the actual product behavior — ranked options side by side, not one fixed answer.

### Error handling
`nx.shortest_path` raises if no path exists between the given nodes; `compare_routes` swallows that exception per-weight so it returns whatever succeeds rather than failing the whole request. Inputs are raw integer node IDs — no validation that the ID exists, and no way to query by station name yet. A bad `source`/`target` currently returns a raw NetworkX/FastAPI error rather than a clean 404.

---

## 5. Frontend — structure & notes

`frontend/app/page.tsx` and `layout.tsx` are the **unmodified `create-next-app` defaults** — Next.js logo, "edit page.tsx to get started" placeholder text, links to Vercel templates. `package.json` has the standard scripts (`dev`, `build`, `start`, `lint`) and Next 16.2.12 / React 19.2.4.

**Not yet done, in order:**
1. A form component accepting `source`, `target`, `weight`
2. `fetch()` call to `/route` or `/compare`
3. Render the returned `path`/`edges`/`totals` as a readable itinerary
4. Mapbox visualization of the route
5. Error state for failed calls or no-route-found

---

## 6. Setup, installation & running

### Prerequisites
- Python 3.13 (confirmed via the committed venv metadata)
- Node.js 18+, npm

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn python-dotenv networkx
uvicorn app.main:app --reload --port 8000
```
⚠️ **Correction to a prior version of this doc:** it suggested running `uvicorn app.main:app --reload --factory --app-dir backend/app --port 8000` from the repo root. This does not work — `--factory` expects `app.main` to expose a factory *function*, but `main.py` defines `app` as a plain `FastAPI()` instance; and `--app-dir backend/app` combined with the `app.main:app` module path is inconsistent (if app-dir already points inside the package, the path should just be `main:app`). The command above (`cd backend` first, then the plain form) is the one that's actually been confirmed working.

⚠️ **Also note:** `backend/requirements.txt` is currently missing `networkx`, even though it's required. `pip install -r backend/requirements.txt` alone will leave `/route` and `/compare` broken with `ModuleNotFoundError`. Install `networkx` explicitly (as above) until that file is fixed, or use the root `requirements.txt` instead, which does include it.

Interactive API docs, once running: `http://127.0.0.1:8000/docs`

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Opens at `http://localhost:3000`.

---

## 7. Testing, linting & quality

Nothing set up yet.
- **Backend:** no tests exist. Recommend `pytest` with a `backend/tests/` folder — good first targets: graph construction (`build_graph` produces the right node/edge count), shortest-path correctness on the known corridor, and specifically the flat-fare aggregation (a 5-hop train journey should total ₹5, not ₹25).
- **Frontend:** `npm run lint` is configured (ESLint) but nothing custom has been added yet.

---

## 8. Deployment guidance (not started)

- **Backend:** containerize with a Dockerfile installing `backend/requirements.txt` (fix the missing-networkx issue first), copying `backend/app/`, running via `uvicorn`. Add `fastapi.middleware.cors.CORSMiddleware` before any frontend calls it in production — currently absent entirely.
- **Frontend:** `npm run build`, deploy to Vercel per the confirmed tech stack. Point API calls at the deployed backend URL, not `localhost`.

---

## 9. Known issues (see also the project handoff for the full, prioritized list)

1. `backend/requirements.txt` missing `networkx`
2. Root `.gitignore` malformed (literal `\n` characters instead of real line breaks — currently harmless since the frontend/backend subfolder `.gitignore` files correctly cover what matters, but should be fixed)
3. No CORS middleware — will block the first real frontend→backend call
4. Fare-zone edge case for direct Khandeshwar boarding (§4, flat-fare note)
5. Only one route per mode-pair exists, so `/compare` doesn't yet show a genuine trade-off frontier — cab always wins time, transit always wins cost

---

## 10. Extensibility & next steps

- Replace hardcoded `NODES`/`EDGES` with a Supabase-backed datastore (`nodes`/`edges` tables, PostGIS-enabled) — schema is designed, not yet created
- Replace placeholder distances/times with real transit data as it's gathered (one route leg still missing; alternate routes not yet collected)
- Add station-name-based lookups instead of requiring raw integer IDs
- Add multi-objective optimization (e.g., minimize time *and* cost jointly, not just one at a time)
- Add emissions as a 4th comparison metric
- Add caching for repeated route queries once query volume matters

---

## 11. References

- FastAPI docs: https://fastapi.tiangolo.com/
- NetworkX docs: https://networkx.org/
- Supabase docs: https://supabase.com/docs
- Next.js docs: https://nextjs.org/docs
