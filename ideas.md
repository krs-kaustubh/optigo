# Optigo — ideas.md: restart analysis, research and roadmap

*Written 2026-10-10 by Claude (Fable 5.1) at Kaustubh's request. Read-only analysis of the repo at `main` = `3684a7c` plus the uncommitted working tree, four web-research passes, and live OpenStreetMap queries. No file other than this one was created or edited. `backend/.env` was not read. The RailRadar API was not called.*

**How to read the tags**

| Tag | Meaning |
|---|---|
| `[code: path:line]` | Verified by reading that file in this repo on 2026-10-10. |
| `[test: …]` | Verified by running the offline test suite on 2026-10-10 (80 tests, 0.28 s, dummy env vars, no keys, no network). |
| `[osm: query]` | Result of an Overpass API query I ran on 2026-10-10 (bbox 18.93–19.22 N, 72.95–73.15 E unless stated). |
| `[verified: URL]` | A page that was actually opened on 2026-10-10. |
| `[snippet: URL]` | Seen only in a search-result snippet; not opened. |
| `[unverified]` | Could not be confirmed; treat as a hypothesis. |
| `[judgement]` | My opinion, not a fact. |

**At a glance (the ten things that matter)**

1. The backend is more finished than the docs say (6 endpoints, 80 passing offline tests, recorded live boards as fixtures), but it is a **static** router: no timetable, so it cannot answer "which train, arriving when" without RailRadar, and it cannot time a transfer. `[code]`
2. The frontend on `main` **does not build from a clean clone**: `frontend/package.json` at HEAD lacks seven runtime dependencies that the components import, and `postcss.config.mjs` was deleted in the frontend commit. The fixes exist only uncommitted on this machine. `[code]`
3. There is **no official public API** for Indian Railways running status. NTES's own disclaimer bans systematic downloading; CRIS's API gateway (Pravah) is partner-only. The one official-partner live feed for Harbour/Uran locals (Central Railway GPS on the Yatri app) is closed. `[verified]`
4. What *is* official and free: Central Railway's Harbour-line public timetable PDFs (w.e.f. 01.05.2026). That is the right foundation for a rewrite. The Uran/Kharkopar timetable is not on the page — ask for it (RTI or CR contact page). `[verified]`
5. NIC and CRIS are different organisations with different powers: NIC hosts data.gov.in; CRIS owns the train data. Your NIC contacts can help you find the right desk and frame an NDSAP "registered access" request, but cannot grant NTES access. `[verified]`
6. The cab layer's "official MMRTA auto rate" (₹28 + ₹18.66/km) is actually the **2022 black-and-yellow taxi** card. The official auto card is ₹26 + ₹17.14/km (w.e.f. 01.02.2025), with a 1 Sept 2026 revision to ₹27 + ₹18.22/km reported in the press. Uber/Ola/Rapido rate cards are unverifiable; Uber's price endpoints are partner-only; Ola's deep link needs an affiliate token; Rapido has no API. `[verified]`
7. The train fare slabs in `graph.py` do not match the only official suburban fare matrix found (WR, 2015): e.g. Churchgate–Dadar (~9 km) is ₹10, not ₹5. The metro chart (₹10→₹40) matches secondary sources. `[verified]`
8. OSM has ~1,100 bus-stop points and 26 railway stations in Navi Mumbai, but only ~8 NMMT bus-route relations (of NMMT's ~74 routes) and ~30 auto stands. Hot nodes can come from OSM; warm nodes (auto stands, share-auto routes) must largely be surveyed or crowdsourced. `[osm]`
9. Recommended rewrite stack (one recommendation): **GTFS files in git as the source of truth → a small RAPTOR router written in TypeScript that runs in the browser (and in a Cloudflare Worker for the API) → MapLibre + OpenFreeMap tiles → a Worker proxy for the RailRadar key.** MOTIS in Docker locally as the oracle to validate your router against. Python stays for offline data-building scripts only. Hosting cost: ₹0/month. `[judgement, with verified prices]`
10. Realistic first small win after the semester: a hand-built `gtfs/` for the Harbour line from the CR PDF that passes `gtfs-validator` and produces a correct "Panvel 08:10 → Vashi" plan in MOTIS. One weekend, no API keys, no servers.

---

## 0. Current system analysis (from the code, not the docs)

### 0.1 Repo state on 2026-10-10

| Item | State | Evidence |
|---|---|---|
| `main` HEAD | `3684a7c` "Merge pull request #3 from krs-kaustubh/himesh" (2026-10-08) | `git log` |
| Branches | `backend` (`303d576`), `feature/live-trains` (`2e1a32e`), `frontend-reference` (`647132f`) — **all merged into `main`** (`git branch --merged main`). Only `main` and `backend` exist on GitHub; `frontend-reference` is local-only. | `git branch -a -v`, `git ls-remote` |
| Uncommitted changes | `backend/app/main.py` (adds `_parse_endpoint_param`, `/compare` takes `str`), `frontend/package.json` (+7 runtime deps), `frontend/package-lock.json`, `frontend/next.config.ts` (removes `cacheComponents`, `partialPrefetching`, a Turbopack CSS rule), `frontend/components/plan/SchematicMap.tsx` (−1 line); untracked `frontend/postcss.config.mjs` | `git status`, `git diff` |
| Who changed what | Himesh's commit `2b34622` ("feat: implement frontend", author `LinuxGuy312`) also edited **backend** `graph.py` (+51: `haversine`, `_resolve_endpoint`) and `main.py` (+8: `/test`) | `git show --stat 2b34622` |
| Tests | 80 pass offline with dummy env vars; the suite's `clear_board_cache()` deletes `backend/.cache/railradar/*.json` as a side effect (it removed the stale `VSH_2h.json` from Oct 8 during my run) | `[test]`, `[code: backend/app/railradar.py:238-247]` |
| Fixtures | 12 real station boards captured 2026-10-05 17:42–17:43 IST with `hours=4` (PNVL 97 trains, VSH 132, BEPR 109, KARP 14, TRGR 15 …) plus response headers showing `x-ratelimit-limit-month: 1000`, `remaining-month: 834` | `[code: backend/tests/fixtures/boards/live-batch-1/manifest.json, PNVL.json]` |

### 0.2 Architecture and data flow in plain language

**Backend (FastAPI, Python 3.12).** One process, no database of its own.

1. A request hits `/compare?source&target[&live][&prefer_seat]`. Endpoints may now be a node id *or* `"lat,lng"` (uncommitted parsing in `main.py`; committed resolution in `graph.py`). `[code: backend/app/main.py:70-106, backend/app/graph.py:174-199]`
2. `graph.build_graph()` fetches **all nodes and all edges from Supabase on every request** (one RPC + one table select, retried once on transport errors) and builds a NetworkX `DiGraph`, adding reverse edges for every mode. `[code: backend/app/graph.py:97-134]`
3. If an endpoint is `lat,lng`, a synthetic node is injected and joined to the 3 nearest stations by straight-line walking edges at 5 km/h. `[code: backend/app/graph.py:174-199]`
4. Three Dijkstra runs: on `time`, on `distance`, and on a per-edge "fare weight". The "cost" candidate is whichever of the three has the lowest cumulative per-mode slab fare. Exactly 3 results are returned; duplicates are normal. `[code: backend/app/graph.py:223-250]`
5. With `live=true`, `railradar.annotate_route_with_live_status()` finds the first contiguous train leg, maps station names to RailRadar codes, fetches that station's live board (cached 60 s in memory **and on disk**, client-side 10/min limiter, 429 cached 60 s), and keeps only trains whose source→destination, placed on a hand-coded corridor list, pass the boarding station strictly before the alighting station. `[code: backend/app/railradar.py:69-85, 118-137, 187-236, 296-337]`
6. With `prefer_seat=true`, `alternatives.annotate_route_with_alternatives()` fetches boards for up to 2 "pivot" origin stations (hours=4) and pairs a leg-1 train with a train originating at the pivot, computing `extra_minutes` against the next direct train. `[code: backend/app/alternatives.py:45-92, 134-395, 398-464]`
7. `/cabs/estimate` returns fare *formulas* (haversine × 1.30, 25 km/h, hard-coded base + per-km + per-minute) and deep links for four providers; ETAs are constants. `[code: backend/app/cabs.py:499-507, 557-749]`

**Frontend (Next.js 16, React 19, Tailwind 4, React Query, framer-motion).** Landing page → `/plan?from&to`. Fetches `/nodes` once and `/compare?live=<bool>` per search (**live defaults to on**), dedupes identical paths, draws a hand-positioned SVG schematic, shows a live board in the details panel. `[code: frontend/lib/api.ts:34-37, frontend/app/plan/page.tsx:22, frontend/components/plan/SchematicMap.tsx:13-39]`

**Data.** 24 nodes / 26 directed edges in Supabase (Harbour Vashi–Panvel, Uran branch to Kharkopar via Sagar Sangam, Metro Line 1 Belapur–Pendhar via RBI, one Kharghar↔Belpada walk). `[code: sql-schema/seed.sql]`

### 0.3 What works (with evidence)

| Claim | Evidence |
|---|---|
| Route candidates, error contract (`{"detail","error"}` with 404/400/422/502) | `[test: test_routing_errors.py 20 tests]` |
| Corridor-model filtering gives only boardable, right-direction trains for the 8 brief journeys, against real boards | `[test: test_phase_b_railradar.py 12 tests on live-batch-1 fixtures]` |
| Ghost-train, symmetric midnight wrap, tz-normalisation, parse-failure isolation | `[code: railradar.py:255-283, 286-310, 328-335]`, `[test]` |
| Quota guards: 60 s cache keyed by (station, hours), disk cache, 10/min limiter, 429 cache, quota header captured | `[code: railradar.py:150-236]` |
| Backing and switching produce plausible alternatives for Khandeshwar→Nerul and Kharghar→Vashi on fixtures | `[test: test_phase_c_alternatives.py]` |
| Fixture-capture discipline (`scripts/capture_boards.py`: pacing, header capture, never prints the key) | `[code: backend/scripts/capture_boards.py]` |
| Frontend: pickers, 3 cards, dedupe, live board with countdown, theme, mobile bottom sheet | `[code: frontend/components/plan/*]` |

### 0.4 What is fragile

| Problem | Where | Why it matters |
|---|---|---|
| Two Supabase round-trips **per request**, no cache; Supabase free projects **pause after 1 week of inactivity** | `graph.py:97-134`; `[verified: https://supabase.com/pricing]` | A demo after a quiet week starts with 502s. |
| Rate limiter and caches are process-local globals | `railradar.py:150-156` | Two uvicorn workers = 20/min against a 10/min key. |
| Public, unauthenticated `/compare?live=true` spends your monthly RailRadar quota (1,000/month on your key `[code: fixtures headers]`; railradar.in/docs now advertises a 100/month sandbox `[verified: https://railradar.in/docs]`) | `main.py:81-92` | ~33 calls/day; one bot or one busy demo day exhausts it. |
| Live default **on** in the frontend | `frontend/lib/api.ts:36`, `plan/page.tsx:22` | Every search costs quota; the handoff asked for live only when requested. |
| Corridors, station codes, origins, display names are hand-coded in three files | `railradar.py:37-85`, `alternatives.py:24-32` | Adding Thane/CSMT or a new line means editing Python in several places. |
| Alternatives fall back to `stops × 3 min` when a train is not on the pivot board; `extra_minutes` falls back to constants 5/10 | `alternatives.py:228, 254, 259, 323, 338, 352` | Fabricated numbers can reach the UI. |
| "Same rake" detection compares train numbers; a turnaround is a different train number on these boards (see PNVL fixture: 98175 arrives, 98180/98182 depart) so it never fires | `alternatives.py:354` | The "stay on board" advice never appears. |
| `calls_used` counts fetch *invocations* including cache hits | `alternatives.py:441-444` | Misreports quota usage. |
| `EMU` is the only accepted train type; whether AC locals carry another type is unknown | `railradar.py:88`; PNVL fixture shows types `EMU, MEMU, Mail/Express, …` | AC locals may be silently dropped. `[unverified]` |
| `lat,lng` endpoints use straight-line walking at 5 km/h to 3 nearest stations | `graph.py:186-195` | Across a creek or highway the walk can be fiction. |
| Cab ETAs are constants (3/4/5/6/7 min); fares use unverified rate cards; disclaimer claims "official MMRTA meter rates" | `cabs.py:548, 593, 605, …, 800-804` | Presented as data; see §3 for what's actually official. |
| Frontend `RouteDetails` shows "Metro-only route: live times aren't available" whenever `live_status` is absent — i.e. for **every** route when the live checkbox is off | `frontend/components/plan/RouteDetails.tsx:14-19` | Misleading UI state. |
| Badges: `dedupeRoutes` produces `"Time"/"Distance"/"Cost"`, but the card checks for `'Fastest'/'Shortest'`, so icons/colours never apply and cards read "Time", "Distance", "Cheapest" | `frontend/lib/route-utils.ts:45-47`, `ResultsList.tsx:87-93` | Cosmetic, but shows the two halves were not integrated. |
| `frontend/lib/types.ts` has no `parse_failed` reason, no `live_alternatives`, no cab types; nothing in the UI calls `prefer_seat` or `/cabs/estimate` | `types.ts:36-48` | Phases C and E have no UI. |
| Root `package.json` dev script hard-codes a Windows venv path (`..\\.venv\\Scripts\\uvicorn`) | `package.json:4` | Does not run on this Linux machine. |
| Leftover `GET /test` ("hello from updated main") committed | `main.py:59-61` | Debug endpoint in production. |

### 0.5 What is unfinished

- **Frontend on `main` cannot be built from a fresh clone**: HEAD `frontend/package.json` lists only `next`, `react`, `react-dom`; the code imports `@tanstack/react-query`, `framer-motion`, `lucide-react`, `next-themes`, `react-zoom-pan-pinch`, `clsx`, `tailwind-merge`; `postcss.config.mjs` was deleted in `2b34622`; HEAD `next.config.ts` references `@tailwindcss/turbopack`, which is not a dependency. All fixes are uncommitted here. `[code: git show HEAD:frontend/package.json; git diff]`
- `lat,lng` endpoint support is half-landed (parsing uncommitted, resolution committed, undocumented, untested). `[code]`
- No UI for seat alternatives or cabs; `prefer_seat` and `/cabs/estimate` are backend-only. `[code]`
- No deployment, CORS still `localhost:3000` only. `[code: main.py:25-30]`
- Schematic map layout is hand-typed per station; `/nodes` lat/lng are fetched but unused for layout. `[code: SchematicMap.tsx]`
- Fare slabs, NMMT, buses, hot/warm nodes, real map: not started (PROTOTYPE_BRIEF Phases D and F). `[code: PROTOTYPE_BRIEF.md]`

### 0.6 Doc vs code mismatches found

| # | Doc says | Code/repo is | Where |
|---|---|---|---|
| 1 | README "Status (2026-10-05): … Frontend owner building against API contract"; "frontend/ Next.js 16 scaffold"; ARCHITECTURE "untouched create-next-app scaffold" | Frontend implemented and merged on 2026-10-08 | `README.md`, `ARCHITECTURE.md` "Frontend" |
| 2 | ARCHITECTURE/backend README: **5** endpoints | **6** (`/test` exists) | `main.py:59` |
| 3 | ARCHITECTURE: `/route` and `/compare` `source`,`target`: int | `str`; `"lat,lng"` accepted (`/route` committed, `/compare` uncommitted) | `main.py:70-92` |
| 4 | ARCHITECTURE: alternatives "fall back to edge times if train record absent" | Fallback is `stops × 3` minutes; graph edge times are never read | `alternatives.py:228,254,323,338` |
| 5 | `future-ideas.md` Idea 2: pivots include **junctions** and a **time variant** | Only `ORIGIN_STATIONS`, seat variant only; `prefer_seat` is not used inside `compute_alternatives` | `alternatives.py:24,45-92,134-140` |
| 6 | ARCHITECTURE header: "Verified … commit 3f8b4d8d, re-audited 2026-09-23" | Document also describes Oct-5 modules; header never updated | `ARCHITECTURE.md:3` |
| 7 | `future-ideas.md` header: "Kept out of git (see .gitignore)" | Tracked since 2026-09-23 | `.gitignore` |
| 8 | `future-ideas.md` Idea 6 references `frontend/app/components/RouteCard.tsx` | Card lives in `frontend/components/plan/ResultsList.tsx` | — |
| 9 | README roadmap: backing unchecked, "Frontend Phase 2 in progress" | Backing/switching implemented; frontend merged | `README.md` Roadmap |
| 10 | `sql-schema/README.md`: Belapur↔RBI↔Belpada "1.0 km each"; `seed.sql` 1.0/1.0 | `6. Distance Update` sets 0.5/0.5; `update-node-edge-data` 0.4/0.4; README's "known result" 10.2 km for Belapur→Pendhar only works with 0.5 (seed gives 11.2). Which the live DB holds is unknown (I did not query Supabase). | `sql-schema/*` |
| 11 | `cabs.py` docstring, ARCHITECTURE, log: "Official MMRTA … ₹28 base + ₹18.66/km" for autos | That is the 01.10.2022 **taxi** card; auto was ₹23+₹15.33 (2022), ₹26+₹17.14 (01.02.2025) `[verified: §3.4]` | `cabs.py:531-535` |
| 12 | `log.md` | No entries for the Oct 7–8 merges, `/test`, `lat,lng` endpoints, or the frontend | `log.md` |
| 13 | `handoff.md`/types: `live_status.reason` set | Code also emits `parse_failed`; frontend union lacks it | `railradar.py:333`, `types.ts:38` |
| 14 | README "26 directed edges … reverse edges added in code" | True, but the 2 walking edges are stored in both directions **and** reversed again (harmless duplicate) | `seed.sql`, `graph.py:131-132` |

### 0.7 Keep or drop in a restart

| Keep (and why) | Drop (and why) |
|---|---|
| **Corridor knowledge** (which trains stop where, Thane trains skip Sanpada/Vashi, two Uran feeders) — but as *data* (GTFS `routes`/`trips`), not Python lists. `[code: railradar.py:69-85]` | **NetworkX static Dijkstra + per-request Supabase fetch** — a timetable router replaces it. |
| **Recorded boards + capture script + offline-test discipline.** These 12 fixtures are the only ground truth you own; they also contain `stop.distance`/`sequence` per train (usable to cross-check chainage). `[code: fixtures PNVL.json]` | **`cost` column, `/route`, `shortest_path_cost_approx`** — a hack around not having fares as a first-class criterion. |
| **Fare mechanism** (cumulative per-mode slab, walking free) — keep the shape, re-source the numbers (§3.4). | **Supabase at runtime** — free tier pauses; the data is 24 rows and belongs in git. |
| **Error contract** `{"detail","error"}` and the reason-code pattern for live status ("never silent"). | **`cabs.py` rate cards, constant ETAs, "official" wording** — replace with official tariff cards + regulated band (§3.4). |
| **Pairing logic of backing/switching** — re-express it on scheduled times (§5). | **Hand-typed `SchematicMap` layout**, `/test`, Windows-only root script, duplicate endpoint parsing. |
| **Himesh's UI** (visual system, React Query, dedupe/merge helpers, bottom sheet) — port, don't rewrite. | **`prefer_seat` as a query flag** — becomes a routing criterion (§5). |
| **Station coordinates** (`seed.sql`) → `stops.txt`. | **Disk cache in `backend/.cache`** — replace with a proper cache or Worker KV. |
| **Docs culture** (ARCHITECTURE as ground truth, log, handoff) — but automate the parts that drift (endpoint list, test counts). | |

---

## 1. Vision and what a restart would fix

**Vision.** *A door-to-door Navi Mumbai planner that is honest about what it knows: timetable-based rail + metro routing with real transfer timing, first/last mile by NMMT, auto, share-auto or cab with clearly labelled estimates, a live overlay only where a legitimate source exists, and seat-aware alternatives (backing/switching) as first-class journey options.* It should run offline from a phone, cost nothing to host, and publish its data (GTFS) so others can build on it.

**What the current design cannot do, honestly:**

| Limitation | Root cause |
|---|---|
| Cannot say "take the 08:14, arrive 08:48" without RailRadar; cannot plan for a future departure time; cannot check whether a Belapur rail→metro transfer is feasible (Idea 5) | No timetable; edges carry a single `time` number |
| Cannot route from an address or to the airport; the `lat,lng` hack walks in straight lines | No street network, no geocoder |
| Cannot include buses, autos, share-autos | 24 nodes, no bus data, no place for informal modes in the model |
| Live data covers only one station per route and only trains; it is an unofficial crowd-sourced source with a 1,000/month cap | RailRadar is the only live source; see §3 |
| Fares are guesses for trains; cabs are formulas | No official fare source wired in |
| Cannot grow: every new line means Python edits in 3 files | Corridor model is code, not data |
| Dies when Supabase pauses or when a demo burns the quota | Runtime dependencies on free tiers with inactivity rules |
| Shows alternatives only as a bolt-on JSON block | Backing/switching live outside the router |

**What a restart fixes:** timetable routing (RAPTOR) makes transfer feasibility, departure-time planning, AC/non-AC and frequency-based metro/bus free; GTFS makes the network data-driven; a street router or precomputed access edges give real first/last mile; a static deployment removes the free-tier failure modes; backing/switching become Pareto-optimal journeys, not a separate engine.

**Principles to carry over:** present, don't decide; never silent on failure; label every estimate; protect quota; tests on recorded data.

---

## 2. Hot / warm node model

### 2.1 Definitions

| Tier | Definition | Examples in Navi Mumbai | Has a timetable? | Source quality |
|---|---|---|---|---|
| **Hot** | Fixed, scheduled, high-capacity interchange points: railway stations, metro stations, bus depots/terminals, the airport terminal | Vashi, Belapur CBD, Panvel, Pendhar, Vashi/Belapur/Kharghar bus depots, NMIA T1 | Yes (or headway) | Official PDFs + OSM |
| **Warm** | Small, semi-formal boarding points with no official schedule: ordinary bus stops, auto-rickshaw stands, share-auto stands and their fixed routes | "Seawoods Station Rickshaw Stand", "Share Rickshaw To Amar Nagar (Rs.20 per seat)" `[osm]` | No (headway or "on demand") | OSM partial; survey/crowdsource |
| **Cold** *(optional third tier)* | Any lat/lng: homes, offices, temples (the "Panvel → temple in Airoli" case from PROTOTYPE_BRIEF) | — | — | Geocoder |

### 2.2 Data model (GTFS-first, with one extension table)

Use GTFS as the primary schema so every tool and engine works unchanged `[verified: https://gtfs.org/documentation/schedule/reference/]`:

- `stops.txt` — every hot and warm node. Use `location_type` (0 stop/platform, 1 station, 2 entrance) and `parent_station` to group platforms/entrances under a station. `[verified: same]`
- `routes.txt`, `trips.txt`, `stop_times.txt`, `calendar.txt` — rail and metro from official PDFs; NMMT as headway-based trips via `frequencies.txt` (`exact_times=0`) `[verified: https://gtfs.org/documentation/schedule/reference/ (frequencies.txt)]`.
- `transfers.txt` / `pathways.txt` — minimum transfer times (Belapur rail↔metro, Kharghar↔Belpada walk).
- **Extension `optigo_nodes.csv`** keyed by `stop_id`: `tier` (hot/warm), `node_kind` (rail, metro, bus_depot, bus_stop, auto_stand, share_auto_stand, airport), `operator`, `osm_id`, `confidence` (official / osm / surveyed / user-reported), `last_verified`.
- **Extension `share_auto_routes.csv`**: `from_stop_id`, `to_stop_id`, `fare_per_seat`, `typical_wait_min`, `hours`, `source`, `last_verified` — modelled as GTFS routes with `route_type=3` and `frequencies.txt`, but flagged `confidence=surveyed`.

### 2.3 Data sources

| Source | What it gives | Coverage measured | Terms |
|---|---|---|---|
| **OpenStreetMap via Overpass** (one-time extract, not at request time) | `railway=station` (46 features incl. ways), `highway=bus_stop` (≥400 sampled; ~1,104 in a wider box per a second query), `amenity=taxi` (30 nodes), `route=bus` relations (184 in wide box, mostly BEST/TMT; **8 tagged NMMT**), `public_transport=platform` (~1,035) | `[osm: 2026-10-10, overpass-api.de and maps.mail.ru mirror]` | ODbL; attribution required `[verified: https://www.openstreetmap.org/copyright]`. Overpass public policy: <10k queries/day, no parallel scripts; the main server returned 504s during my queries — extract once with osmium from the Geofabrik "Western Zone" file (210 MB) `[verified: https://wiki.openstreetmap.org/wiki/Overpass_API, https://download.geofabrik.de/asia/india.html]` |
| OSM bus-stop quality | In a 400-stop sample: ~35% have `name`, ~90% `operator` (NMMT/TMT/BEST), ~88% `public_transport`, **0 `route_ref`** | `[osm]` | Stops exist as points; which route serves them is mostly missing. |
| OSM auto stands | 30 `amenity=taxi` nodes; names like "Auto Stand", "Rickshaw Stand", one `taxi_vehicle=auto_rickshaw`, one share-rickshaw with "Rs.20 per seat" | `[osm]` | Effectively unmapped relative to reality; no tag for share-auto routes exists (`taxi_vehicle=auto_rickshaw` 1,634 uses worldwide vs `taxi_type=auto_rickshaw` 5) `[verified: https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dtaxi, taginfo]` |
| **Central Railway PTT PDFs** | Harbour DN/UP w.e.f. 01.05.2026, Harbour AC, Trans-Harbour (13.01.2024), Port Line; **no Belapur/Nerul–Kharkopar file** | `[verified: https://cr.indianrailways.gov.in/view_section.jsp?lang=0&id=0,5,2360]` | Official; manual/semiautomatic parsing |
| **CIDCO budget 2026-27** | Metro Line 1: 11 stations, 11.10 km; Line 1A (Belapur→Sagar Sangam, 2 stations), Line 2 (Pendhar→NMIA T4, 11 stations), Line 8 CSMIA–NMIA (2030 target) | `[verified: https://cidco.maharashtra.gov.in/Upload/20260513111413224.pdf]` | Official |
| **NMIA ground access** (Adani release 5 Oct 2026) | NMMT routes A1–A7 to Kharkopar, Targhar, Belapur, Nerul, Panvel, Khandeshwar; Chalo Bus to Mumbai; MSRTC e-Shivai; free CSMIA shuttle | `[verified: https://www.adani.com/newsroom/media-releases/navi-mumbai-international-airport-offers-affordable-multimodal-travel-with-buses-taxis-autos]` | The airport is a new hot node with published feeders |
| NMMT | 567 buses / 74 routes / avg headway 15 min; live tracking only in the "Apali NMMT" app (seller NMMC); no route/timetable PDFs on the SPA site | `[snippet: https://online.nmmc.gov.in/navimumbai/nmmt]`, `[verified: https://apps.apple.com/in/app/nmmt-bustracker/id1235574124, https://www.nmmc.gov.in/nmmt]` | No data export; routes must be transcribed from the app/stop boards |
| Community GTFS `croyla/mumbai-gtfs` | BEST + TMT + KDMT, MIT-0, dataset 2026-08-20, service to 2027-02-15; **no NMMT** | `[verified: https://mobilitydatabase.org/feeds/gtfs/mdb-3138, https://github.com/croyla/mumbai-gtfs]` | Reusable as-is for BEST routes into Vashi/Belapur |
| Your own survey / crowdsourcing | Share-auto stands, routes, per-seat fares, hours | — | Needed for warm nodes; see Idea 6.10 |

### 2.4 How tiers connect

- **Hot↔hot**: scheduled trips (rail, metro) or frequency trips (NMMT trunk routes, airport feeders).
- **Warm→hot**: access edges. Compute walking time on the street network once (OSRM/Valhalla on the Navi Mumbai extract) for every warm node to its k nearest hot nodes; store as `transfers.txt` rows or a precomputed `access.csv`. Straight-line × 1.3 only as the fallback for unmapped areas, and label it. `[judgement]`
- **Cold→warm/hot**: at query time, snap the user's point to the nearest street node and take the precomputed/online walk to the nearest few nodes of either tier.
- **Share-auto**: a warm→warm or warm→hot edge with `headway` (typical wait), `fare_per_seat`, `hours`; `confidence=surveyed`.
- **Cab/auto on demand**: an edge available from any node, cost from the official tariff card (§3.4), time from road distance; shown only when it saves ≥ N minutes or when no scheduled option exists.

### 2.5 Effects on routing and the map

- **Routing**: RAPTOR treats all tiers the same; the tier affects *transfer penalties* (hot: known concourse times; warm: larger uncertainty → add 2–5 min and a "may vary" label), *pruning* (prefer hot-to-hot legs when times are close), and *confidence propagation* (a journey's confidence = min over its legs; show it).
- **Map**: hot nodes always visible with icons by `node_kind`; warm nodes appear from zoom ≈14; share-auto routes drawn dashed; airport feeders as a distinct layer; a "verified / OSM / reported" badge per node drives both the style and a "report a correction" action (which becomes an OSM edit or a `share_auto_routes.csv` PR).
- **Decision from PROTOTYPE_BRIEF Phase F** ("display layer or real graph nodes?"): make hot nodes real graph nodes from day one (they are stops in GTFS anyway); make warm nodes real only where an access edge or a surveyed share-auto route exists; everything else is display-only until surveyed. `[judgement]`

---

## 3. Live data access plan

### 3.1 Rail — what exists and who owns it

| Entity | What it is | What it provides | Access for a student |
|---|---|---|---|
| **CRIS** (Centre for Railway Information Systems) | "An organization under Ministry of Railways", est. 1986, 1,300+ staff; builds and runs PRS/CONCERT, UTS, NGeT (IRCTC backend), **NTES**, RailOne app, RailMadad, FOIS, COA, RTIS, eDrishti/RailDrishti | All train-running and timetable data | No public API, no developer programme, no open data; site allows RTI (₹10) and says material reuse requires permission `[verified: https://cris.org.in/, https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/aug/doc202686945401.pdf]` |
| **NTES** (enquiry.indianrail.gov.in) | CRIS-built public enquiry site | Live running status, live station boards | Disclaimer forbids building a database, "regularly or systematically downloading and storing" pages, reuse on other sites, and commercial use `[verified: https://enquiry.indianrail.gov.in/mntes/disclaimerDisplay.html]`. Homepage links Mumbai suburban users to zonal pages rather than serving locals directly `[verified: https://enquiry.indianrail.gov.in/mntes/]`. Whether Live Station lists EMU locals: `[unverified]` |
| **Project Pravah** (CRIS API gateway on WSO2, since 15 Aug 2021) | Internal/partner API manager: ~1.25 M calls/day, 140+ APIs, consumers include NeGD/UMANG, IRCTC 139 IVRS, e-Catering, freight customers | The APIs you would want | Partner-only; no public portal URL `[verified: https://wso2.com/br/customers/cris-revolutionizes-indian-railways-wso2/ (vendor source)]` |
| **Central Railway (Mumbai Division)** | Operator of Harbour/Trans-Harbour/Uran lines; took over the CIDCO-built stations by Aug 2026 | **Public timetable PDFs** (Harbour DN/UP and AC w.e.f. 01.05.2026; Trans-Harbour 13.01.2024; Port Line 15.12.2025) | Free download; Uran line PDF missing from the page `[verified: https://cr.indianrailways.gov.in/view_section.jsp?lang=0&id=0,5,2360, https://www.outlookbusiness.com/news/central-railway-assumes-charge-of-14-navi-mumbai-suburban-stations-from-cidco]` |
| **CR GPS on Yatri app** (CDP Yatri Pvt Ltd, "official partner" of CR/WR Mumbai Division) | GPS devices on all CR suburban rakes since 13 Jul 2022, incl. Harbour, Trans-Harbour, Belapur/Nerul–Kharkopar; 15 s refresh | The best live feed for your lines | Closed; no API `[verified: https://www.freepressjournal.in/mumbai/mumbai-central-railways-live-location-feature-on-yatri-app-receives-stellar-response (news), https://apps.apple.com/us/app/-/id1563046909, https://frontiertech.niti.gov.in/story/how-yatri-is-transforming-mumbais-public-transport-through-data-and-ai/]` |
| **MRVC** | MoR:GoM PSU for Mumbai suburban projects | Corporate plan with crush-load and MUTP facts; no timetable/GTFS | Documents only `[verified: https://mrvc.indianrailways.gov.in/]` |
| **RailRadar** (what you use) | "Independent crowd-powered real-time train tracker", "EST. 2026", "not affiliated with Indian Railways, IRCTC, or NTES"; data from app GPS pings, "publicly accessible databases", and its own structured schedules | Station boards, suburban timetables, "NTES and compressed feeds" endpoint families | Bearer key; your key's headers show 10/min and **1,000/month** `[code: fixtures]`; docs page now says free sandbox **100 requests/month** `[verified: https://railradar.in/docs]`; terms silent on academic use, redistribution and attribution; legal entity not named `[verified: https://railradar.in/terms, /about, /privacy]`. Given the NTES disclaimer, any NTES-derived content is in tension with CRIS terms. `[judgement]` |
| Other third parties | erail.in API dead (DNS); indianrailapi.com (pricing behind login, source unstated); RapidAPI "IRCTC1" unofficial; Where Is My Train (Google; cell-tower + crowd; no API); RailYatri/ixigo/ConfirmTkt no public API | — | In June 2025 Railways publicly told passengers to use only NTES and named RailYatri, ixigo Train and Where Is My Train as sources of incorrect information `[verified: https://www.india.com/news/india/indian-railways-irctc-rail-apps-digital-india-ntes-app-cris-rail-yatri-ixigo-train-where-is-my-train-modi-ashwini-vaishnaw-7863321/ (news)]` |
| Community GTFS "Indian Railways, Unofficial" (mdb-2867, `Neo2308/indianrailways-gtfs`) | 8,550 stops, 10,594 routes, one trip each; only 14 stop_times at Harbour stations from locals; Uran stations absent; no licence | Long-distance only | **Not usable for the Harbour line** `[verified: https://mobilitydatabase.org/feeds/gtfs/mdb-2867, https://github.com/Neo2308/indianrailways-gtfs]` |
| data.gov.in / API Setu | "Indian Railways Train Time Table" catalog exists but has **zero resources**; API Setu lists no railway API | — | `[verified: https://www.data.gov.in/catalog/indian-railways-train-time-table, https://apisetu.gov.in/]` |

**CRIS vs NIC — the distinction your contacts need you to understand**

| | CRIS | NIC |
|---|---|---|
| Parent | Ministry of Railways `[verified: https://cris.org.in/]` | MeitY (est. 1976) `[verified: https://en.wikipedia.org/wiki/National_Informatics_Centre]` |
| Runs | NTES, PRS, UTS, FOIS, COA/RTIS, RailOne, Pravah gateway | NICNET, MeghRaj cloud, government portals/email, **data.gov.in** (built by NIC under NDSAP §12) `[verified: NDSAP 2012 text at https://transdev.assam.gov.in/sites/default/files/menu/document/pndd_medhassu_in/ndsap-30jan2012.pdf]` |
| Owns train data? | **Yes** (on behalf of Railway Board) | **No** — hosts the platform; publishes only what MoR/CRIS upload |
| Can grant you | NTES/timetable access (never done publicly); RTI documents | Advice on the NDSAP "Registered access" process; possibly an introduction to the MoR data desk; nothing about live trains |
| API Setu | not CRIS | run by DIC/NeGD/MeitY, not NIC `[verified: https://apisetu.gov.in/]` |

What your NIC contacts *can* realistically do `[judgement]`: explain how a ministry publishes to data.gov.in and who in MoR nominates datasets; tell you whether an academic "registered access" path has ever been used for railway data; and, because UMANG (NeGD/MeitY) already consumes CRIS APIs via Pravah `[verified: WSO2 page above]`, point you to the MeitY-side counterpart who knows the CRIS API desk. Ask them for a *name of a desk*, not for data.

### 3.2 What is actually obtainable, in order of realism

1. **Static official timetable (now, free, legal).** Parse CR's Harbour DN/UP and AC PTT PDFs (w.e.f. 01.05.2026) into GTFS. Keep the "effective from" date and the source URL in `feed_info.txt`. `[verified: CR page above]`
2. **Uran line timetable.** Not on the CR page. Ask via the CR "Contact Us" page or file an RTI (₹10) for the Belapur/Nerul–Kharkopar PTT; alternatively transcribe departures from the recorded RailRadar boards you already have (KARP 14 and TRGR 15 trains in a 4-hour window `[code: fixtures]`) and label them `confidence=observed`.
3. **RailRadar as an unofficial, best-effort overlay** — delays and platforms only, never the base timetable; attribute it as "crowdsourced, not affiliated with Indian Railways"; keep the quota maths visible (1,000/month ≈ 33 calls/day ≈ 10–30 live searches/day with the 60 s cache).
4. **NDSAP "Registered access" request to Railway Board/CRIS** (template below). NDSAP defines Open / Registered / Restricted classes and lets the data owner set access and pricing (§11) `[verified: NDSAP PDF]`. Expect no answer; document the attempt in your report.
5. **Institutional doors that are actually open**: the Indian Railways Innovation Policy ("Startups for Railways", E&R 01/2022) explicitly encourages "individual innovators and R&D institutions" to apply against published problem statements `[verified: https://rskr.irimee.in/forum/wp-content/uploads/2023/08/2022-Indian-Railways-Innovation-policy.pdf]`; Smart India Hackathon has Ministry of Railways problem statements `[verified: https://www.sih.gov.in/]` — note SIH gives problems, not APIs.
6. **Yatri / CR GPS feed** — only via a CR-level partnership; not a student path. `[judgement]`

### 3.3 Draft request email (fill the placeholders; send via your college)

> **Subject:** Request for academic, read-only access to Mumbai suburban timetable / running-status data (NDSAP registered access) — [College name], [Course, Year]
>
> Dear Sir/Madam,
>
> I am [Full name], a second-year [Branch] student at [College, University], working under the guidance of [Guide name, designation] on an academic project, *Optigo*, a journey planner for Navi Mumbai that combines the Harbour, Trans-Harbour and Belapur/Nerul–Kharkopar suburban lines with Navi Mumbai Metro Line 1 and NMMT buses.
>
> The project is non-commercial, open-source ([repository URL]), and will be submitted as [Mini Project / Major Project] in [month, year]. Today it uses the public timetable PDFs published by Central Railway and a third-party crowdsourced service for live status. I would like to replace the latter with data from the owner.
>
> I request, under the National Data Sharing and Accessibility Policy (2012) "Registered access" category, one or both of:
> 1. A machine-readable (CSV/Excel) copy of the current Mumbai suburban public timetable for the Harbour, Trans-Harbour and Belapur/Nerul–Kharkopar lines, including the Belapur–Kharkopar line which is not on the Central Railway timetable page; and
> 2. Read-only access to live running-status information (expected departure, platform, delay) for suburban services at the Navi Mumbai stations listed in the annexure, at a rate not exceeding [N] requests per minute, for the duration of the project ([start]–[end]).
>
> I undertake to: use the data only for this academic project; not redistribute raw data; attribute [CRIS / Central Railway] in the application and the report; respect any rate limits or technical conditions you set; and delete all stored data at the end of the project on request. A letter from my institution confirming the project is attached.
>
> If this request should be addressed to a different office (for example the Mumbai Division of Central Railway, or the Railway Board's data/IT directorate), I would be grateful for a pointer.
>
> Thank you for your time.
>
> [Full name] · [College] · [Email] · [Phone]
> Guide: [Name, designation, institutional email]
> Annexure: station list with codes (VSH, SNCR, JNJ, NEU, SWDK, BEPR, KHAG, MANR, KNDS, PNVL, TRGR, BMDR, KARP); project summary (1 page).

Where to send: Railway Board "Contact Us" `[verified href: https://indianrailways.gov.in/railwayboard/view_section.jsp?lang=0&id=0,7]`; CRIS contact/RTI section `[verified: https://cris.org.in/#contact]`; Central Railway contact page `[verified: https://cr.indianrailways.gov.in/view_section.jsp?lang=0&id=0,7]`. Do not copy email addresses from third-party sites; use the forms/addresses on those official pages. A short variant of the same letter to CR Mumbai Division asking only for the Belapur–Kharkopar PTT is the most likely to succeed. `[judgement]`

### 3.4 Metro, bus, cab/auto — what exists, what doesn't, fallbacks

**Navi Mumbai Metro Line 1 (Belapur–Pendhar).** Owner CIDCO; O&M by Maha Metro (10 years), with Konkan Railway supplying operating staff from 1 Apr 2024 `[verified: https://en.wikipedia.org/wiki/Line_1_(Navi_Mumbai_Metro), https://www.freepressjournal.in/mumbai/navi-mumbai-krcl-takes-charge-of-nm-metro-operations-for-next-3-years]`. Commercial service since 17 Nov 2023; 11 stations, 11.10 km `[verified: Wikipedia; CIDCO budget PDF]`. **Fare chart ₹10 (0–2 km) / 15 / 20 / 25 / 30 / ₹40 (>10 km) — matches `graph.py`** `[verified: https://themetrorailguy.com/navi-mumbai-metro-information-map-updates/ (secondary; no official CIDCO fare PDF found)]`. Timetable revised 13 Jul 2026 (one-way 25 min 30 s) `[verified: https://www.freepressjournal.in/mumbai/navi-mumbai-metro-line-1-cidco-cuts-belapur-pendhar-travel-time-by-90-seconds-from-july-13]`; headway 10–15 min and hours ~06:00–22:00 `[snippet: housing.com, thecsrjournal.in]`. Station 10 is "Pethali–Taloja" on Wikipedia and "Panchanand" on themetrorailguy — your DB uses the former; check a station board. No app, no API, no open data found. **Fallback:** `frequencies.txt` with the observed headway; no live layer; say so in the UI.

**NMMT.** No published route list, timetable or non-AC fare chart; live tracking only inside "Apali NMMT" (formerly NMMT BusTracker, seller NMMC) `[verified: App Store]`; ITMS with GPS on 500+ buses `[snippet: FPJ 2021]`; AC fares min ₹10 / max ₹65 (MMRTA, Oct 2021) `[verified: https://www.freepressjournal.in/mumbai/navi-mumbai-nmmt-ac-bus-fares-down-by-46]`. **Fallback:** transcribe the routes you need (airport A1–A7, station feeders) from the app and stop boards into frequency-based GTFS; crowdsource corrections.

**BEST / Chalo.** Chalo covers BEST only (live tracking, crowding indicator, tickets); no developer API `[verified: https://chalo.com/mumbai]`. BEST fares from 9 May 2025: non-AC ₹10 (≤5 km) rising by 5-km bands `[verified: https://www.theweek.in/wire-updates/national/2025/05/08/bes25-mh-ld-best-fare.html]`. Community GTFS exists (above).

**Mumbai One (MMRDA).** Launched 9 Oct 2025; 11 operators including Navi Mumbai Metro, Mumbai Suburban, BEST, TMT, NMMT; multimodal journey planner and single QR; hosted on GCP; **no API or open data mentioned** `[verified: https://mmrda.maharashtra.gov.in/sites/default/files/2025-10/mumbai_one_app_press_release.pdf]`. Implication: the state already ships an integrated planner; Optigo's value must be transparency, seat logic, informal modes, open data and offline — not "one app for everything". `[judgement]`

**ONDC/Beckn.** Mumbai Metro Lines 2A/7 ticketing on ONDC since Dec 2025; Chennai/Kochi metros earlier; Namma Yatri is AGPL open source but serves Bengaluru, Delhi, Hyderabad, Chennai, Kochi, Mysore, Tumkur — **not Mumbai** `[verified: https://egov.eletsonline.com/?p=103717, https://github.com/nammayatri/nammayatri, https://apps.apple.com/in/app/namma-yatri-ride-booking-app/id1637429831]`. No NMMT/NMM on ONDC found.

**Cabs and autos (fact-check of `cabs.py`).**

| Assumption in code | Verdict | Fact |
|---|---|---|
| Auto ₹28 + ₹18.66/km "official MMRTA" | **Wrong** | That is the black-and-yellow **taxi** card w.e.f. 01.10.2022. Auto: ₹23 + ₹15.33 (01.10.2022) → **₹26 + ₹17.14 (01.02.2025)** `[verified: https://transport.maharashtra.gov.in/Site/Upload/GR/Auto%20Rickshaw%20Tariff%20Card.pdf, …/YB%20Taxi%20English%201.pdf, …/Auto%20English%201.pdf]`; ₹27 + ₹18.22 from 1 Sept 2026 per MMRTA (press; official card not yet online) `[verified: https://www.freepressjournal.in/mumbai/mumbai-taxi-auto-fares-to-rise-from-september-1-minimum-fares-to-increase-from-31-to-33-and-26-to-27]`. Same tariff across MMR incl. Navi Mumbai/Thane `[verified: https://www.timeout.com/mumbai/news/mumbai-auto-and-taxi-fares-rise-from-september-1-check-the-new-rates-090126]`. Surcharges on the official cards: +25% 00:00–05:00; waiting 10% of per-km fare per minute; luggage ₹6/package >60×40 cm. |
| Uber deep link `m.uber.com/ul/?action=setPickup&client_id=optigo…` | **Partly** | Current docs document `https://m.uber.com/looking?client_id=…&pickup=<json>&drop[0]=<json>` and `uber://riderequest?…`; the legacy `/ul/` form still redirects (via get.uber.com → an attribution link) but is undocumented; `client_id` is in every example but never labelled required `[verified: https://developer.uber.com/docs/riders/ride-requests/tutorials/deep-links/introduction]`. |
| Uber fares (Auto ₹30+₹16/km etc.) | **Unverifiable** | No public rate card; `/v1.2/estimates/price` "requires approval from Uber" and using it for price comparison with competitors violates the API terms `[verified: https://developer.uber.com/docs/riders/references/api/v1.2/estimates-price-get]`. |
| Ola deep link `book.olacabs.com/?lat…` | **Partly** | Documented, but `utm_source` is mandatory and must be an affiliate token; the developer platform is invite-only since Nov 2017 `[verified: https://developers.olacabs.com/docs/deep-linking, /docs/overview]`. |
| Ola, Rapido rate cards | **Unverifiable** | No official cards; Rapido has no API or deep-link docs at all `[verified: https://www.rapido.bike/, https://providers.apievangelist.com/providers/rapido/]`. Maharashtra STA set bike-taxi fare ₹15 for 1.5 km + ₹10.27/km (Aug 2025) `[verified: https://www.theweek.in/wire-updates/national/2025/09/15/bom28-mh-bike-taxi-ld-fare.html (PTI)]`. |
| Regulatory envelope | **Useful** | MMRTA directed app aggregators in Mumbai (Sept 2025) to charge kaali-peeli per-km rates with −25% / +1.5× band `[verified: https://www.businesstoday.in/india/story/ola-uber-rapido-app-based-cabs-asked-to-follow-base-fare-of-black-yellow-taxis-in-mumbai-494713-2025-09-19 (news; no primary)]`. |

**How the cab layer should fit:** keep the `CabProvider` interface, but (1) compute **metered auto/taxi exactly** from the official tariff cards (deterministic, no live data needed) with the night surcharge; (2) show app cabs as a **band** derived from the official per-km rate × [0.75, 1.5] labelled "regulated range, app shows exact"; (3) use deep links as documented (Uber `looking?…`; Ola only if you obtain an affiliate token; Rapido: none — link to the store); (4) delete constant ETAs; (5) road distance from OSRM/Valhalla rather than haversine × 1.3. The cab leg is a first/last-mile option in the planner, not a separate screen.

**Fares to verify for rail.** PIB says suburban single-journey and season fares were unchanged in the 1 Jul 2025 and 25 Dec 2025 revisions `[verified: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2140857, …PRID=2208532]`. The only official matrix found is WR's second-class table w.e.f. 08.06.2015 (Churchgate–Dadar ₹10, –Borivali ₹15, –Virar ₹20) `[verified: https://wr.indianrailways.gov.in/cris/uploads/files/1442984528198-Suburban%20Fare%20table%20CT.pdf]` — the `graph.py` slabs (₹5 ≤10 km, ₹10 ≤20 km, ₹15 ≤25 km …) do not reproduce those values. Navi Mumbai tickets also carry a CIDCO surcharge (per-ticket amount not found) `[verified: https://www.freepressjournal.in/mumbai/cidco-railway-deadlock-over-navi-mumbai-stations-continues-passenger-amenities-suffer-revenue-fight-unsolved]`. AC/first-class fares were rationalised by Railway Board CC 11/2022 `[verified: https://www.indianrailwayrules.com/indianrailwayrules-com-rationalization-of-fare-of-ac-ordinary-services-running-over-suburban-sections-cc-11-of-2022/]`. **Action:** get the CR Harbour fare matrix (RTI or station enquiry) and store fares as `fare_rules`-style station-pair tables, not slabs.

### 3.5 Comparison of all live/static data options

| Option | Coverage for Optigo | Cost | Access route | Reliability | Risk |
|---|---|---|---|---|---|
| CR PTT PDFs (static) | Harbour, Trans-Harbour, Port, AC; **Uran missing** | Free | Download; parse | Official; changes a few times a year | Parsing errors; must track "w.e.f." dates |
| RailRadar boards (live) | All your rail stations except Sagar Sangam | Free sandbox (1,000/mo observed; 100/mo advertised now); paid tiers unreadable | API key | Crowdsourced; `delay_minutes` often null | Unofficial; ToS silent; NTES-derived data conflicts with CRIS terms; quota |
| NTES site (live) | Everything | Free | Browser only | Official | **ToS forbids systematic download** — do not scrape |
| CRIS Pravah / NDSAP registered access | Everything | Unknown | Formal letter; partnership | Official | Likely no reply; months |
| Yatri app CR GPS | Harbour/Uran locals, 15 s | — | Closed | Official partner | Not accessible |
| Community rail GTFS (mdb-2867) | Long-distance only | Free | Download | Unlicensed, stale | Useless for locals |
| NMM Line 1 | No feed | — | — | — | Use headways; no live |
| NMMT Apali app / ITMS | 74 routes live | — | App only | Official | No export; transcribe |
| croyla mumbai-gtfs | BEST/TMT/KDMT static | Free (MIT-0) | Download | Community, maintained 2026 | No NMMT |
| Mumbai One | Planner + tickets, 11 PTOs | — | App only | Official | No API; it's the incumbent |
| Google Routes API (transit) | Mumbai transit incl. BEST/locals (2011 onward); NMM `[unverified]` | India price list: 70,000 free Compute Routes Essentials/month then $1.50/1k `[verified: https://developers.google.com/maps/billing-and-pricing/pricing-india]` | API key + billing | High | Black box; cannot explain or customise; terms restrict caching |
| Ola Maps (geocoding/directions, no transit) | Roads, places | 100K free calls per API/month; new credit pricing from 1 Sep 2026 `[verified: https://maps.olakrutrim.com/pricing]` | Krutrim account | Good for India | Not transit |
| Uber/Ola ride APIs | Live fares | — | Partner/affiliate only | — | Unobtainable |
| Official auto/taxi tariff cards | All MMR | Free | PDF | Deterministic | Must track revisions (Sept 2026 card pending) |
| OSM (static nodes, streets) | Stations good; bus stops fair; auto stands poor | Free | Extract | Community | Attribution; gaps |
| Your users (crowdsourcing) | Warm nodes, crowding, delays | Dev time | In-app | Starts empty | Moderation, cold start |

---

## 4. Tech stack for the rewrite

### 4.1 Static Dijkstra vs time-dependent timetable routing

Your network has services every 3–8 minutes on the Harbour trunk (VSH board: 132 EMUs in 4 h both directions) but only ~14–15 trains in 4 hours at Kharkopar/Targhar (≈ 30 min per direction) and a 10–15 min metro `[code: fixtures manifest]`, `[snippet: housing.com]`. A static "edge time" router gets the trunk roughly right and the Uran branch and metro transfers badly wrong (it cannot see a 25-minute wait). Timetable routing fixes this, and it is what makes Ideas 4, 5, 6 and backing/switching natural.

| Approach | What it is | Fit |
|---|---|---|
| **RAPTOR** (Delling, Pajor, Werneck, ALENEX 2012) | Round-based: each round allows one more trip; scans routes, not graph edges; no priority queue; naturally produces Pareto sets (arrival time × transfers); rRAPTOR for departure ranges; McRAPTOR for extra criteria `[verified: https://www.microsoft.com/en-us/research/publication/round-based-public-transit-routing/, PDF https://www.microsoft.com/en-us/research/wp-content/uploads/2012/01/raptor_alenex.pdf]` | **Best fit**: tiny network, needs "fewest transfers" and "boards at origin" criteria |
| **CSA** (Dibbelt, Pajor, Strasser, Wagner, 2013/2018) | One time-sorted array of connections scanned once; extremely simple; profile variant for ranges `[verified: https://arxiv.org/abs/1703.05997]` | Simplest to implement (≈ 100 lines); weaker for multi-criteria |
| Static Dijkstra (current) | Edge weights | Keep only for the street/walking layer |

Recommendation: implement RAPTOR (with rRAPTOR for a departure window) yourself; keep CSA as a reference implementation for tests. `[judgement]`

### 4.2 Use an existing engine or write your own?

| Engine | Facts (2026-10-10) | Verdict for a solo student |
|---|---|---|
| **OpenTripPlanner 2.10** (Java, LGPL-3, GraphQL, GTFS-RT updaters, frequency trips supported since 2022 with a performance caveat) | RAM "from less than one GB to more than 100 GB"; Docker image; v2.10.0 2026-09-09 `[verified: https://docs.opentripplanner.org/en/latest/System-Requirements/, https://github.com/opentripplanner/OpenTripPlanner/pull/3916]` | Most documented, heaviest; always-on JVM; you learn configuration, not routing |
| **MOTIS 2.11** (C++, MIT, REST/OpenAPI, RAPTOR core "nigiri", GTFS + GTFS-RT + OSM street routing + geocoding + tiles, 3-command quick start, Docker) | v2.11.3 2026-09-10 `[verified: https://github.com/motis-project/motis, https://raw.githubusercontent.com/motis-project/motis/master/openapi.yaml]` | **Best off-the-shelf**: run it locally in Docker as the *oracle* to validate your router and GTFS; could also be the production backend on a ₹300–400/month VPS or Oracle's free ARM tier |
| Transitous (free public MOTIS API) | India feeds = Flixbus + the unofficial long-distance rail GTFS only; no Mumbai `[verified: https://raw.githubusercontent.com/public-transport/transitous/main/feeds/in.json]` | Not useful until you contribute a feed (which you could — see Idea 6.9) |
| R5/r5py, GraphHopper PT, Valhalla multimodal, Navitia | R5 is an analysis tool; GraphHopper PT needs 8 GB for Berlin and no GTFS-RT; Valhalla transit is partial (no arrive-by); Navitia is closing its repos `[verified: see sources]` | Not for this |
| Small readable implementations | `planarnetwork/raptor` (TS, GPLv3, 120★, pushed 2026-09), `planarnetwork/connection-scan-algorithm` (TS, GPLv3), `aubryio/minotor` (TS, MIT, 81★, **client-side RAPTOR in browser/Node/RN**, GTFS→protobuf), `lmeulen/pyraptor` (Python, MIT, stale 2022) `[verified: GitHub pages]` | Read `minotor` and `planarnetwork/raptor`; write your own (MIT) — avoid copying GPL code into a differently-licensed project |

**Decision: write your own RAPTOR (~500 lines + tests), validate against MOTIS on the same GTFS.** The network is a few hundred stops; a round touches tiny arrays; correctness and explainability matter more than speed; and "I implemented RAPTOR and it agrees with MOTIS on 200 random queries" is a stronger academic result than "I configured OTP". `[judgement]`

### 4.3 Storage

- pgRouting has **no** time-dependent or transit functions `[verified: https://docs.pgrouting.org/latest/en/index.html]`; every production engine keeps the timetable in memory as arrays. So the database is for *editing and analysis*, not routing.
- **Recommendation:** GTFS text files in `data/gtfs/` in git as the source of truth (24 stations and a few hundred trips are reviewable in a diff), plus the two extension CSVs from §2.2. A build step validates (`gtfs-validator`, Docker image available `[verified: https://github.com/MobilityData/gtfs-validator]`) and compiles to a compact JSON/protobuf bundle. Use DuckDB (spatial extension) or `gtfs_kit`/`partridge` for ad-hoc analysis `[verified: https://duckdb.org/docs/current/core_extensions/spatial/overview.html, https://github.com/mrcagney/gtfs_kit]`. Drop Supabase at runtime; if you ever want SQL, `gtfs-via-postgres` loads a feed into PostGIS with `connections` views `[verified: https://github.com/public-transport/gtfs-via-postgres]`.

### 4.4 Real-time ingestion

- Internal format: **GTFS-Realtime `TripUpdate`** (protobuf; Python/JS bindings from MobilityData) even if the only producer is your RailRadar adapter `[verified: https://gtfs.org/documentation/realtime/reference/, https://github.com/MobilityData/gtfs-realtime-bindings]`. When any official feed appears, only the adapter changes.
- Polling budget reality: 13 stations polled every 5 minutes would be ~112,000 calls/month against a 1,000/month key, so live stays **on-demand per boarding station with a 60 s shared cache**, as now, but behind a server-side proxy (Cloudflare Worker: 100,000 requests/day free `[verified: https://developers.cloudflare.com/workers/platform/limits/]`) that holds the key, enforces 10/min, and exposes `live_status.quota_remaining`.
- Apply `TripUpdate`s on the client by shifting `stop_times` for matched trips (train number ↔ `trip_id`), and label unmatched trains.

### 4.5 Map library and tiles

| Choice | Facts | Verdict |
|---|---|---|
| **MapLibre GL JS** | BSD-3, v6.13.0 (2026-10-06) `[verified: https://github.com/maplibre/maplibre-gl-js]` | **Use it** |
| Mapbox GL JS | Proprietary ToS since v2; 50,000 web map loads/month free then $5/1k `[verified: https://raw.githubusercontent.com/mapbox/mapbox-gl-js/main/LICENSE.txt, https://www.mapbox.com/pricing]` | Avoid lock-in |
| Leaflet | Light; raster-oriented | Fine, but MapLibre's vector styling suits transit layers better |
| **OpenFreeMap** tiles | Free, no key, no limits, commercial OK, attribution required, no SLA `[verified: https://openfreemap.org/]` | **Default tile source** |
| Protomaps PMTiles | Self-host a Navi Mumbai extract (tens of MB) on Cloudflare R2/Pages `[verified: https://docs.protomaps.com/pmtiles/cli, https://docs.protomaps.com/deploy/cost]` | Backup / offline-capable |
| MapTiler free | 5k map loads/month, logo, non-commercial `[verified: https://www.maptiler.com/cloud/pricing/]` | Too small |
| tile.openstreetmap.org | Best-effort, no SLA, app use discouraged `[verified: https://operations.osmfoundation.org/policies/tiles/]` | Don't |

Schematic view: keep Himesh's idea but **generate** it — either a hand-maintained `schematic.geojson` (x/y per stop) rendered by the same MapLibre instance in a second "diagram" projection, or `ad-freiburg/loom` to auto-generate octilinear maps from GTFS `[verified: https://github.com/ad-freiburg/loom]`.

### 4.6 Backend language

| Language | For this project |
|---|---|
| **TypeScript** | One language with the Next.js frontend; the router can run **in the browser** (offline PWA for free, zero server cost) and in a Worker; `minotor` proves the pattern. Cost: you must learn TS properly. |
| Python (FastAPI) | Continuity with the 80 tests and your skills; best GTFS/ETL tooling; but needs an always-on server (free tiers spin down: Render free sleeps after 15 min idle and wakes in ~1 min `[verified: https://render.com/docs/free]`). |
| Go / Rust | No payoff at this scale; more build/deploy friction. |

No credible Python-vs-TS benchmark for RAPTOR was found; at a few hundred stops all of them answer in milliseconds `[judgement]`.

### 4.7 Hosting and cost (prices read 2026-10-10)

| Service | Free tier | Note |
|---|---|---|
| Cloudflare Pages + Workers | Pages: 500 builds/month; Workers: 100k req/day, 10 ms CPU `[verified: https://developers.cloudflare.com/pages/platform/limits/, https://developers.cloudflare.com/workers/platform/limits/]` | Static site + live proxy = ₹0 |
| Vercel Hobby | Non-commercial only; generous limits `[verified: https://vercel.com/docs/limits]` | Fine for the Next.js app |
| Render Free | Spins down after 15 min idle; 750 h/month; free Postgres expires after 30 days `[verified: https://render.com/docs/free]` | OK for a demo backend, not for "always works" |
| Fly.io | No free tier; smallest always-on ≈ $2.19/month `[verified: https://docs.fly.io/about/pricing]` | Cheapest always-on container |
| Railway | $5 trial; Hobby $5/month incl. $5 usage `[verified: https://railway.com/pricing]` | |
| Oracle Cloud Always Free | A1 Flex ARM: 2 OCPU / 12 GB (docs), 200 GB block, 10 TB egress; idle instances may be reclaimed `[verified: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm]` | Enough to run MOTIS for free, with reclaim risk |
| Supabase Free | 500 MB, **pauses after 1 week inactivity** `[verified: https://supabase.com/pricing]` | Why runtime DB is dropped |
| Neon Free | 1 GB/project, scale-to-zero after 5 min `[verified: https://neon.com/pricing]` | If you must have Postgres |
| GitHub Student Pack | Azure $100, Heroku $13/month ×24, Namecheap domain + SSL, Datadog, Copilot `[verified: https://education.github.com/pack]` | Domain for free |

### 4.8 The one recommendation

```
data/gtfs/*.txt  (+ optigo_nodes.csv, share_auto_routes.csv, fares/)   ← source of truth, in git
   │  python scripts: parse CR PDFs, OSM extract (osmium), validate (gtfs-validator), build bundle
   ▼
packages/router (TypeScript, MIT): GTFS bundle loader, RAPTOR/rRAPTOR, McRAPTOR criteria
   ├── runs in the browser (Next.js app, PWA, offline)            ← default path, ₹0
   └── runs in a Cloudflare Worker (/plan API for others, live proxy holding the RailRadar key)
apps/web (Next.js, MapLibre + OpenFreeMap, Himesh's components ported)
tools/motis (Docker, local only): oracle for router + GTFS validation
```

Why this and not "FastAPI + MOTIS on a VPS": it costs nothing, survives inactivity, works offline, teaches the algorithm, and keeps Python where it is strongest (data building). If you later get an official feed or need isochrones, add MOTIS behind the Worker without touching the client. `[judgement]`

---

## 5. Backing and switching — the carried-over design, what was built, what to change

### 5.1 The design (Ideas 1 and 2 from `future-ideas.md`, in full)

**Problem.** At boarding station B wanting alighting station A, through trains are packed. Two moves trade a few minutes for a boarding at an origin station (near-certain seat, no accumulated delay):

- **Idea 1 — Backing** (`kind: "back"`): ride *against* your direction to an origin terminus T behind B, then board a train originating at T that passes B towards A. Example: Khandeshwar → Nerul via Panvel. All Panvel-origin locals (CSMT/Vadala/Goregaon/Thane-bound) share Panvel → Khandeshwar → Mansarovar → Kharghar → Belapur → Seawoods → Nerul → Juinagar and diverge only after Juinagar, so the corridor model (`harbour` and `trans-harbour` both contain JNJ…PNVL) handles the branch check.
- **Idea 2 — Forward switch** (`kind: "switch"`): ride *forward* to an intermediate origin or junction S between B and A, alight, board a train starting at S. Example: Kharghar → Vashi switching at Belapur CBD (Belapur–CSMT / Belapur–Vadala locals); cost is the wait at Belapur only.

**Origins observed on boards:** Panvel (all Mumbai/Thane-bound), Belapur CBD (CSMT, Vadala Road, Uran), Nerul (Thane, Uran), Vashi (Thane). **Junctions** (station in ≥2 corridors): Juinagar, Sanpada, Seawoods-Darave, Belapur, Nerul.

**Shared algorithm.**
1. Pivot set: from `first_train_leg()` get B, A, corridor; backing pivots = origins on the far side of B from A (cap the detour, e.g. ≤5 stops/≤15 min); switching pivots = origins and junctions strictly between B and A. Cap total pivots (3–4) to bound API calls.
2. Boards: B's (already fetched) + one per pivot, cached 60 s.
3. Leg 1 at B: trains with `train_serves(src, dst, B, P)` — deliberately including trains that do not reach A (a Thane-bound train is fine to Juinagar). Next 1–2 by expected departure.
4. Leg 2 at P: *seat variant* `train.source == P` and `train_serves(P, dst, P, A)`; *time variant* any train serving P→A after arrival.
5. Pairing: arrival at P ≈ leg-1 expected departure at B + edge times B→P + transfer buffer (3–5 min; platform change usual at Belapur). First leg-2 train after that.
6. ETAs: direct = next B→A train's expected departure + edge times B→A; alternative = leg-2 departure + edge times P→A; `extra_minutes` = alternative − direct (may be negative in the time variant).
7. Present, don't decide: attach `live_alternatives[]` entries `{kind, seat, via, leg1{train_number, route_name, departure_time, platform}, leg2{…}, eta_direct, eta_alternative, extra_minutes, note}`; show the best 1–2; hide above a threshold (≈15–20 min) unless the user opted into "I want a seat".

**Open decisions recorded:** travel-time source (edge times vs per-train schedules); where it lives (annotation, not a 4th Dijkstra); same-rake turnaround at Panvel ("stay on board"); seat wording ("originates here — likely seat", never a promise); thresholds, buffer, how many to show; seat-only vs time variant in v1; toggle per search vs saved preference. **Edge cases:** B is itself an origin; A beyond the branch point (origin train must match A's branch); Uran-line boarding (only Belapur/Nerul origins); delays (use expected times on both boards); midnight wrap. **Occupancy:** no data exists; "trains are full" is the user's input (toggle), with a peak-window hint (08:00–11:00 towards Mumbai, 17:30–21:00 towards Panvel). **Cost:** +1 RailRadar call per pivot per search.

### 5.2 What `alternatives.py` actually implements

Faithful to the design: pivot discovery behind/between on the corridor; seat variant with `source == P`; pairing with buffers (4 min at Belapur, 3 elsewhere); `extra_minutes` vs the next direct train; cap 2 pivots, return ≤2, threshold 15; ticket-validity note for backing; boards at `hours=4`; offline tests on real boards. `[code: alternatives.py]`

Departures from the design: **no junction pivots, no time variant** (`prefer_seat` is ignored inside `compute_alternatives`); fallback travel time is `stops × 3 min`, not graph edge times; `extra_minutes` falls back to constants (5/10); same-rake detection by train-number equality cannot fire; `eta_direct`/`eta_alternative` are not returned (only `extra_minutes`); `calls_used` over-counts. `[code: alternatives.py:24, 134-140, 228, 254-259, 323, 338, 350-354, 441-444]`

### 5.3 What I would change in the rewrite

1. **Make it a routing criterion, not a bolt-on.** With a timetable, backing and switching are ordinary journeys: Khandeshwar→Panvel→Nerul is just a two-trip itinerary that RAPTOR will find if the window is wide enough. Run **McRAPTOR** with criteria (arrival time, transfers, *non-origin boardings*). A journey whose every boarding is at a trip's first stop dominates on the third criterion; the Pareto set then contains "direct, 2 min faster" and "via Panvel, +11 min, boards at origin" side by side. No boards needed for the *static* version; RailRadar only shifts times.
2. **Edge times → scheduled times.** Pairing uses `stop_times`, so arrival at P and the direct train's passing time are exact, including the Uran branch and AC locals.
3. **Same-rake turnaround**: detect at terminus pivots by matching a leg-1 arrival to a leg-2 departure from the same platform within a few minutes, or by a `block_id` in GTFS if you can infer rake links; say "stay on board".
4. **Ticket validity**: backing is riding beyond your ticketed section; keep the note, and only offer backing to holders of a season pass covering T (a user setting), or show the extra fare.
5. **Junction switching (time variant)** is where switching beats direct (Thane-bound to Juinagar, then a CSMT train) — it comes free from the multi-criteria router.
6. **Seat heuristic calibration**: add a one-tap "did you get a seat?" after the journey; store (origin station, time-of-day, direction) → seat probability; show it as "likely seat (users report 80% at Belapur 18:00–19:00)". Starts empty; honest.
7. **Quota**: pivot boards are still needed for *live* times; cap at 2 and reuse the 60 s cache; show `quota_remaining`.

---

## 6. Additional ideas, ranked by value × feasibility

| # | Idea | Why it matters | Data needed / exists? | Cheapest test |
|---|---|---|---|---|
| 6.1 | **Official timetable GTFS for Harbour + Trans-Harbour + Metro (+ Uran from boards)** | Foundation for everything in §4–5; makes the app correct without any live source | CR PTT PDFs ✔ `[verified]`; metro headway ✔ (secondary); Uran ✘ (RTI / observed boards) | Hand-build `stop_times` for one hour of Harbour UP; load in MOTIS Docker; compare with the PNVL fixture departures (97 trains, 2026-10-05 17:42) |
| 6.2 | **Transfer feasibility and connection warnings** (old Idea 5) | Belapur rail↔metro and Kharghar↔Belpada are the two multimodal transfers; users need "tight / comfortable / missed" | GTFS + `transfers.txt` ✔ once 6.1 exists; walking times from OSRM on OSM ✔ | Compute arrival at Belapur from a fixture train + metro headway; assert the warning on 3 cases |
| 6.3 | **Door-to-door with a real street layer** (addresses, NMIA, temples) | PROTOTYPE_BRIEF Phase D; current straight-line walk is fiction | OSM Navi Mumbai extract ✔; geocoder: self-hosted Nominatim/Photon or Ola Maps (100k free) ✔ `[verified]` | Run OSRM in Docker on the Western-Zone extract; compare 10 station-to-address walks with Google Maps walking times |
| 6.4 | **NMMT and airport feeders as frequency-based GTFS + warm nodes** | NMIA opened 25 Dec 2025 with NMMT A1–A7 feeders to your stations `[verified: Adani release]`; nobody has this as open data | Routes from Apali NMMT app / Adani release ✔ (manual); stops from OSM ✔ (~1,100) | Transcribe A1–A7 + 5 station feeders; publish as `optigo-nmmt-gtfs`; validate; submit to the Mobility Database |
| 6.5 | **Honest live overlay abstraction** (source, freshness, confidence per leg) | Multiple weak sources (RailRadar crowd, user reports, none for metro) need one truthful presentation | Existing `live_status.reason` pattern ✔ | Render three states (fresh / stale >2 min / none) on the current UI |
| 6.6 | **AC-local awareness and fares** (old Idea 4) | Harbour AC services since 26 Jan 2026 carried ~40k/day in 16 days `[verified: FPJ citing CR]`; fare differs | CR Harbour AC PTT ✔ `[verified]`; AC fares via CC 11/2022 (scanned) ✘ partial | Add AC trips as a separate `route_id`; check whether RailRadar types them `EMU` (`[unverified]`) using the PNVL fixture |
| 6.7 | **Crowding heuristic + user reports** (old Idea 6) | Crush load >6,000 per 12-car vs 2,400 rated at peak `[verified: MRVC Corporate Plan]`; m-Indicator shows "less-crowded trains" `[verified: App Store]` | Time-of-day table ✔ (judgement); reports ✘ (collect) | Ship the static table with a "report crowding" tap; look at 2 weeks of data |
| 6.8 | **Offline PWA** (old Idea 8) | Underground/metro gaps; free if the router is client-side | GTFS bundle ✔ | `next build` + service worker; plan a route in airplane mode |
| 6.9 | **Publish the feed** (Mobility Database + Transitous `in.json`) | Puts Navi Mumbai on open-transit maps; external validation; good for the report | 6.1/6.4 | Open a PR to `public-transport/transitous` feeds `[verified: repo]` |
| 6.10 | **Share-auto survey and crowdsourcing → OSM** | OSM has 30 auto stands and one share-auto node; real network is dense; nobody maps per-seat fares | ✘ (collect); tag `amenity=taxi` + `taxi_vehicle=auto_rickshaw` `[verified: taginfo]` | Survey Belapur, Kharghar, Nerul station stands on one Saturday; add to OSM and `share_auto_routes.csv` |
| 6.11 | **Evaluation harness** | Academic credibility: compare 100 random queries against Google Routes transit (70k free/month in India `[verified]`) and MOTIS; report agreement | Router ✔ | A script that logs travel-time deltas |
| 6.12 | **Nearest-station from GPS** (old Idea 3) | Mobile UX | Client-side KD-tree over `stops.txt` ✔ | 20 lines |
| 6.13 | **Accessibility layer** (entrances, lifts, `wheelchair=*`) | Stations have multiple entrances; OSM has `railway=subway_entrance`/station entrances | Partial in OSM `[verified: wiki]` | Add entrances as `location_type=2` for Belapur and Vashi |

Ranking rationale: 6.1–6.3 unblock the rewrite; 6.4 and 6.10 are the only genuinely new data anyone would produce; 6.5–6.8 are cheap once the router exists; 6.9/6.11 strengthen the submission; 6.12–6.13 are polish. `[judgement]`

---

## 7. Post-semester milestones

| # | Milestone | Done when | Rough effort |
|---|---|---|---|
| M0 | **Freeze v1.** Tag `main` as `v1-miniproject`; commit the uncommitted frontend fixes so a clean clone builds; push `frontend-reference`. | `git clone && npm ci && npm run build` works | 1 evening |
| M1 | **First small win: Harbour GTFS + MOTIS.** `data/gtfs/` from the CR Harbour DN/UP PDF (one weekday calendar), `feed_info.txt` with source and w.e.f. date, `gtfs-validator` clean; MOTIS in Docker plans Panvel 08:10 → Vashi with real train times. | A screenshot of MOTIS's plan matching the PDF | 1–2 weekends |
| M2 | **Own router.** `packages/router` RAPTOR in TS with a test that compares 200 random (origin, destination, time) queries against MOTIS on the same feed. | ≥95% identical arrival times; differences explained | 3–4 weeks part-time |
| M3 | **Map + hot nodes.** MapLibre + OpenFreeMap; stations/platforms from OSM extract; schematic view generated from `schematic.geojson`; Himesh's components ported. | Plan page works on the new stack, offline | 2–3 weeks |
| M4 | **Live overlay.** Cloudflare Worker proxy for RailRadar (key, 10/min, 60 s cache, quota header); `TripUpdate` adapter; honest states. | Panvel→Vashi shows live platforms/delays from the proxy | 1–2 weeks |
| M5 | **Metro + transfers + fares.** Metro `frequencies.txt`; `transfers.txt` for Belapur/Kharghar; fares as station-pair tables once the CR matrix arrives (RTI filed at M1). | Belapur→Pendhar shows a timed transfer and a verified fare | 2 weeks |
| M6 | **Backing/switching as McRAPTOR criterion.** | Khandeshwar→Nerul Pareto set includes "via Panvel, boards at origin" with exact scheduled times | 2–3 weeks |
| M7 | **First/last mile.** OSRM walking; auto/taxi from official tariff cards; app-cab band; NMMT A1–A7 + station feeders as frequency GTFS; warm nodes layer. | Panvel → NMIA T1 and Panvel → an Airoli address both plan | 3–4 weeks |
| M8 | **Publish + evaluate + outreach.** Mobility Database/Transitous PR; evaluation harness vs Google/MOTIS; letters to CR/CRIS (M1 already sent the Uran PTT request); SIH/Innovation Portal check. | Report chapter with numbers | ongoing |

Order the letters early (M1) because replies, if any, take months.

---

## 8. Risks, open questions, assumptions

### 8.1 Risks

| Risk | Impact | Mitigation |
|---|---|---|
| RailRadar changes terms, shrinks the sandbox (docs already say 100/month), or disappears ("EST. 2026") | Live layer dies | Timetable-first design; adapter pattern; never depend on it for the base plan |
| Using NTES-derived data (via RailRadar) could be seen as violating NTES's no-systematic-download terms | Legal/ethical exposure in a college submission | Label the source; keep live usage minimal; prefer the official PDFs; seek registered access |
| CR timetable changes (w.e.f. dates) and your GTFS goes stale | Wrong trains | `feed_info` end date; a monthly check of the CR page; show "timetable valid to …" |
| Uran line timetable never arrives | Branch is observed-only | Label `confidence=observed`; keep requesting |
| Solo-student scope creep (NMMT transcription, surveys) | Nothing ships | Milestones above; M1–M3 before any bus work |
| Free-tier changes (Cloudflare, OpenFreeMap no SLA) | Outage | Static bundle + PMTiles fallback; everything runs locally |
| GPL contamination if code is copied from `planarnetwork/*` | Licence conflict | Read, don't copy; MIT `minotor` is safer |
| Fares wrong on screen | Users misled | Show "estimated" until the CR matrix is in; metro chart is secondary-source only |
| Mumbai One already does integrated planning | "Why Optigo?" | Position on transparency, seat logic, informal modes, open data, offline |

### 8.2 Open questions

1. Does NTES Live Station list EMU locals at Navi Mumbai stations? (JS + CAPTCHA; unverified.)
2. How does RailRadar type AC locals (`train.type`)? None matched "AC" in the PNVL fixture names; needs a board during AC service hours.
3. Which Belapur–RBI–Belpada distances does the live Supabase DB hold (0.4 / 0.5 / 1.0)? Not queried.
4. What is the per-ticket CIDCO surcharge on Harbour tickets, and the current CR second-class fare matrix?
5. Is station 10 "Pethali–Taloja" or "Panchanand"?
6. Will Himesh continue on the frontend after the semester, and is he fine with a TypeScript-everywhere monorepo?
7. Does the 1 Sept 2026 auto/taxi tariff card exist as an official PDF yet?
8. Is Uber app registration still open for a `client_id`, and is one required for the `looking?` link?

### 8.3 Assumptions I made

- "After this semester" ≈ from December 2026; milestones are relative, not dated.
- Budget for hosting ≈ ₹0/month; a VPS is acceptable only if free credits cover it.
- The teammate's frontend is to be *ported*, not discarded; the visual design is yours to keep.
- The live Supabase data matches `seed.sql` except possibly the RBI hops (unknown).
- RailRadar's observed 1,000/month applies to your existing key; new sandbox keys may get 100/month as the docs now state.
- OSM counts use a bounding box, not the municipal boundary; the wider box includes parts of Thane, so bus-route counts there overstate Navi Mumbai.
- The user's NIC contacts are informal; nothing here assumes they can authorise anything.
- "Second-year student working alone" means ~8–10 hours/week; effort estimates reflect that.
- PROTOTYPE_BRIEF said to work on a fork; in practice the backend/frontend branches were merged into `main`. I treated `main` as the current project.
- Running the offline test suite was within scope ("no network, no keys"); its side effect of clearing the dev disk cache is reported in §0.1.

---

## 9. Sources (all accessed 2026-10-10)

**Repository (read directly):** `backend/app/{main,graph,railradar,alternatives,cabs}.py`, `backend/tests/*.py`, `backend/tests/fixtures/boards/live-batch-1/*.json`, `backend/scripts/capture_boards.py`, `sql-schema/*`, `frontend/**`, `ARCHITECTURE.md`, `README.md`, `backend/README.md`, `sql-schema/README.md`, `PROTOTYPE_BRIEF.md`, `future-ideas.md`, `log.md`, `handoff.md`, `plan.md`, `REPO.md`, git history (`git log --all --graph`, `git branch --merged`, `git show 2b34622`, `git diff`).

**OpenStreetMap queries (2026-10-10):** `https://overpass-api.de/api/interpreter` — `nwr["railway"="station"]`, `nwr["amenity"="taxi"]` (tags), `relation["route"="bus"]` (tags), `node["highway"="bus_stop"]` (400-tag sample) in bbox 18.93,72.95,19.22,73.15; second-pass counts via the `maps.mail.ru/osm/tools/overpass` mirror (bus_stop 1,104; platform 1,035; station 26; taxi 30; route=bus 184; taxi_vehicle=auto_rickshaw 1).

**Indian Railways / CRIS / NIC / policy**
- https://cris.org.in/ · https://cris.org.in/PDF/Annual_Report/report and accounts for the year 2024.pdf · https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/aug/doc202686945401.pdf · https://en.wikipedia.org/wiki/Centre_for_Railway_Information_Systems
- https://enquiry.indianrail.gov.in/mntes/ · https://enquiry.indianrail.gov.in/mntes/disclaimerDisplay.html
- https://wso2.com/br/customers/cris-revolutionizes-indian-railways-wso2/ (Project Pravah, vendor source)
- https://apisetu.gov.in/ · https://directory.apisetu.gov.in/ · https://www.data.gov.in/catalog/indian-railways-train-time-table · https://www.data.gov.in/government-open-data-license-india
- https://transdev.assam.gov.in/sites/default/files/menu/document/pndd_medhassu_in/ndsap-30jan2012.pdf (NDSAP 2012) · https://en.wikipedia.org/wiki/National_Informatics_Centre · https://www.nic.gov.in/
- https://cr.indianrailways.gov.in/view_section.jsp?lang=0&id=0,5,2360 (CR Mumbai suburban PTT PDFs) · https://cr.indianrailways.gov.in/view_section.jsp?lang=0&id=0,7 (CR contact) · https://wr.indianrailways.gov.in/view_section.jsp?lang=0&id=0,6,458 · https://mrvc.indianrailways.gov.in/ · https://mrvc.indianrailways.gov.in/uploads/Corporate%20Plan%20English%20-July%2025.pdf
- https://indianrailways.gov.in/railwayboard/view_section.jsp?lang=0&id=0,7 (Railway Board contact)
- https://rskr.irimee.in/forum/wp-content/uploads/2023/08/2022-Indian-Railways-Innovation-policy.pdf · https://www.sih.gov.in/ · https://www.somaiya.edu.in/en/view-announcement/1026
- https://www.freepressjournal.in/mumbai/mumbai-central-railways-live-location-feature-on-yatri-app-receives-stellar-response · https://apps.apple.com/us/app/-/id1563046909 · https://frontiertech.niti.gov.in/story/how-yatri-is-transforming-mumbais-public-transport-through-data-and-ai/
- https://www.india.com/news/india/indian-railways-irctc-rail-apps-digital-india-ntes-app-cris-rail-yatri-ixigo-train-where-is-my-train-modi-ashwini-vaishnaw-7863321/ · https://www.medianama.com/2013/09/223-terrible-move-indian-railways-pulls-the-plug-on-rail-radar-train-enquiry/ · https://www.outlookbusiness.com/news/adani-s-trainman-not-a-competition-clarifies-irctc-over-e-ticketing-business-row-news-295995 · https://www.outlookbusiness.com/news/central-railway-assumes-charge-of-14-navi-mumbai-suburban-stations-from-cidco
- https://railradar.in/ · https://railradar.in/docs · https://railradar.in/terms · https://railradar.in/privacy · https://railradar.in/about · https://railradar.in/pricing
- https://erail.in/info/data/2300 · https://indianrailapi.com/ · https://en.wikipedia.org/wiki/Where_Is_My_Train
- https://mobilitydatabase.org/feeds/gtfs/mdb-2867 · https://github.com/Neo2308/indianrailways-gtfs · https://github.com/datameet/railways
- Fares: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2140857 · https://www.pib.gov.in/PressReleasePage.aspx?PRID=2208532 · https://wr.indianrailways.gov.in/cris/uploads/files/1442984528198-Suburban%20Fare%20table%20CT.pdf · https://wr.indianrailways.gov.in/cris/uploads/files/1442984551054-Suburban%20Fare%20table%20ST.pdf · https://www.indianrailwayrules.com/indianrailwayrules-com-rationalization-of-fare-of-ac-ordinary-services-running-over-suburban-sections-cc-11-of-2022/ · https://www.freepressjournal.in/mumbai/cidco-railway-deadlock-over-navi-mumbai-stations-continues-passenger-amenities-suffer-revenue-fight-unsolved · https://www.freepressjournal.in/mumbai/mumbai-ac-locals-draw-massive-response-on-harbour-line-64-lakh-passengers-travel-in-16-days-says-central-railway

**Navi Mumbai Metro, NMIA, NMMT, BEST, Mumbai One, ONDC**
- https://en.wikipedia.org/wiki/Line_1_(Navi_Mumbai_Metro) · https://cidco.maharashtra.gov.in/Page?Token=92BA1874285 · https://cidco.maharashtra.gov.in/Upload/20260513111413224.pdf (CIDCO budget 2026-27) · https://www.mahametro.org/ · https://www.freepressjournal.in/mumbai/navi-mumbai-krcl-takes-charge-of-nm-metro-operations-for-next-3-years · https://themetrorailguy.com/navi-mumbai-metro-information-map-updates/ · https://www.dnaindia.com/india/report-mumbai-metro-navi-mumbai-belapur-utsav-chowk-line-s-list-of-11-stations-ticket-prices-revealed-3034590 · https://www.freepressjournal.in/mumbai/navi-mumbai-metro-line-1-cidco-cuts-belapur-pendhar-travel-time-by-90-seconds-from-july-13 · [snippet] https://housing.com/news/navi-mumbai-metro · [snippet] https://thecsrjournal.in/cidco-navi-mumbai-metro-crosses-one-crore-ridership-milestone-in-just-two-years/
- https://en.wikipedia.org/wiki/Navi_Mumbai_International_Airport · https://www.adani.com/newsroom/media-releases/chairman-gautam-adani-welcomes-first-passengers-as-navi-mumbai-international-airport-takes-flight · https://www.adani.com/newsroom/media-releases/navi-mumbai-international-airport-offers-affordable-multimodal-travel-with-buses-taxis-autos · https://navimumbai.adaniairports.com/
- https://en.wikipedia.org/wiki/Navi_Mumbai_Municipal_Transport · https://www.nmmc.gov.in/nmmt · [snippet] https://online.nmmc.gov.in/navimumbai/nmmt · https://apps.apple.com/in/app/nmmt-bustracker/id1235574124 · https://www.freepressjournal.in/mumbai/navi-mumbai-nmmt-ac-bus-fares-down-by-46
- https://chalo.com/mumbai · https://www.theweek.in/wire-updates/national/2025/05/08/bes25-mh-ld-best-fare.html
- https://mmrda.maharashtra.gov.in/sites/default/files/2025-10/mumbai_one_app_press_release.pdf · https://www.freepressjournal.in/mumbai/mumbai-one-app-launches-today-indias-first-unified-mobility-platform-goes-live-at-5-am-heres-what-it-offers
- https://www.ondc.org/pages/public-transport.html · https://egov.eletsonline.com/?p=103717 · https://github.com/nammayatri/nammayatri · https://apps.apple.com/in/app/namma-yatri-ride-booking-app/id1637429831
- GTFS catalog: https://mobilitydatabase.org/feeds/gtfs/mdb-3138 · https://github.com/croyla/mumbai-gtfs · https://otd.delhi.gov.in/documentation · https://github.com/Vonter/bmtc-gtfs · https://github.com/ungalsoththu/ChennaiGTFS
- Apps: https://apps.apple.com/in/app/m-indicator-mumbai-local/id593278253 · https://citymapper.com/cities · [snippet] https://moovitapp.com/index/en/public_transit-lines-Mumbai-3732-1016766

**Cabs, autos, map APIs**
- https://developer.uber.com/docs/riders/ride-requests/tutorials/deep-links/introduction · https://developer.uber.com/docs/riders/introduction · https://developer.uber.com/docs/riders/references/api/v1.2/estimates-price-get · https://developer.uber.com/docs/riders/references/api/v1.2/estimates-time-get · https://developer.uber.com/docs/riders/references/api/v1.2/products-get · https://developer.uber.com/docs/riders/guides/scopes · https://www.uber.com/in/en/price-estimate/
- https://developers.olacabs.com/ · https://developers.olacabs.com/docs/overview · https://developers.olacabs.com/docs/ride-estimate · https://developers.olacabs.com/docs/access-token · https://developers.olacabs.com/docs/deep-linking · https://maps.olakrutrim.com/pricing · https://maps.olakrutrim.com/docs
- https://www.rapido.bike/ · https://providers.apievangelist.com/providers/rapido/
- https://transport.maharashtra.gov.in/Site/Upload/GR/Auto%20Rickshaw%20Tariff%20Card.pdf · https://transport.maharashtra.gov.in/Site/Upload/GR/Black%20Yellow%20Taxi%20Tariff%20Card.pdf · https://transport.maharashtra.gov.in/Site/Upload/GR/COOL%20CAB%20Taxi%20Tariff%20Card1.pdf · https://transport.maharashtra.gov.in/Site/Upload/GR/Auto%20English%201.pdf · https://transport.maharashtra.gov.in/Site/Upload/GR/YB%20Taxi%20English%201.pdf · https://transport.maharashtra.gov.in/Site/Upload/Pdf/Maharashtra_Bike_Taxi%20Rules2025.pdf
- https://www.freepressjournal.in/mumbai/mumbai-taxi-auto-fares-to-rise-from-september-1-minimum-fares-to-increase-from-31-to-33-and-26-to-27 · https://www.timeout.com/mumbai/news/mumbai-auto-and-taxi-fares-rise-from-september-1-check-the-new-rates-090126 · https://www.freepressjournal.in/mumbai/thane-rto-issues-mandatory-meter-verification-advisory-ahead-of-revised-auto-taxi-fares-from-september-1 · https://www.businesstoday.in/india/story/ola-uber-rapido-app-based-cabs-asked-to-follow-base-fare-of-black-yellow-taxis-in-mumbai-494713-2025-09-19 · https://www.theweek.in/wire-updates/national/2025/09/15/bom28-mh-bike-taxi-ld-fare.html
- https://developers.google.com/maps/billing-and-pricing/faq · https://developers.google.com/maps/billing-and-pricing/pricing · https://developers.google.com/maps/billing-and-pricing/pricing-india · https://developers.google.com/maps/documentation/routes/transit-route · https://developers.google.com/maps/documentation/routes/usage-and-billing · https://support.google.com/transitpartners/answer/1111471 · https://www.medianama.com/2011/04/223-google-launches-public-transport-info-for-mumbai-on-maps/
- https://about.mappls.com/api/ · https://openrouteservice.org/restrictions/ · https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server · https://github.com/valhalla/valhalla

**Routing engines, algorithms, GTFS tooling**
- https://docs.opentripplanner.org/en/latest/ · https://docs.opentripplanner.org/en/latest/System-Requirements/ · https://docs.opentripplanner.org/en/latest/GTFS-RT-Config/ · https://docs.opentripplanner.org/en/latest/Container-Image/ · https://github.com/opentripplanner/OpenTripPlanner · https://github.com/opentripplanner/OpenTripPlanner/pull/3916
- https://github.com/motis-project/motis · https://raw.githubusercontent.com/motis-project/motis/master/openapi.yaml · https://github.com/motis-project/nigiri · https://github.com/motis-project/osr · https://transitous.org/ · https://transitous.org/api/ · https://github.com/public-transport/transitous · https://raw.githubusercontent.com/public-transport/transitous/main/feeds/in.json
- https://github.com/conveyal/r5 · https://r5py.readthedocs.io/stable/ · https://valhalla.github.io/valhalla/api/route/api-reference/ · https://raw.githubusercontent.com/graphhopper/graphhopper/master/reader-gtfs/README.md · https://github.com/hove-io/navitia
- https://github.com/planarnetwork/raptor · https://github.com/planarnetwork/connection-scan-algorithm · https://github.com/aubryio/minotor · https://github.com/lmeulen/pyraptor · https://github.com/UrbanAnalyst/gtfsrouter · https://hub.docker.com/r/chairemobilite/trrouting
- https://www.microsoft.com/en-us/research/publication/round-based-public-transit-routing/ · https://www.microsoft.com/en-us/research/wp-content/uploads/2012/01/raptor_alenex.pdf · https://arxiv.org/abs/1703.05997 · https://i11www.iti.kit.edu/members/thomas_pajor/publications
- https://gtfs.org/documentation/schedule/reference/ · https://gtfs.org/documentation/realtime/reference/ · https://github.com/MobilityData/gtfs-realtime-bindings · https://github.com/MobilityData/gtfs-validator · https://github.com/mrcagney/gtfs_kit · https://github.com/remix/partridge · https://github.com/ad-freiburg/pfaedle · https://github.com/BlinkTagInc/node-gtfs · https://github.com/public-transport/gtfs-via-postgres · https://docs.pgrouting.org/latest/en/index.html · https://duckdb.org/docs/current/core_extensions/spatial/overview.html

**Maps, OSM, hosting**
- https://github.com/maplibre/maplibre-gl-js · https://raw.githubusercontent.com/mapbox/mapbox-gl-js/main/LICENSE.txt · https://www.mapbox.com/pricing · https://leafletjs.com/ · https://openfreemap.org/ · https://www.maptiler.com/cloud/pricing/ · https://docs.protomaps.com/pmtiles/cli · https://docs.protomaps.com/deploy/cost · https://stadiamaps.com/pricing/ · https://operations.osmfoundation.org/policies/tiles/ · https://github.com/ad-freiburg/loom
- https://wiki.openstreetmap.org/wiki/Overpass_API · https://dev.overpass-api.de/overpass-doc/en/preface/commons.html · https://download.geofabrik.de/asia/india.html · https://wiki.openstreetmap.org/wiki/Tag:railway%3Dstation · https://wiki.openstreetmap.org/wiki/Key:public_transport · https://wiki.openstreetmap.org/wiki/Tag:highway%3Dbus_stop · https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dbus_station · https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dtaxi · https://wiki.openstreetmap.org/wiki/Key:taxi · https://wiki.openstreetmap.org/wiki/India/Transport/Trivandrum · https://taginfo.openstreetmap.org/api/4/key/values?key=taxi_vehicle&sortname=count&sortorder=desc&rp=10 · https://wiki.openstreetmap.org/wiki/Tag:railway%3Dsubway_entrance · https://www.openstreetmap.org/copyright · https://osmfoundation.org/wiki/Licence/Attribution_Guidelines
- https://render.com/docs/free · https://docs.fly.io/about/pricing · https://railway.com/pricing · https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm · https://supabase.com/pricing · https://neon.com/pricing · https://vercel.com/docs/limits · https://developers.cloudflare.com/workers/platform/limits/ · https://developers.cloudflare.com/pages/platform/limits/ · https://education.github.com/pack
