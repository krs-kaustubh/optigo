import os
import requests
from dotenv import load_dotenv

load_dotenv()

RAILRADAR_BASE = "https://api.railradar.in/v1"
RAILRADAR_KEY = os.environ["RAILRADAR_API_KEY"]  # add to .env


def get_local_trains(city: str = "Mumbai"):
    """Suburban local trains for a metro city (Mumbai/Kolkata/Chennai/Hyderabad)."""
    resp = requests.get(
        f"{RAILRADAR_BASE}/lookup/trains/local",
        params={"city": city},
        headers={"Authorization": f"Bearer {RAILRADAR_KEY}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_train_live(train_number):
    """Live status for a single train: status + delayMinutes + current halt."""
    resp = requests.get(
        f"{RAILRADAR_BASE}/trains/{train_number}/live",
        headers={"Authorization": f"Bearer {RAILRADAR_KEY}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _normalize(s: str) -> str:
    return "".join(ch.lower() for ch in s if ch.isalnum())


def find_relevant_trains(station_names, all_trains, limit=3):
    """Match local-train route names against path station names via
    normalized (alnum-only) substring match. `all_trains` is the raw
    get_local_trains() response: {"success", "data": {train_number: route_name}, "meta"}.
    Returns up to `limit` matches as (train_number, route_name) tuples."""
    normalized_stations = [_normalize(s) for s in station_names]
    trains_data = all_trains.get("data", {}) if isinstance(all_trains, dict) else {}
    matches = []
    for train_number, route_name in trains_data.items():
        norm_route = _normalize(route_name)
        if any(st in norm_route for st in normalized_stations):
            matches.append((train_number, route_name))
        if len(matches) >= limit:
            break
    return matches


def annotate_route_with_live_status(route_result, limit=3):
    """Attach live_trains: [{train_number, route_name, status, delay_minutes}]
    to a route dict. Best-effort: swallows per-train fetch errors."""
    station_names = route_result.get("path", [])
    try:
        all_trains = get_local_trains("Mumbai")
    except Exception:
        route_result["live_trains"] = []
        return route_result

    matches = find_relevant_trains(station_names, all_trains, limit=limit)
    live_trains = []
    for train_number, route_name in matches:
        try:
            live = get_train_live(train_number)
            live_data = live.get("data", {}) if isinstance(live, dict) else {}
            live_trains.append({
                "train_number": train_number,
                "route_name": route_name,
                "status": live_data.get("status"),
                "delay_minutes": live_data.get("delayMinutes"),
            })
        except Exception:
            continue

    route_result["live_trains"] = live_trains
    return route_result


if __name__ == "__main__":
    from pprint import pprint
    pprint(get_local_trains("Mumbai"))