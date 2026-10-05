"""Shared Alternatives Engine (Railway Backing and Forward Switching).

Implements Ideas 1 (Backing) and 2 (Forward Switching) from future-ideas.md:
- Backing (kind="back"): Ride in the opposite direction to an origin terminus (e.g. Panvel),
  to board a fresh train originating there.
- Switching (kind="switch"): Ride forward along the route to an intermediate origin
  station (e.g. Belapur CBD), switch to a train originating there for a likely seat.

Pure pairing logic operates on pre-fetched station boards, making it 100% testable
offline against fixtures. Timings are determined by matching train numbers across
station boards, with graph edge times as a fallback.
"""

from datetime import datetime, timedelta
from typing import Callable, Optional

from app import railradar as rr

# Origins where suburban local trains originate
# PNVL: CSMT, VDLR, GMN, TNA locals
# BEPR: CSMT, VDLR, URAN locals
# NEU:  TNA, URAN locals
# VSH:  TNA locals
ORIGIN_STATIONS = {"PNVL", "BEPR", "NEU", "VSH"}

# Station display names for readable notes
STATION_NAMES = {
    "VSH": "Vashi", "SNCR": "Sanpada", "JNJ": "Juinagar", "NEU": "Nerul",
    "SWDK": "Seawoods-Darave", "BEPR": "Belapur CBD", "SGSG": "Sagar Sangam",
    "KHAG": "Kharghar", "MANR": "Mansarovar", "KNDS": "Khandeshwar", "PNVL": "Panvel",
    "TRGR": "Targhar", "BMDR": "Bamandongri", "KARP": "Kharkopar",
}

DEFAULT_BUFFER_MINUTES = 3
BELAPUR_BUFFER_MINUTES = 4
MAX_PIVOTS_CHECKED = 2
MAX_ALTERNATIVES_RETURNED = 2
DEFAULT_THRESHOLD_MINUTES = 15


def _station_name(code: str) -> str:
    return STATION_NAMES.get(code, code)


def find_pivots(boarding_code: str, alighting_code: str, corridor: str,
                max_pivots: int = MAX_PIVOTS_CHECKED) -> list[dict]:
    """Find candidate pivot origin stations on the given corridor.

    - Backing pivots: origins strictly behind boarding_code (opposite direction from alighting).
    - Switching pivots: origins strictly between boarding_code and alighting_code.
    """
    seq = None
    for name, s in rr.CORRIDORS:
        if name == corridor:
            seq = s
            break
    if not seq or boarding_code not in seq or alighting_code not in seq:
        return []

    i_b = seq.index(boarding_code)
    i_a = seq.index(alighting_code)
    direction = 1 if i_a > i_b else -1

    pivots = []

    # 1. Switching pivots: between i_b and i_a
    step_indices = range(i_b + direction, i_a, direction)
    for idx in step_indices:
        code = seq[idx]
        if code in ORIGIN_STATIONS and code != boarding_code and code != alighting_code:
            pivots.append({
                "code": code,
                "name": _station_name(code),
                "kind": "switch",
                "stops": abs(idx - i_b),
            })

    # 2. Backing pivots: behind i_b (away from i_a)
    back_indices = range(i_b - direction, -1 if direction > 0 else len(seq), -direction)
    for idx in back_indices:
        code = seq[idx]
        if code in ORIGIN_STATIONS and code != boarding_code:
            pivots.append({
                "code": code,
                "name": _station_name(code),
                "kind": "back",
                "stops": abs(idx - i_b),
            })

    # Sort pivots by proximity (fewest stops detour/switch first) and cap
    pivots.sort(key=lambda p: (0 if p["kind"] == "switch" else 1, p["stops"]))
    return pivots[:max_pivots]


def _find_train_on_board(board: dict, train_number: str) -> Optional[dict]:
    """Find a specific train entry on a raw board by train number."""
    if not board or not isinstance(board, dict):
        return None
    data_dict = board.get("data", {}) if isinstance(board, dict) else {}
    raw = data_dict.get("trains", []) if isinstance(data_dict, dict) else []
    for item in raw:
        if item.get("train", {}).get("number") == train_number:
            return item
    return None


