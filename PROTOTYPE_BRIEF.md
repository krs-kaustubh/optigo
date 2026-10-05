# Optigo Prototype: Brief for the Coding Agent

*Written 2026-09-29 by Kaustubh. Put this file in the repo root of the **fork** and tell your coding agent to read it first.*

---

## 0. Who I am and how to work with me

I'm a second-year engineering student building this as a learning prototype. I want to understand what you change, not just receive it. Explain your reasoning in plain language, show test output, and never claim something works unless you ran it.

## 1. Ground rules (read before touching anything)

1. **Work only in the fork / on a new branch.** `main` in the original repo is my college Mini Project submission (final deadline **Oct 9 2026**). It must not break.
2. **Review before editing.** Phase A is read-only. Wait for my go-ahead before Phase B.
3. **RailRadar quota is tight:** 1,000 calls/month and 10/min on the sandbox key (roughly 855 left as of 2026-09-23). Record real station boards once as test fixtures, build and test offline, and tell me before any batch of live calls.
4. **Keep the 48 existing tests passing** and add tests for everything new.
5. **Don't invent data or APIs.** If a data source or API might not exist (see Section 6), say so and propose a fallback instead of writing code against an imagined endpoint.
6. **Keep docs honest:** update `ARCHITECTURE.md` and `log.md` as you go. Commit after each phase.

## 2. Where the project stands

Everything is described in `ARCHITECTURE.md`, `handoff.md`, `log.md` and `future-ideas.md`. Short version:

- FastAPI + NetworkX (Dijkstra) backend, Supabase/PostGIS data, 24 stations (Main Harbour line Vashi to Panvel, Uran line branch cut off at Kharkopar, Belapur to Pendhar Metro Line 1).
- `/compare` returns three candidate routes. `railradar.py` has a corridor model that filters live trains to ones that really carry you along the first train leg.
- Not built yet: backing and switching (Ideas 1 and 2), cab/bus integration, hot/warm node tiers, the custom map.

## 3. Priority order

| Priority | Goal |
|---|---|
| **P1** | Railway part fully working and trustworthy, **plus backing and forward switching** |
| **P2** | Multimodal routes: rail plus bus/cab for the first or last mile |
| **P3** | Cab provider layer (Uber, Ola, Rapido): fares and deep links |
| **P4** | Hot/warm node tiers and the custom map |

Do them in order. Don't start a later priority until the earlier one is verified.

## 4. Phases

### Phase A: Review only (no edits)

Read `ARCHITECTURE.md`, `handoff.md`, `log.md`, `future-ideas.md`, `backend/app/railradar.py`, `backend/app/graph.py`, `backend/app/main.py`, and this file. Then report:

1. How live train data flows through the app, in your own words.
2. Weaknesses you can already see in the train features (wrong trains, missing stations, null or stale data, quota risks).
3. Whether Ideas 1 and 2 are sound, and what you would change.
4. A concrete plan for Phases B to D, with the questions you need me to answer.

Then stop and wait.

### Phase B: Make the railway part correct (P1, part 1)

**Scope: three corridors only**
- Harbour: Panvel to Vashi (both directions)
- Uran branch from Belapur to Kharkopar (both directions)
- Uran branch from Nerul via Seawoods to Kharkopar (both directions)

**Goal:** for any station pair on these corridors, the live trains shown are the ones a person could actually board, in the right direction, with sensible times. Compare against another train app or site for the same journey.

**Test journeys (add to a fixture-based test file):**
- Panvel to Vashi and Vashi to Panvel
- Belapur to Kharkopar and the reverse
- Nerul to Kharkopar, and Seawoods to Kharkopar
- Kharghar to Vashi (the Idea 2 example)
- Khandeshwar to Nerul (the Idea 1 example)

**Method:** record boards for the relevant stations once, diagnose problems with evidence, fix them, add tests. Report anything the corridor model gets wrong.

**Done when:** all test journeys pass offline on fixtures, one careful live spot-check matches what the other app shows, and the old tests still pass.

### Phase C: Backing and forward switching (P1, part 2)

Implement the shared engine described in `future-ideas.md` (Ideas 1 and 2):

