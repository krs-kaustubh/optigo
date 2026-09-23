# Optigo — Future Ideas

Design notes for features not yet built. Each idea records the problem, the proposed logic, open decisions, and what already exists in the code that it can build on. Kept out of git (see .gitignore) alongside plan.md and log.md.

---

## Idea 1 — Railway backing (ride back to an origin terminus to board a fresh train)

*Captured 2026-09-23 from a discussion; not started. See Idea 2 for the forward-switch variant and the shared engine.*

### The idea
You are at boarding station **B** and want alighting station **A**. Instead of waiting for the next B→A train, ride a train in the *opposite* direction to a nearby origin terminus **T**, then board a train that *originates* at T and passes B on its way to A. You pay some extra travel time; in return you board at an origin, which in Mumbai practice means a near-certain seat and a train with no accumulated delay.

Example: at Khandeshwar wanting Nerul, take any Panvel-bound local one stop back to Panvel, then board any Panvel-origin local. Every Panvel-origin train (CSMT / Vadala Road / Goregaon / Thane-bound) shares the same stops Panvel → Khandeshwar → Mansarovar → Kharghar → Belapur CBD → Seawoods → Nerul → Juinagar and only diverges after Juinagar (Sanpada/Vashi vs Turbhe/Thane). The corridor model in `railradar.py` already encodes this (both `harbour` and `trans-harbour` contain JNJ…PNVL), so `train_serves()` handles the branch check for free.

### Origins in this network (data-driven, from `train.source` on the boards)
- **Panvel (PNVL)** — all Mumbai- and Thane-bound locals.
- **Belapur CBD (BEPR)** — Belapur–CSMT, Belapur–Vadala Road, Belapur–Uran locals.
- **Nerul (NEU)** — Nerul–Thane, Nerul–Uran locals.
- (Vashi originates Vashi–Thane trains, but Thane is outside the graph.)

So Seawoods→Vashi has two candidate origins: Belapur (1 stop back) or Panvel (5 stops back).

### Algorithm
1. **Candidate origins.** For B and A on a shared corridor, T is any origin station on that corridor on the far side of B from A. Cap the detour (e.g. ≤ 5 stops or ≤ 15 min from B).
2. **Boards.** B's board (already fetched for live status) plus T's board — one extra RailRadar call per origin, cached 60 s like the others.
3. **Backing leg.** From B's board keep trains where `train_serves(src, dst, B, T)` holds (heading toward T and stopping there). Take the next 1–2 by expected departure.
4. **Origin leg.** From T's board keep trains with `source == T` and `train_serves(T, dst, T, A)`. This single check enforces the branch: for A = Vashi it keeps CSMT/VDLR/GMN trains and rejects TNA; for A = Nerul it keeps both.
5. **Pairing.** Arrival at T ≈ backing train's expected departure at B + summed graph edge `time` B→T. Add a transfer buffer (3–5 min). The first origin train departing after that is the pair.
6. **ETAs at A.** Direct: next B→A train's expected departure + edge times B→A. Backing: origin train's departure at T + edge times T→A. Report the difference.
7. **Present, don't decide.** Attach a `live_backing` block to the route:
   ```json
   "live_backing": {
     "applicable": true, "via": "Panvel",
     "backing_train": {"train_number": "99058", "route_name": "Panvel - Thane Local", "departure_time": "18:22", "platform": "3"},
     "origin_train":  {"train_number": "98184", "route_name": "Panvel - Mumbai CSMT Local", "departure_time": "18:37", "platform": "2"},
     "eta_direct": "18:51", "eta_backing": "19:02", "extra_minutes": 11,
     "boards_at_origin": true,
     "alternatives": []
   }
   ```
   Show it only when `extra_minutes` is under a threshold (≈15) or when the direct wait exceeds the detour.

