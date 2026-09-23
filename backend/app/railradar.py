"""RailRadar live-status integration.

Attaches an m-Indicator style live board (recently departed + upcoming locals)
to a route produced by graph.py. Only trains that actually carry the user from
the boarding station towards the alighting station of the first train leg are
returned; everything else on the station board (arrivals that terminate here,
trains on other branches, wrong-direction trains, long-distance expresses) is
filtered out using the corridor model below.
"""

import os
import time
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

RAILRADAR_BASE = "https://api.railradar.in/v1"
RAILRADAR_KEY = os.environ.get("RAILRADAR_API_KEY", "")

# RailRadar only accepts these window sizes for /stations/{code}/live.
BOARD_HOURS = 2
BOARD_CACHE_TTL_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 10

# --------------------------------------------------------------------------
# Station codes
# --------------------------------------------------------------------------

# Graph station name (normalized with _normalize) -> RailRadar station code.
# Codes verified against the live API on 2026-09-23. Sagar Sangam is a junction
# with no passenger halt and does not exist in RailRadar; it keeps an internal
# token so it can still be positioned on a corridor below.
STATION_CODES = {
    "vashi": "VSH",
    "sanpada": "SNCR",
    "juinagar": "JNJ",
    "nerul": "NEU",
    "seawoodsdarave": "SWDK",
    "belapurcbd": "BEPR",
    "belapur": "BEPR",
    "sagarsangam": "SGSG",
    "kharghar": "KHAG",
    "mansarovar": "MANR",
    "khandeshwar": "KNDS",
    "panvel": "PNVL",
    "targhar": "TRGR",
    "bamandongri": "BMDR",
    "kharkopar": "KARP",
}

# Codes that appear in our graph but have no live board on RailRadar.
NOT_IN_RAILRADAR = {"SGSG"}

# Termini outside the Navi Mumbai graph, grouped by which side of the network
# they sit on. A train whose source/destination is in one of these groups is
# positioned at the matching "@" anchor of a corridor.
MUMBAI_SIDE = {"CSMT", "VDLR", "GMN", "BA", "ADH", "CLA", "KCE", "MNKD", "CMBR", "WR"}
THANE_SIDE = {"TNA", "ARLI", "RABE", "GNSL", "KPHN", "TUH"}
URAN_SIDE = {"URAN", "GAVN", "RJPD", "NHVS", "DRNG"}

ANCHORS = {"@MUMBAI": MUMBAI_SIDE, "@THANE": THANE_SIDE, "@URAN": URAN_SIDE}

# Ordered station lists. A train from source S to destination D on a corridor
# stops at every station between S and D, in order. Derived from the actual
# station boards on 2026-09-23:
#   - Thane–Panvel/Nerul trains skip Sanpada (Turbhe joins at Juinagar).
#   - Thane–Vashi trains do stop at Sanpada.
#   - Uran trains run from both Nerul (via Seawoods) and Belapur.
CORRIDORS = [
    ("harbour", ["@MUMBAI", "VSH", "SNCR", "JNJ", "NEU", "SWDK", "BEPR",
                 "KHAG", "MANR", "KNDS", "PNVL"]),
    ("trans-harbour", ["@THANE", "JNJ", "NEU", "SWDK", "BEPR",
                       "KHAG", "MANR", "KNDS", "PNVL"]),
    ("trans-harbour-vashi", ["@THANE", "SNCR", "VSH"]),
    ("uran-nerul", ["NEU", "SWDK", "SGSG", "TRGR", "BMDR", "KARP", "@URAN"]),
    ("uran-belapur", ["BEPR", "SGSG", "TRGR", "BMDR", "KARP", "@URAN"]),
]

# RailRadar `train.type` values that are suburban locals.
SUBURBAN_TRAIN_TYPES = {"EMU"}

# Human-readable direction labels for the destination shown on a train card.
DESTINATION_NAMES = {
    "CSMT": "Mumbai CSMT", "VDLR": "Vadala Road", "GMN": "Goregaon",
    "BA": "Bandra", "ADH": "Andheri", "TNA": "Thane", "URAN": "Uran",
    "PNVL": "Panvel", "BEPR": "Belapur CBD", "NEU": "Nerul", "VSH": "Vashi",
}


def _normalize(s) -> str:
    return "".join(ch.lower() for ch in str(s) if ch.isalnum())


def station_code(name) -> str | None:
    """Graph station name -> RailRadar code (or internal token), else None."""
    if name is None:
        return None
    return STATION_CODES.get(_normalize(name))