- Pivot stations: origins behind the boarding station (backing) and origins or junctions ahead of it (forward switch).
- Pair a leg-1 train with a leg-2 train using graph edge times plus a transfer buffer.
- Compare ETAs against the direct option and compute `extra_minutes`.
- Return the result as `live_alternatives` on the route. Entries use `"kind": "back"` or `"kind": "switch"`.
- **Present, don't decide.** Show the options and let the user choose. Never promise a seat; say "originates here, likely seat".
- Add a "I want a seat" toggle as a query parameter. Occupancy data doesn't exist, so this is the user's input, not something we detect.
- Cap the number of pivots to protect the quota (live calls are cached 60 seconds per station).

**Done when:** the Kharghar to Vashi and Khandeshwar to Nerul examples produce sensible alternatives on fixtures, the edge cases in `future-ideas.md` are covered by tests (boarding at an origin, branch mismatch, delays, midnight wrap), and the extra RailRadar calls per search are documented.

### Phase D: Multimodal first and last mile (P2)

**Example I want to support:** Panvel to a temple in Airoli. The best option might be: train from Panvel to Juinagar, then either a bus (if one is due soon) or a cab for the rest of the way.

Needed:
1. A way to represent destinations that aren't railway stations (a lat/lng or a named place).
2. A rule for choosing the exit station (nearest suitable station along a corridor, or ask the router to try a few).
3. A last-mile leg: bus or cab, with estimated time and cost.
4. Honest labels. Anything estimated must say "estimated".

Airoli and the area beyond Juinagar are outside the current 24-node graph, so decide first how much of the graph to expand. Propose options in Phase A and let me choose.

### Phase E: Cab provider layer (P3)

Build this behind a small interface, for example `CabProvider.estimate(origin, destination) -> {provider, fare_low, fare_high, eta_min, deeplink}`, with one implementation per provider and a fallback estimator.

See the risks in Section 6 before writing any real integration.

### Phase F: Hot/warm nodes and custom map (P4)

- **Hot nodes:** railway and metro stations, major bus stops on or near the highway, depots. Structured, scheduled, fixed.
- **Warm nodes:** auto stands and small bus stops. Informal, no official dataset.
- Candidate source for both tiers: OpenStreetMap via the Overpass API (tags like `railway=station`, `public_transport=station`, `highway=bus_stop`, `amenity=bus_station`). Expect gaps for auto stands.
- Decide with me whether this is only a display layer or whether the tiers become real graph nodes with their own routing weights. The second is a much bigger change.

## 5. Working agreement

- Small steps, tests first where it makes sense, commit per phase.
- At the end of each phase give me: what changed, why, test output, and what's still uncertain.
- If something in this brief conflicts with the actual code, trust the code and tell me.
- If you're unsure, ask one clear question rather than guessing.

## 6. Known risks and unknowns (important)

- **Cab login and fares (Uber, Ola, Rapido):** as far as I know, none of these offer an open public API that lets any developer sign users in and fetch live fare estimates in India. Uber's developer access is gated, and Ola and Rapido may not offer usable public APIs at all. **Verify before building.** Likely workable fallbacks: a transparent estimate model (base fare + per-km + per-minute, clearly marked "estimated") and deep links that open the user's installed app with pickup and drop pre-filled. Real "log in and compare" is probably a partnership-level feature, not a weekend one.
- **Bus data:** no verified live or scheduled source for Navi Mumbai buses is known. Treat bus legs as estimated until a real source is found.
- **Seat and crowding:** no occupancy data exists. "Originates here" is a heuristic only.
- **Fare slabs** for train and metro are estimates, not verified against official tables.
- **Graph size:** hot/warm nodes and Airoli-type destinations expand the graph a lot. The current design rebuilds the graph per request, so expect to add caching.

## 7. Kickoff prompt (paste this as the first message)

```
Read PROTOTYPE_BRIEF.md in the repo root, then ARCHITECTURE.md, handoff.md,
log.md, future-ideas.md and the three backend files it mentions.
Work on a new branch, not main. Do Phase A only: report what you understood,
the weaknesses you see, your opinion on Ideas 1 and 2, and a plan with
questions for me. Do not edit any files until I approve.
```
