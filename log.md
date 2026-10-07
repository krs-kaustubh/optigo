# Optigo — Work Log

Chronological record of what was changed, why, and how it was verified.
Newest entries at the bottom. Tracked in git as the project work log.

---

## 2026-09-23 — Build day, Phase 1 (backend audit + fixes)

### Audit (read-only)
- Read plan.md and ARCHITECTURE.md, then main.py, graph.py, railradar.py against live Supabase data and the live RailRadar API.
- `requests` confirmed present in backend/requirements.txt (2.34.2); clean install into a fresh venv works.
- Refuted ARCHITECTURE.md claim: the "cost" route from compare_routes can be the fare_approx path (min() runs over all candidates). Proven with Belapur CBD -> Pendhar.
- Live-status filter confirmed broken in every scenario tested (Panvel->Vashi returned trains *arriving* at Panvel; Belapur->Kharkopar dropped the Uran locals and returned Panvel-bound trains).
- Other findings: /route 500s on bad weight or unknown node; compare_routes swallows all exceptions into an empty 200; three graph rebuilds per compare; float noise in totals; repo .venv points at a removed python3.13; root requirements.txt stale.

### railradar.py rewrite
- Replaced name/destination substring matching with a corridor model (harbour, trans-harbour, trans-harbour-vashi, uran-nerul, uran-belapur). A train is kept only if it stops at the boarding station strictly before the alighting station in its direction of travel.
- Alighting station = end of the first contiguous train leg (bounded to one corridor), not the route's final node.
- Non-EMU trains dropped; sorted by expected departure; per-station board cache (60s) so /compare?live=true makes one API call.
- New `live_status` object on each route (applicable, reason, stations, codes, counts). Failures are reported, never silent.
- Station code fixes: Seawoods-Darave is SWDK (SWDV is an inactive record). Sagar Sangam is not a RailRadar station.
- RailRadar facts learned: `hours` accepts only 2/4/6/8; rate limit 10/min and 1,000/month; ~855 monthly calls remaining after this session.
- Tests: backend/tests/test_railradar.py, 28 tests, stdlib unittest, no network. All pass.
- Live verification: Panvel->Vashi, Vashi->Panvel, Belapur->Vashi, Belapur->Kharkopar, Panvel->Pendhar, Belapur->Pendhar, Panvel->Nerul all return only relevant trains. All-metro route returns `applicable: false`.
- ARCHITECTURE.md railradar section rewritten to match.

### Backup
- `~/Desktop/codes/6_36_backup.zip` — snapshot of the repo after the railradar fix and before the error-handling work. Excludes .venv, frontend/node_modules, frontend/.next, __pycache__. Includes .git and backend/.env.

### /route and compare_routes error handling
- graph.py: added `RoutingError` hierarchy (`InvalidWeight`, `UnknownNode`, `SameNode`, `NoPath`). `build_graph` validates weight; `_find_path` validates endpoints and converts `NetworkXNoPath`. `compare_routes` no longer wraps everything in bare `except: pass` — bad input raises, Supabase errors propagate, and it never returns `[]`.
- main.py: `weight` is a `Literal["time","distance","cost"]` (422 on anything else); a `RoutingError` exception handler returns `{"detail", "error"}` with 404 (UnknownNode, NoPath) / 400 (SameNode).
- Before: `/route?weight=bogus` and `/route?target=999` → bare 500; `/compare?target=999` → `[]` with 200; same-node → degenerate one-station route with 200.
- Tests: backend/tests/test_routing_errors.py (fixture graph, Supabase mocked). Full suite: 42 tests pass.
- Verified against live Supabase through the FastAPI TestClient: 422 / 404 / 400 as designed; happy paths and `/compare?live=true` unchanged.
- ARCHITECTURE.md: endpoints section gains an error table; compare_routes description corrected (cost route can be the fare_approx path).