def _place(code: str) -> str:
    """Map a RailRadar code to its corridor token (an anchor for far termini)."""
    for anchor, members in ANCHORS.items():
        if code in members:
            return anchor
    return code


# --------------------------------------------------------------------------
# Corridor logic
# --------------------------------------------------------------------------

def _corridor_positions(seq, *codes):
    """Indices of `codes` in `seq`, or None if any is missing."""
    try:
        return [seq.index(c) for c in codes]
    except ValueError:
        return None


def train_serves(source: str, destination: str, boarding: str, alighting: str):
    """Return the corridor name if a train running source->destination carries
    a passenger from `boarding` to `alighting`, else None.

    The train must stop at boarding strictly before alighting in its direction
    of travel, and must not terminate at or before the boarding station.
    """
    s, d = _place(source), _place(destination)
    if s == d:
        return None
    for name, seq in CORRIDORS:
        pos = _corridor_positions(seq, s, d, boarding, alighting)
        if pos is None:
            continue
        i_s, i_d, i_b, i_a = pos
        if i_s < i_d and i_s <= i_b < i_a <= i_d:
            return name
        if i_s > i_d and i_s >= i_b > i_a >= i_d:
            return name
    return None


def first_train_leg(route_result: dict):
    """Identify the first train leg of a route.

    Returns (boarding_name, alighting_name, corridor) or None if the route has
    no train edge. Consecutive train edges form one segment; the alighting
    station is the farthest station along that segment that still lies on a
    single corridor with the boarding station (i.e. where the passenger would
    have to change trains at the latest).
    """
    edges = route_result.get("edges", [])
    start = next((i for i, e in enumerate(edges) if e.get("mode") == "train"), None)
    if start is None:
        return None

    stations = [edges[start].get("from")]
    for e in edges[start:]:
        if e.get("mode") != "train":
            break
        stations.append(e.get("to"))

    codes = [station_code(s) for s in stations]
    boarding = stations[0]
    if codes[0] is None or len(stations) < 2:
        return boarding, stations[-1], None

    best_alight, best_corridor = stations[1], None
    for name, seq in CORRIDORS:
        if codes[0] not in seq:
            continue
        # Longest prefix of the segment that is monotonic along this corridor.
        idx = [seq.index(c) if c in seq else None for c in codes]
        n = 1
        while n < len(idx) and idx[n] is not None:
            step = idx[n] - idx[n - 1]
            if abs(step) != 1 or (n > 1 and (step > 0) != (idx[n - 1] - idx[n - 2] > 0)):
                break
            n += 1
        if n > 1 and (best_corridor is None or n - 1 > stations.index(best_alight)):
            best_alight, best_corridor = stations[n - 1], name
    return boarding, best_alight, best_corridor


# --------------------------------------------------------------------------
# RailRadar client
# --------------------------------------------------------------------------

_BOARD_CACHE: dict = {}  # station_code -> (monotonic_ts, board_json)