### Decisions still open
- **Travel-time source.** Graph edge times (free, approximate) vs RailRadar `/v1/trains/{number}` schedules (exact, one call per train against a 1,000/month quota). Start with edge times.
- **Where it lives.** Live layer of `railradar.py` as an annotation of the recommended route (recommended), not a fourth Dijkstra candidate. A static "seat-friendly route via nearest origin" with a time penalty could come later but would be guessing without live data.
- **Same-rake turnaround.** At Panvel the arriving train often *becomes* the next departure. If the pairing picks that rake the honest advice is "stay on board". Detect via departure within a few minutes of arrival on the same platform, or ignore in v1.
- **Seat claim wording.** Occupancy is unknown; "originates here" is a heuristic. UI must say "likely seat", never promise.
- **Threshold** for extra minutes; **one best origin or all candidates**; **transfer buffer** value.

### Edge cases (handled by the checks above)
- B is itself an origin → no backing.
- A beyond the branch point → origin train must match A's branch (`train_serves`).
- Uran line boarding (Targhar, Bamandongri, Kharkopar) → only Belapur/Nerul origins apply; the cap and `source == T` rule keep it sane.
- Delays → use expected times (include `delayMinutes`) on both boards, so a late backing train can miss its pairing correctly.
- Midnight wrap → already handled by the datetime logic in `railradar.py`.

### Builds on
- `railradar.CORRIDORS`, `train_serves()`, `first_train_leg()`, `get_station_live_board()` (cached), `select_relevant_trains()`.
- Graph edge `time` attributes from `graph.build_graph()`.
- Frontend types in `frontend/lib/api.ts` — add `LiveBacking` and render on `RouteCard` under the live board (Phase 3 work).

### Cost
- +1 RailRadar call per candidate origin per search (cached 60 s). With one origin that doubles live-status usage; watch the monthly quota.

---

## Idea 2 — Switching at a junction or origin station en route (forward switch)

*Captured 2026-09-23 from a discussion; not started. Companion to Idea 1 — same engine, opposite direction.*

### The idea
You are at boarding station **B** wanting **A**, and the trains coming through B are packed (no seat). Instead of standing all the way, ride *forward* along your route to an intermediate station **S** where trains *originate* (or where another line joins), get off, and board a train that starts at S. You pay the wait at S; in return you board at an origin, with a likely seat.

Example: **Kharghar → Vashi.** Direct is ~21 min (edge times: 5+4+3+3+3+3). Belapur CBD, two stops ahead, originates Belapur–CSMT and Belapur–Vadala Road locals that stop at Vashi. Switching means: any Mumbai-bound train Kharghar→Belapur (5 min), wait for the next Belapur-origin local (on the 2026-09-23 board they left at 18:16, 18:44, 19:20, 20:02, 20:18 — so the wait is the whole cost), then Belapur→Vashi (16 min). The UI should show exactly that: "+N min, boards at origin".

### Difference from Idea 1
| | Idea 1 — backing | Idea 2 — forward switch |
|---|---|---|
| Pivot station P | an **origin behind** B (opposite direction to A) | an **origin or junction ahead** of B (between B and A) |
| Leg 1 | train B→P against your direction | train B→P in your direction (may be a train that does *not* reach A, e.g. a Thane-bound one) |
| Leg 2 | train originating at P, serving P→A | train originating at P (seat variant) **or** any train serving P→A (time variant) |
| Typical cost | detour time + wait | wait only |

Both are the same computation with a different pivot set, so they should share one engine (see "Shared engine" below).

### Pivot candidates in this network
- **Origins** (from `train.source` on the boards): Panvel `PNVL`, Belapur CBD `BEPR` (CSMT / Vadala Road / Uran locals), Nerul `NEU` (Thane / Uran locals), Vashi `VSH` (Thane locals).
- **Junctions** (a station present in ≥ 2 corridors in `railradar.CORRIDORS`): Juinagar `JNJ` (Harbour ↔ Trans-Harbour), Sanpada `SNCR` (Harbour ↔ Thane–Vashi), Seawoods-Darave `SWDK` and Belapur `BEPR` (Harbour ↔ Uran), Nerul `NEU` (Harbour ↔ Uran).
- For a given B→A, the pivot set is the intersection of these with the stations strictly between B and A on the corridor of the first train leg. Kharghar→Vashi → {Belapur, Seawoods, Nerul, Juinagar, Sanpada}; only Belapur has origin trains toward Vashi, so the seat variant yields one option; the time variant may yield more.