### Remaining audit items
- graph.py: `compare_routes` now builds the graph once and passes it to the three searches (`shortest_path(..., graph=)`, `shortest_path_cost_approx(..., graph=)`). Edges carry `fare_weight` at build time. One `/compare` = 1 `fetch_nodes` + 1 `fetch_edges`, verified live via mock-counting (was 3 + 3). Response time for Belapur->Pendhar compare ~1.2 s, dominated by the two Supabase calls.
- graph.py: float totals rounded to 2 dp in `_route_result` (Belapur->Pendhar cost route now `11.8`).
- Root `requirements.txt` replaced with a forwarding stub (`-r backend/requirements.txt`) so it can never go stale again; it previously lacked `requests` and `supabase`.
- Repo `.venv` deleted and rebuilt on system Python 3.12.3 from the root requirements; all imports verified. Added `.venv/`, `venv/`, `__pycache__/` to root .gitignore (the old 3.13 venv had self-ignored via its own internal .gitignore, the new one did not).
- Tests: added `test_compare_routes_fetches_graph_once` and `test_totals_are_rounded`. Suite passes on both the temp venv and the rebuilt repo venv.
- Incident: three shell calls run in parallel shared one working directory, so a `cd` in one affected the others. Effects: a stray venv was created in `backend/.venv` (removed), and the forwarding stub was written over `backend/requirements.txt` (restored from git HEAD, which had the identical committed content). No other files were touched; verified with `git status`. Lesson recorded: use absolute paths / subshells for anything parallel.
- ARCHITECTURE.md updated: graph.py section, compare_routes step 6, Setup section.

### Folder split: optigo -> optigo-fable
- `~/Desktop/codes/optigo-fable` created by copying the fully-fixed working tree of `optigo` (rsync, excluding `.venv`, `backend/.env`, `__pycache__`; `.git` and `frontend/node_modules` included). Fresh `.venv` built on Python 3.12 from the root requirements; imports verified; 44 tests pass here.
- `backend/.env` in optigo-fable is an empty template (`SUPABASE_URL=`, `SUPABASE_KEY=`, `RAILRADAR_API_KEY=`) — keys to be pasted by hand. Gitignored.
- `~/Desktop/codes/optigo` restored from `6_36_backup.zip` to the state after the railradar fix and before the error-handling work: `git status` there shows only `backend/app/railradar.py` modified plus untracked `backend/tests/test_railradar.py`. Its rebuilt `.venv` was kept. A handoff note was prepended to its log.md.
- From here on, all work happens in optigo-fable.

### Dev-environment gotcha: Flatpak VS Code terminal
- Symptom: `uvicorn app.main:app` inside the activated `.venv` fails with `ModuleNotFoundError: No module named 'uvicorn'`, while the same venv works from a host shell.
- Cause: VS Code is installed as a Flatpak (org.freedesktop.Sdk 25.08). Its integrated terminal runs inside the sandbox, where `/usr/bin/python3` is Python 3.13.15; the host has 3.12.3. A venv's `bin/python3` is a symlink to `/usr/bin/python3`, so a venv built on the host (3.12) resolves to 3.13 inside the sandbox and finds no `lib/python3.13/site-packages`. This is also why the original `optigo/.venv` (created inside the sandbox on Aug 6 at 3.13.14) was broken on the host.
- Fix: run backend commands in a host shell. From the VS Code terminal: `flatpak-spawn --host bash`, then activate the venv as usual. Or use a system terminal. Do not rebuild the venv from inside the sandbox unless all tooling will also run there.

- Follow-up: a `host-bash` VS Code terminal profile was added and then rolled back at the user's request; settings.json is back to its original content. The user runs the backend manually with `flatpak-spawn --host ../.venv/bin/uvicorn app.main:app --reload --port 8000` from the `backend` folder.

## 2026-09-23 — Phase 2 (frontend integration)

- Backend: added `GET /nodes` (`graph.list_nodes()`, `fetch_nodes()` now also keeps `type`). Test added; suite 45 tests pass.
- Frontend (was untouched create-next-app boilerplate): `lib/api.ts` typed client with `ApiError`; `lib/routes.ts` pure helpers; `app/components/RouteCard.tsx`; `app/page.tsx` single screen (from/to pickers fed by `/nodes`, optimise-for radio, submit, 3 cards, error notice). Layout metadata set to "Optigo". Shareable `?from&to&for` URLs.
- Verification: `tsc --noEmit`, `eslint`, `next build` clean. Production build served and rendered in headless Chrome against the live backend: station list loads (24 options), Panvel→Vashi shows 3 cards with correct totals (34 min / 19 km / ₹10 ×2, 41 min / 18.6 km / ₹20), "your pick" and duplicate-journey tags correct, Belapur→Pendhar renders the all-metro + train/walk/metro candidates, same-node and unknown-node show the backend's message in an alert.
- Gotcha: `next dev` (Turbopack) exits silently mid-compile when launched from Claude Code's shell; `next dev --webpack` runs fine. Added `npm run dev:webpack` as a fallback. Untested from a normal terminal.
- Phase 3 next: render `live_status` / `live_trains` on cards with a live toggle; all-metro must read as "not applicable".