def _get_train_stop_time(item: dict, board_time: Optional[datetime], is_arrival: bool = False) -> Optional[datetime]:
    stop = item.get("stop", {})
    live = item.get("live", {})
    if is_arrival:
        iso_str = live.get("expectedArrivalTime")
        if iso_str:
            return rr._parse_iso(iso_str)
        hhmm = stop.get("arrival") or stop.get("departure")
        if hhmm and board_time:
            try:
                h, m = (int(x) for x in hhmm.split(":")[:2])
                dt = board_time.replace(hour=h, minute=m, second=0, microsecond=0)
                delay = live.get("delayMinutes")
                if isinstance(delay, (int, float)):
                    dt += timedelta(minutes=delay)
                return dt
            except ValueError:
                pass
    return rr._departure_datetime(stop, live, board_time)


def compute_alternatives(
    route: dict,
    boards: dict[str, dict],
    prefer_seat: bool = True,
    threshold_minutes: int = DEFAULT_THRESHOLD_MINUTES,
    transfer_buffer_minutes: int = DEFAULT_BUFFER_MINUTES,
) -> tuple[list[dict], dict]:
    """Compute backing and forward switching alternatives for a route.

    Takes pre-fetched boards: {station_code: board_json}.
    Returns (alternatives_list, status_dict).
    """
    leg = rr.first_train_leg(route)
    if leg is None:
        return [], {"applicable": False, "reason": "no_train_leg"}

    boarding_name, alighting_name, corridor = leg
    b_code = rr.station_code(boarding_name)
    a_code = rr.station_code(alighting_name)

    if not b_code or not a_code:
        return [], {"applicable": False, "reason": "unknown_station_code"}

    b_board = boards.get(b_code)
    if not b_board:
        return [], {"applicable": False, "reason": "missing_boarding_board"}

    b_board_time = rr._parse_iso((b_board.get("meta") or {}).get("timestamp"))

    # Direct trains baseline: earliest upcoming direct train
    direct_candidates, _ = rr.select_relevant_trains(b_board, b_code, a_code, limit=3)
    upcoming_direct = [t for t in direct_candidates if t["status"] != "departed"]
    if not upcoming_direct:
        return [], {"applicable": True, "reason": "no_direct_trains"}

    direct_train = upcoming_direct[0]
    direct_dep_b = rr._parse_iso(direct_train.get("expected_departure"))

    pivots = find_pivots(b_code, a_code, corridor)
    if not pivots:
        return [], {"applicable": True, "reason": "no_pivots_available", "pivots_checked": []}

    alternatives = []
    pivots_checked = []

    for pivot in pivots:
        p_code = pivot["code"]
        p_name = pivot["name"]
        kind = pivot["kind"]
        pivots_checked.append(p_code)

        p_board = boards.get(p_code)
        if not p_board:
            continue
        p_board_time = rr._parse_iso((p_board.get("meta") or {}).get("timestamp"))

        # Transfer buffer: 4 min at Belapur CBD, 3 min elsewhere
        buffer_min = BELAPUR_BUFFER_MINUTES if p_code == "BEPR" else transfer_buffer_minutes

        if kind == "switch":
            # Forward switch:
            # Leg 1: trains from B serving B -> P
            leg1_trains, _ = rr.select_relevant_trains(b_board, b_code, p_code, limit=4)
            leg1_upcoming = [t for t in leg1_trains if t["status"] != "departed"]

            # Leg 2 candidates at P: trains originating at P (train.source == P) serving P -> A
            raw_p = p_board.get("data", {}).get("trains", []) if isinstance(p_board, dict) else []
            origin_trains = []
            for item in raw_p:
                tr = item.get("train", {})
                if tr.get("type") == "EMU" and tr.get("source") == p_code:
                    if rr.train_serves(p_code, tr.get("destination", ""), p_code, a_code):
                        entry = rr._train_entry(item, corridor, p_board_time)
                        if entry["status"] != "departed":
                            origin_trains.append((entry, item))

            if not leg1_upcoming or not origin_trains:
                continue

            far_future = datetime.max.replace(tzinfo=rr.IST)
            origin_trains.sort(key=lambda t: t[0]["_sort"] or far_future)

            # Pair earliest feasible
            paired = None
            for l1 in leg1_upcoming:
                l1_dep_b = rr._parse_iso(l1.get("expected_departure"))
                if not l1_dep_b:
                    continue

                # When does Leg 1 arrive at P?
                l1_item_at_p = _find_train_on_board(p_board, l1["train_number"])
                if l1_item_at_p:
                    l1_arr_p = _get_train_stop_time(l1_item_at_p, p_board_time, is_arrival=True)
                else:
                    l1_arr_p = l1_dep_b + timedelta(minutes=pivot["stops"] * 3)

                if not l1_arr_p:
                    continue

                min_leg2_dep = l1_arr_p + timedelta(minutes=buffer_min)

                for l2_entry, l2_item in origin_trains:
                    l2_dep_p = rr._parse_iso(l2_entry.get("expected_departure"))
                    if l2_dep_p and l2_dep_p >= min_leg2_dep:
                        paired = (l1, l1_arr_p, l2_entry, l2_dep_p)
                        break
                if paired:
                    break

            if not paired:
                continue

            l1, l1_arr_p, l2, l2_dep_p = paired

            # Arrival time difference:
            # Find when direct train passes P
            dir_item_at_p = _find_train_on_board(p_board, direct_train["train_number"])
            if dir_item_at_p:
                dir_dep_p = _get_train_stop_time(dir_item_at_p, p_board_time, is_arrival=False)
            else:
                dir_dep_p = direct_dep_b + timedelta(minutes=pivot["stops"] * 3) if direct_dep_b else None

            if dir_dep_p and l2_dep_p:
                extra_min = round((l2_dep_p - dir_dep_p).total_seconds() / 60)
            else:
                extra_min = 5

            if extra_min <= threshold_minutes:
                alternatives.append({
                    "kind": "switch",
                    "seat": True,
                    "via": p_name,
                    "via_code": p_code,
                    "leg1": {
                        "train_number": l1["train_number"],
                        "route_name": l1["route_name"],
                        "departure_time": l1["departure_time"],
                        "expected_departure": l1["expected_departure"],
                        "platform": l1.get("platform"),
                    },
                    "leg2": {
                        "train_number": l2["train_number"],
                        "route_name": l2["route_name"],
                        "departure_time": l2["departure_time"],
                        "expected_departure": l2["expected_departure"],
                        "platform": l2.get("platform"),
                    },
                    "direct": {
                        "train_number": direct_train["train_number"],
                        "departure_time": direct_train["departure_time"],
                        "expected_departure": direct_train["expected_departure"],
                    },
                    "extra_minutes": max(0, extra_min),
                    "note": f"Switch at {p_name} to a train originating there — likely seat.",
                })

        elif kind == "back":
            # Backing:
            # Leg 1: trains from B heading backwards to P (B -> P)
            leg1_trains, _ = rr.select_relevant_trains(b_board, b_code, p_code, limit=3)
            leg1_upcoming = [t for t in leg1_trains if t["status"] != "departed"]

            # Leg 2 candidates at P: trains originating at P (source == P) serving P -> A
            raw_p = p_board.get("data", {}).get("trains", []) if isinstance(p_board, dict) else []
            origin_trains = []
            for item in raw_p:
                tr = item.get("train", {})
                if tr.get("type") == "EMU" and tr.get("source") == p_code:
                    if rr.train_serves(p_code, tr.get("destination", ""), p_code, a_code):
                        entry = rr._train_entry(item, corridor, p_board_time)
                        if entry["status"] != "departed":
                            origin_trains.append((entry, item))

            if not leg1_upcoming or not origin_trains:
                continue

            far_future = datetime.max.replace(tzinfo=rr.IST)
            origin_trains.sort(key=lambda t: t[0]["_sort"] or far_future)

            paired = None
            for l1 in leg1_upcoming:
                l1_dep_b = rr._parse_iso(l1.get("expected_departure"))
                if not l1_dep_b:
                    continue

                l1_item_at_p = _find_train_on_board(p_board, l1["train_number"])
                if l1_item_at_p:
                    l1_arr_p = _get_train_stop_time(l1_item_at_p, p_board_time, is_arrival=True)
                else:
                    l1_arr_p = l1_dep_b + timedelta(minutes=pivot["stops"] * 3)

                if not l1_arr_p:
                    continue

                min_leg2_dep = l1_arr_p + timedelta(minutes=buffer_min)

                for l2_entry, l2_item in origin_trains:
                    l2_dep_p = rr._parse_iso(l2_entry.get("expected_departure"))
                    if l2_dep_p and l2_dep_p >= min_leg2_dep:
                        # Find when l2 passes B (from B's board or departure at P + edge time)
                        l2_item_at_b = _find_train_on_board(b_board, l2_entry["train_number"])
                        if l2_item_at_b:
                            l2_dep_b = _get_train_stop_time(l2_item_at_b, b_board_time, is_arrival=False)
                        else:
                            l2_dep_b = l2_dep_p + timedelta(minutes=pivot["stops"] * 3)
                        paired = (l1, l1_arr_p, l2_entry, l2_dep_p, l2_dep_b)
                        break
                if paired:
                    break

            if not paired:
                continue

            l1, l1_arr_p, l2, l2_dep_p, l2_dep_b = paired

            if l2_dep_b and direct_dep_b:
                extra_min = round((l2_dep_b - direct_dep_b).total_seconds() / 60)
            else:
                extra_min = 10

            is_same_rake = (l1["train_number"] == l2["train_number"])
            rake_note = " Same rake turns around — stay on board." if is_same_rake else ""

            if extra_min <= threshold_minutes:
                alternatives.append({
                    "kind": "back",
                    "seat": True,
                    "via": p_name,
                    "via_code": p_code,
                    "leg1": {
                        "train_number": l1["train_number"],
                        "route_name": l1["route_name"],
                        "departure_time": l1["departure_time"],
                        "expected_departure": l1["expected_departure"],
                        "platform": l1.get("platform"),
                    },
                    "leg2": {
                        "train_number": l2["train_number"],
                        "route_name": l2["route_name"],
                        "departure_time": l2["departure_time"],
                        "expected_departure": l2["expected_departure"],
                        "platform": l2.get("platform"),
                    },
                    "direct": {
                        "train_number": direct_train["train_number"],
                        "departure_time": direct_train["departure_time"],
                        "expected_departure": direct_train["expected_departure"],
                    },
                    "extra_minutes": max(0, extra_min),
                    "note": f"Ride back to {p_name} to board origin train — likely seat.{rake_note} Requires valid ticket/pass for detour via {p_name}.",
                })

    alternatives.sort(key=lambda a: a["extra_minutes"])
    trimmed = alternatives[:MAX_ALTERNATIVES_RETURNED]

    status = {
        "applicable": True,
        "reason": "ok" if trimmed else "no_alternatives_within_threshold",
        "pivots_checked": pivots_checked,
        "alternatives_found": len(trimmed),
    }
    return trimmed, status