### Algorithm
1. **Pivot set.** From `first_train_leg()` get B, A and the corridor; collect pivot stations between them (above). Cap at 3–4 pivots to bound API calls.
2. **Boards.** B's board (already fetched) + one board per pivot (cached 60 s).
3. **Leg 1 candidates at B.** Trains with `train_serves(src, dst, B, P)` — note this deliberately *includes* trains that don't reach A (a Thane-bound train is a fine ride to Juinagar). Next 1–2 by expected departure.
4. **Leg 2 candidates at P.**
   - *Seat variant:* `train.source == P` and `train_serves(P, dst, P, A)`.
   - *Time variant:* any train with `train_serves(src, dst, P, A)` departing after arrival.
5. **Pairing.** Arrival at P ≈ leg-1 expected departure at B + summed edge `time` B→P, plus a transfer buffer (3–5 min; platform change at Belapur is usual). First leg-2 train after that.
6. **ETAs at A.** Direct = next B→A train's expected departure + edge time B→A. Switch = leg-2 departure + edge time P→A. `extra_minutes` = switch − direct (can be negative in the time variant when the direct train is a long way off).
7. **Present, don't decide.** Attach to the route:
   ```json
   "live_alternatives": [{
     "kind": "switch", "seat": true, "via": "Belapur CBD",
     "leg1": {"train_number": "98189", "route_name": "Mumbai CSMT - Panvel Local", "departure_time": "18:34", "platform": "1"},
     "leg2": {"train_number": "98372", "route_name": "Belapur Cbd - Mumbai CSMT Local", "departure_time": "18:44", "platform": "2"},
     "eta_direct": "18:55", "eta_alternative": "19:00", "extra_minutes": 5,
     "note": "boards a train originating at Belapur CBD — likely seat"
   }]
   ```
   Idea 1 entries use `"kind": "back"` in the same list. Show the best 1–2 by `extra_minutes`; hide anything above a threshold (≈ 15–20 min) unless the user opted into "prefer a seat".

### Occupancy — what we can and cannot know
- RailRadar gives no crowding data, and there is no public Central Railway occupancy feed. "Trains are almost full" is the **user's** judgement, so this is a **toggle** ("I want a seat"), not something the app detects.
- Cheap heuristic to *offer* the toggle proactively: peak windows (roughly 08:00–11:00 towards Mumbai, 17:30–21:00 towards Panvel on weekdays). Keep it as a hint only.
- Never promise a seat; say "originates here" / "likely seat".

### Shared engine (Ideas 1 + 2)
```
alternatives(route, boards, prefer_seat):
    B, A, corridor = first_train_leg(route)
    pivots = origins_behind(B, A)          # Idea 1
           + origins_and_junctions_between(B, A)   # Idea 2
    for P in pivots (capped):
        leg1 = trains_at(B) serving B→P
        leg2 = trains_at(P) serving P→A  (source == P if prefer_seat)
        pair earliest feasible, compute ETAs vs direct
    return sorted by extra_minutes, top N
```
Builds on `CORRIDORS`, `train_serves()`, `first_train_leg()`, `get_station_live_board()` (cached), graph edge `time`s. One new module-level helper to sum edge times between two stations on a corridor (graph already has the edges).

### Open decisions
- Threshold for `extra_minutes`; how many alternatives to show; transfer buffer value.
- Seat-only vs also the time variant in v1 (time variant is where junction switching actually beats direct; seat variant is the user's stated need — start with seat, keep the time variant behind the same engine).
- Whether the toggle is per search or a saved preference.
- Same-rake caveat from Idea 1 applies at Panvel; not at Belapur (Belapur-origin trains are separate rakes from the through trains).

### Cost
- +1 RailRadar call per pivot per search (cached 60 s). Kharghar→Vashi with pivots capped at 3 = up to 4 calls per live search. Budget accordingly (1,000/month sandbox).