- Late fixes: `page.tsx` moved URL-param handling to `useSearchParams` inside a `Suspense` boundary (the earlier effect-based version failed `react-hooks/set-state-in-effect` lint). `lib/api.ts` unreachable-backend message now mentions CORS and the page origin, because a page served on any port other than 3000 fails with the same fetch error (backend allows `http://localhost:3000` only). `RouteCard` header no longer wraps under the "your pick" badge.
- Final verification on a clean `next build` + `next start :3000` against the live backend: `/?from=6&to=23&for=time` pre-fills both pickers, auto-runs, renders 3 cards (₹40 ×2 metro-only, ₹35 train+walk+metro cheapest), duplicate tag on the shortest card, zero alerts. `tsc`, `eslint`, `next build` clean.
- Servers I started for verification: production Next on :3000 (left running for you to look at; kill with `pkill -f next-server` when done). Dev server on :3001 stopped.

### Sporadic 500 "Server disconnected" from Supabase (found in the user's uvicorn log)
- Symptom: first request after an idle pause failed with `httpx.RemoteProtocolError: Server disconnected` deep inside postgrest/httpx; the next request worked. Cause: supabase-py keeps a pooled HTTP/2 connection that Supabase closes server-side after idling.
- Fix in graph.py: custom `httpx.Client` via `ClientOptions(httpx_client=...)` with `keepalive_expiry=15s` (idle connections discarded before Supabase drops them) + `_with_reconnect()` retrying once on `RemoteProtocolError/ReadError/WriteError/ConnectError`, then raising `UpstreamError`. main.py maps `UpstreamError` → 502 `{"detail","error":"UpstreamError"}` so the frontend shows a message instead of a raw 500.
- Tests: retry-once, persistent-failure → UpstreamError, endpoint → 502. Suite 48 tests pass. Real client imports and fetches 24 nodes; live uvicorn reloaded cleanly; a call after 45 s idle succeeds.

- Created `future-ideas.md` (gitignored) and saved **Idea 1 — Railway backing** (ride back to an origin terminus to board an originating train): problem, algorithm, open decisions, edge cases, what it builds on.