def get_station_live_board(code: str, hours: int = BOARD_HOURS, use_cache: bool = True):
    """Fetch the live arrival/departure board for a station.

    Cached per station for BOARD_CACHE_TTL_SECONDS so that annotating the
    three /compare candidates costs one API call, not three.
    """
    now = time.monotonic()
    if use_cache:
        hit = _BOARD_CACHE.get(code)
        if hit and now - hit[0] < BOARD_CACHE_TTL_SECONDS:
            return hit[1]

    if not RAILRADAR_KEY:
        raise RuntimeError("RAILRADAR_API_KEY is not set")

    resp = requests.get(
        f"{RAILRADAR_BASE}/stations/{code}/live",
        params={"hours": hours},
        headers={"Authorization": f"Bearer {RAILRADAR_KEY}"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    _BOARD_CACHE[code] = (now, data)
    return data


def clear_board_cache():
    _BOARD_CACHE.clear()


# --------------------------------------------------------------------------
# Board parsing
# --------------------------------------------------------------------------

def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _departure_datetime(stop: dict, live: dict, board_time: datetime | None):
    """Best available departure time for sorting: RailRadar's expected time,
    else the scheduled HH:MM placed on the board's date (with midnight wrap)."""
    expected = _parse_iso(live.get("expectedDepartureTime"))
    if expected:
        return expected
    hhmm = stop.get("departure")
    if not hhmm or board_time is None:
        return None
    try:
        h, m = (int(x) for x in hhmm.split(":")[:2])
    except ValueError:
        return None
    dt = board_time.replace(hour=h, minute=m, second=0, microsecond=0)
    delay = live.get("delayMinutes")
    if isinstance(delay, (int, float)):
        dt += timedelta(minutes=delay)
    if dt < board_time - timedelta(hours=12):
        dt += timedelta(days=1)
    return dt


def _train_entry(item: dict, corridor: str, board_time):
    train, stop, live = item.get("train", {}), item.get("stop", {}), item.get("live", {})
    delay = live.get("delayMinutes")
    dest = train.get("destination", "")
    when = _departure_datetime(stop, live, board_time)
    return {
        "train_number": train.get("number"),
        "route_name": train.get("name", ""),
        "towards": DESTINATION_NAMES.get(dest, dest),
        "destination_code": dest,
        "line": corridor,
        "departure_time": stop.get("departure"),
        "expected_departure": when.isoformat() if when else None,
        "platform": stop.get("platform"),
        "status": live.get("type", "scheduled"),
        "delay_minutes": delay if isinstance(delay, (int, float)) else None,
        "_sort": when,
    }


def select_relevant_trains(board: dict, boarding_code: str, alighting_code: str, limit: int):
    """Filter a raw RailRadar board down to trains that serve boarding ->
    alighting, ordered by departure time. Returns (departed, upcoming, stats)."""
    raw = board.get("data", {}).get("trains", []) if isinstance(board, dict) else []
    board_time = _parse_iso((board.get("meta") or {}).get("timestamp")) if isinstance(board, dict) else None

    departed, upcoming = [], []
    skipped = {"not_suburban": 0, "not_serving_route": 0}
    for item in raw:
        train = item.get("train", {})
        if train.get("type") not in SUBURBAN_TRAIN_TYPES:
            skipped["not_suburban"] += 1
            continue
        corridor = train_serves(train.get("source", ""), train.get("destination", ""),
                                boarding_code, alighting_code)
        if corridor is None or not item.get("stop", {}).get("departure"):
            skipped["not_serving_route"] += 1
            continue
        entry = _train_entry(item, corridor, board_time)
        (departed if entry["status"] == "departed" else upcoming).append(entry)

    far_future = datetime.max.replace(tzinfo=board_time.tzinfo) if board_time else None
    key = lambda e: e["_sort"] or far_future or datetime.max  # noqa: E731
    departed.sort(key=key)
    upcoming.sort(key=key)

    selected = departed[-2:] + upcoming[:limit]
    for e in selected:
        e.pop("_sort", None)
    stats = {
        "trains_on_board": len(raw),
        "relevant_trains": len(departed) + len(upcoming),
        "board_time": board_time.isoformat() if board_time else None,
        **skipped,
    }
    return selected, stats


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def annotate_route_with_live_status(route_result: dict, limit: int = 5):
    """Attach `live_trains` (list) and `live_status` (dict) to a route dict.

    `live_status.applicable` is False when the route has no train leg, so the
    UI can show "not applicable" instead of "no data". `live_status.reason`
    is one of: ok, no_relevant_trains, no_train_leg, station_not_in_railradar,
    api_key_missing, fetch_failed.
    """
    def finish(reason, applicable, **extra):
        route_result.setdefault("live_trains", [])
        route_result["live_status"] = {"applicable": applicable, "reason": reason, **extra}
        return route_result

    route_result["live_trains"] = []

    leg = first_train_leg(route_result)
    if leg is None:
        return finish("no_train_leg", applicable=False)
    boarding, alighting, corridor = leg
    b_code, a_code = station_code(boarding), station_code(alighting)
    info = {
        "boarding_station": boarding, "alighting_station": alighting,
        "boarding_code": b_code, "alighting_code": a_code, "line": corridor,
    }

    if b_code is None or a_code is None or b_code in NOT_IN_RAILRADAR:
        return finish("station_not_in_railradar", applicable=True, **info)
    if not RAILRADAR_KEY:
        return finish("api_key_missing", applicable=True, **info)

    try:
        board = get_station_live_board(b_code)
    except Exception as exc:  # network, HTTP, JSON
        return finish("fetch_failed", applicable=True, error=type(exc).__name__, **info)

    selected, stats = select_relevant_trains(board, b_code, a_code, limit)
    route_result["live_trains"] = selected
    reason = "ok" if selected else "no_relevant_trains"
    return finish(reason, applicable=True, **info, **stats)
