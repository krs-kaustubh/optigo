import os
import requests
from dotenv import load_dotenv

load_dotenv()

RAILRADAR_BASE = "https://api.railradar.in/v1"
RAILRADAR_KEY = os.environ.get("RAILRADAR_API_KEY", "")

# Station code mapping for Harbour & Uran lines
STATION_CODES = {
    "vashi": "VSH",
    "sanpada": "SNCR",
    "juinagar": "JNJ",
    "nerul": "NEU",
    "seawoods-darave": "SWDV",
    "seawoodsdarave": "SWDV",
    "seawoods darave": "SWDV",
    "belapur cbd": "BEPR",
    "belapur": "BEPR",
    "sagarsangam": "SGSG",
    "sagar sangam": "SGSG",
    "kharghar": "KHAG",
    "mansarovar": "MANR",
    "khandeshwar": "KNDS",
    "panvel": "PNVL",
    "targhar": "TRGR",
    "bamandongri": "BMDR",
    "kharkopar": "KARP",
}


def _normalize(s: str) -> str:
    return "".join(ch.lower() for ch in str(s) if ch.isalnum())


def get_station_live_board(station_code: str, hours: int = 2):
    """Fetch live departure/arrival board for a station from RailRadar."""
    resp = requests.get(
        f"{RAILRADAR_BASE}/stations/{station_code}/live",
        params={"hours": hours},
        headers={"Authorization": f"Bearer {RAILRADAR_KEY}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def annotate_route_with_live_status(route_result: dict, limit: int = 5):
    """
    Attaches m-Indicator style live train board (past departed + upcoming)
    to a route dict based on the first train boarding station in the route.
    """
    edges = route_result.get("edges", [])
    path = route_result.get("path", [])

    # Find the boarding station for the first train segment
    boarding_station = None
    target_station = path[-1] if path else None

    for edge in edges:
        if edge.get("mode") == "train":
            boarding_station = edge.get("from")
            break

    # If no train edge exists, return empty list
    if not boarding_station:
        route_result["live_trains"] = []
        return route_result

    # Look up station code
    norm_name = boarding_station.strip().lower()
    code = STATION_CODES.get(norm_name) or STATION_CODES.get(_normalize(boarding_station))

    if not code:
        route_result["live_trains"] = []
        return route_result

    try:
        board_data = get_station_live_board(code, hours=2)
    except Exception:
        route_result["live_trains"] = []
        return route_result

    raw_trains = (
        board_data.get("data", {}).get("trains", [])
        if isinstance(board_data, dict)
        else []
    )

    if not raw_trains:
        route_result["live_trains"] = []
        return route_result

    # Direction matching: find target station code if available
    target_code = None
    if target_station:
        norm_target_name = target_station.strip().lower()
        target_code = STATION_CODES.get(norm_target_name) or STATION_CODES.get(_normalize(target_station))

    departed = []
    upcoming = []

    for item in raw_trains:
        t_info = item.get("train", {})
        stop_info = item.get("stop", {})
        live_info = item.get("live", {})

        status_type = live_info.get("type", "scheduled")
        delay = live_info.get("delayMinutes", 0)
        dep_time = stop_info.get("departure") or stop_info.get("arrival") or ""
        platform = stop_info.get("platform", "—")

        train_dest = t_info.get("destination", "")
        train_name = t_info.get("name", "")

        # If user is heading towards Panvel (PNVL), prioritize trains going that way
        is_relevant = True
        if target_code and target_station:
            norm_target = _normalize(target_station)
            if target_code != train_dest and norm_target not in _normalize(train_name):
                is_relevant = False

        entry = {
            "train_number": t_info.get("number"),
            "route_name": train_name,
            "departure_time": dep_time,
            "platform": platform,
            "status": status_type,
            "delay_minutes": delay,
            "is_direct_target": is_relevant,
        }

        if status_type == "departed":
            departed.append(entry)
        else:
            upcoming.append(entry)

    # Filter to relevant direction if matches found, else fallback to all
    relevant_departed = [t for t in departed if t["is_direct_target"]] or departed
    relevant_upcoming = [t for t in upcoming if t["is_direct_target"]] or upcoming

    # Clean up internal flag
    for t in relevant_departed + relevant_upcoming:
        t.pop("is_direct_target", None)

    # Pick 2 recently departed + upcoming trains
    selected_trains = []
    if relevant_departed:
        selected_trains.extend(relevant_departed[-2:])
    selected_trains.extend(relevant_upcoming[:limit])

    route_result["live_trains"] = selected_trains
    return route_result