### Documentation pass
- `future-ideas.md` is now **tracked** (removed from .gitignore at the user's request — it is meant to be read by others).
- Rewrote `README.md` (root), `backend/README.md`, `frontend/README.md` to match the code as it actually is: 4 endpoints incl. `/nodes`, nested `totals`, real `live_trains`/`live_status` shapes, error table, corridor filter description, Supabase reconnect, venv/Flatpak notes, tests, updated known results and roadmap. Removed every stale claim the audit flagged (flat totals, 3× Dijkstra, `get_local_trains`/`get_train_live`, "frontend is boilerplate").
- `plan.md`: status block at top (Phase 1 & 2 done, Phase 3 next). `REPO.md`: run commands, Flatpak note, RailRadar facts, docs map. `ARCHITECTURE.md`: header/docs index, tests in structure, node-ID table incl. Vashi/RBI, environment gotchas.

- `future-ideas.md`: added **Idea 2 — Switching at a junction or origin station en route** (Kharghar→Vashi via Belapur-origin locals when trains are full): pivot candidates (origins + junctions from the corridor model), seat vs time variants, algorithm, `live_alternatives` shape shared with Idea 1, occupancy caveats (no data; user toggle), shared-engine pseudocode, cost.

### Committed and folders consolidated
- Two commits on `main`: `b9e1593` Backend (+ root docs, future-ideas.md) and `647132f` Frontend. Working tree clean.
- Old `~/Desktop/codes/optigo` (frozen at the 6_36 point) zipped to `~/Desktop/codes/before-fable_optigo.zip` (440 files, archive tested; excludes .venv, node_modules, .next, __pycache__; includes .git and backend/.env) and deleted.
- `optigo-fable` renamed to `optigo`. The venv was rebuilt because venv scripts hard-code the absolute path (`.venv/bin/uvicorn` shebang pointed at the old folder). `frontend/.next` build cache removed; it regenerates. 48 tests and `tsc` pass in the new location.
- Historical log entries above still say `optigo-fable`; that is the same folder as today's `optigo`.

## 2026-09-25 — Frontend handed back to its owner

- Teammate has started the frontend, so the Phase 2 reference UI was removed from `main`: `git branch frontend-reference 647132f` keeps it; `git revert --no-commit 647132f` staged (not committed) so `frontend/` is byte-identical to the pre-Phase-2 scaffold (verified with `git diff --quiet 36b3e62 -- frontend/`). `frontend/.next` cache removed.
- Wrote `handoff.md` (gitignored): exact API contract with shapes, `live_status.reason` → UI-state table, error table, test ids, phase expectations, gotchas (port 3000 CORS, `real_fare` not `cost`, duplicate candidates, quota). Points to `frontend-reference` for `lib/api.ts` / `lib/routes.ts`.
- README, ARCHITECTURE.md, plan.md, REPO.md updated: frontend is scaffold on `main`, owned by the teammate; reference on the branch.

## 2026-10-05 — Phase B: Local train correctness & quota guard

### Live Fixture Capture & Real-board Verification
- Captured 12 live station boards as test fixtures (`PNVL`, `KNDS`, `KHAG`, `BEPR`, `NEU`, `VSH`, `SWDK`, `TRGR`, `BMDR`, `KARP`, `JNJ`, `SNCR`) using `capture_boards.py` with 4-hour window and 6.5s pacing under the 10/min rate limit.
- Monthly quota verified from live headers: 823 calls remaining (out of 1000).
- Probed RailRadar for Sagar Sangam (`SGSGM`, `SGSG`, `SGSM`); confirmed all return 404 `STATION_NOT_FOUND`. Kept `NOT_IN_RAILRADAR = {"SGSG"}`.
- Analyzed `BEPR` vs `SWDK` live boards: confirmed 0 overlap between Belapur–Uran trains and Seawoods–Darave Uran trains. Belapur–Uran trains bypass Seawoods directly to Sagar Sangam/Targhar. Verified `CORRIDORS` model is 100% correct.

### Bug Fixes & Edge Cases
- Ghost train fix: Trains whose expected departure is in the past (>1 minute before board timestamp) are now classified as `departed` instead of lingering in `upcoming` when RailRadar labels them `scheduled`, `upcoming`, or `not-started`.
- Symmetric midnight wrap: `_departure_datetime` now wraps symmetrically (`dt > board_time + 12h -> dt - 1 day` and `dt < board_time - 12h -> dt + 1 day`).
- Timezone normalization: Normalized all naive and aware datetimes to IST (`Asia/Kolkata` / `+05:30`) to eliminate `TypeError: can't compare offset-naive and offset-aware datetimes`.
- Parse error isolation: Handled malformed payloads in `select_relevant_trains` and isolated parsing exceptions in `annotate_route_with_live_status` returning `reason: "parse_failed"` instead of unhandled 500s.
- Quota Guard: Added client-side sliding window limiter (10 calls/min), 429 response caching for 60s, disk cache (`backend/.cache/railradar`) to survive dev server reloads, and attached `quota_remaining` to `live_status`.

### Tests
- Added `backend/tests/test_phase_b_railradar.py` testing all 8 brief journeys (Panvel↔Vashi, Belapur↔Kharkopar, Nerul↔Kharkopar, Seawoods→Kharkopar, Kharghar→Vashi, Khandeshwar→Nerul) plus edge case tests for ghost trains, midnight wrap, naive/aware timestamps, and error isolation.
- Full suite: 60 tests pass (48 existing + 12 new Phase B tests).

## 2026-10-05 — Phase C: Shared alternatives engine (Backing & Forward Switching)

### Implementation (`backend/app/alternatives.py`)
- Created shared alternatives engine implementing Idea 1 (Railway Backing) and Idea 2 (Forward Switching) under `prefer_seat: bool = True`.
- `find_pivots()`: Identifies candidate pivot stations along the train corridor.
  - Backing pivots: Suburban origins (`PNVL`, `BEPR`, `NEU`, `VSH`) strictly behind the boarding station (direction away from alighting station).
  - Switching pivots: Suburban origins strictly between boarding and alighting stations.
  - Pointers sorted by proximity (detour/switch stops) and capped at 2.
- `compute_alternatives()`: Pure pairing logic using pre-fetched station boards:
  - Finds earliest upcoming direct train as time baseline.
  - Leg 1 trains: Boarding station -> pivot station.
  - Leg 2 trains: Originating trains starting at pivot station -> alighting station.
  - Origin train sorting: Originating trains explicitly sorted by expected departure to prevent picking distant trains.
  - Train-number matching across boards: Matches Leg 1 and Leg 2 across station boards to extract accurate live arrival/departure times, falling back to graph edge times if absent.
  - Transfer buffers: Enforces 4 minutes at Belapur CBD (`BEPR`), 3 minutes elsewhere.
  - Filter: Filters alternatives to `extra_minutes <= 15`, sorts by extra time, returns max 2 alternatives.
  - Includes advisory ticket note for backing journeys ("Requires valid ticket/pass for detour").
- `annotate_route_with_alternatives()`: Integrates into routing pipeline. Fetches needed pivot boards via `rr.get_station_live_board(hours=4)` (reuses 60s memory/disk cache), attaching `live_alternatives` and `live_alternatives_status`.

### API & Endpoint Extension
- `GET /compare`: Added `prefer_seat: bool = Query(False)`. When true, runs both `annotate_route_with_live_status` and `annotate_route_with_alternatives`.

### Tests
- Added `backend/tests/test_phase_c_alternatives.py` with 8 offline unit tests covering:
  - Idea 1: Khandeshwar → Nerul backing via Panvel.
  - Idea 2: Kharghar → Vashi forward switching at Belapur CBD.
  - Boarding at origin station (no backing pivots generated).
  - Non-train route handling (`applicable: false`).
  - Max pivot capping (at 2).
  - Forward switch pivot discovery.
  - Backing pivot discovery.
  - `/compare` endpoint integration with `prefer_seat=true`.
- Full test suite: **68 tests total** (48 baseline + 12 Phase B + 8 Phase C). All pass cleanly in 1.9s.

## 2026-10-05 — Phase E: Cab Provider Layer (Uber, Ola, Rapido, Auto)

### Implementation (`backend/app/cabs.py`)
- Built aggregator fare estimation engine with `CabProvider` abstract base class and 4 concrete providers:
  - `AutoRickshawProvider`: Official MMRTA meter rates (₹28 base for 1.5 km + ₹18.66/km).
  - `UberProvider`: Uber Auto, Uber Go, Uber Premier with universal deep links preloading coordinates (`https://m.uber.com/ul/?action=setPickup&client_id=optigo...`).
  - `OlaProvider`: Ola Auto, Ola Mini, Ola Prime Sedan with web/app deep links (`https://book.olacabs.com/?lat=...`).
  - `RapidoProvider`: Rapido Bike Taxi (15% faster through traffic) and Rapido Auto with app scheme deep links (`rapido://ride?...`).
- `haversine_km` and `estimate_road_distance_and_duration`: Accounts for 1.30x urban road winding factor and 25 km/h urban traffic speed.
- `get_all_cab_estimates()`: Aggregates all ride options, sorts by lowest fare, attaches distance, duration, and disclaimer.

### API & Endpoint Extension (`backend/app/main.py`)
- Added `GET /cabs/estimate`:
  - Accepts GPS coordinates (`pickup_lat, pickup_lng, dropoff_lat, dropoff_lng`) OR station IDs (`source_station_id, target_station_id`).
  - Validates inputs (404 on unknown station ID, 422 if coordinates/station IDs missing).

### Tests (`backend/tests/test_cabs.py`)
- Added 10 unit tests:
  - Haversine distance and road distance/duration estimation.
  - Fare calculations for Auto Rickshaw, Uber, Ola, Rapido.
  - Deep link format and coordinate pre-filling.
  - Aggregate sorting by lowest fare.
  - `/cabs/estimate` endpoint tests (coordinates, station IDs, 422 on missing params).
- Full test suite: **78 tests total** (all passing cleanly in 2.9s).