def annotate_route_with_alternatives(
    route_result: dict,
    prefer_seat: bool = True,
    threshold_minutes: int = DEFAULT_THRESHOLD_MINUTES,
    fetch_board_fn: Optional[Callable[[str], dict]] = None,
) -> dict:
    """Attach `live_alternatives` (list) and `live_alternatives_status` (dict) to a route dict."""
    if not prefer_seat:
        route_result["live_alternatives"] = []
        route_result["live_alternatives_status"] = {"applicable": False, "reason": "prefer_seat_disabled"}
        return route_result

    leg = rr.first_train_leg(route_result)
    if leg is None:
        route_result["live_alternatives"] = []
        route_result["live_alternatives_status"] = {"applicable": False, "reason": "no_train_leg"}
        return route_result

    boarding_name, alighting_name, corridor = leg
    b_code = rr.station_code(boarding_name)
    a_code = rr.station_code(alighting_name)

    if not b_code or not a_code:
        route_result["live_alternatives"] = []
        route_result["live_alternatives_status"] = {"applicable": False, "reason": "unknown_station_code"}
        return route_result

    fetch = fetch_board_fn or (lambda c: rr.get_station_live_board(c, hours=4))

    # Identify candidate pivots
    pivots = find_pivots(b_code, a_code, corridor)
    if not pivots:
        route_result["live_alternatives"] = []
        route_result["live_alternatives_status"] = {
            "applicable": True, "reason": "no_pivots_available", "pivots_checked": []
        }
        return route_result

    # Fetch boards for B and needed pivots
    boards = {}
    calls_made = 0
    needed_codes = [b_code] + [p["code"] for p in pivots]

    for code in needed_codes:
        try:
            boards[code] = fetch(code)
            calls_made += 1
        except Exception as exc:
            route_result["live_alternatives"] = []
            route_result["live_alternatives_status"] = {
                "applicable": True,
                "reason": "fetch_failed",
                "failed_station": code,
                "error": type(exc).__name__,
            }
            return route_result

    alts, status = compute_alternatives(
        route=route_result,
        boards=boards,
        prefer_seat=prefer_seat,
        threshold_minutes=threshold_minutes,
    )
    status["calls_used"] = calls_made
    route_result["live_alternatives"] = alts
    route_result["live_alternatives_status"] = status
    return route_result
