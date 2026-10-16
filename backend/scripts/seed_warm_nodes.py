"""Warm-node Overpass fetcher and road_edges SQL generator.

Usage:
  1. Optional one-shot fetch from Overpass API (saves raw JSON + CSV):
       python backend/scripts/seed_warm_nodes.py --fetch-overpass

  2. Generate reviewable SQL (`sql-schema/seed_warm_nodes_and_roads.sql`) from
     `sql-schema/warm_nodes.csv`:
       python backend/scripts/seed_warm_nodes.py --generate-sql

Design guarantees:
  - Never touches the live Supabase database directly; outputs a reviewable SQL file.
  - Refuses to include rows marked `example_template_replace_before_import`
    unless `--allow-examples` is explicitly passed.
  - Connects each warm node to its k=3 nearest nodes within R=3.0 km, and
    guarantees graph connectivity by linking to the single nearest hot node if
    no hot node was within the k-nearest set.
  - Also generates road_edges between nearby hot nodes (k=3 within 3.0 km) so
    station-to-station road hops (e.g. Kharghar <-> Belpada) exist in road_edges.
  - Inserts road edges in BOTH directions ((u, v) and (v, u)) with
    distance = round(haversine_km * 1.30, 2) and distance_source = 'estimated'.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = REPO_ROOT / "sql-schema" / "warm_nodes.csv"
RAW_JSON_PATH = REPO_ROOT / "sql-schema" / "overpass_warm_nodes_raw.json"
OUT_SQL_PATH = REPO_ROOT / "sql-schema" / "seed_warm_nodes_and_roads.sql"

CIRCUITY_FACTOR = 1.30
K_NEAREST = 3
MAX_RADIUS_KM = 3.0
MAX_OVERPASS_ROWS = 30

# Canonical 24 hot nodes from sql-schema/seed.sql
HOT_NODES = [
    {"name": "Vashi", "lat": 19.0632517, "lng": 72.9988553, "tier": "hot", "kind": "rail"},
    {"name": "Sanpada", "lat": 19.0659637, "lng": 73.0094849, "tier": "hot", "kind": "rail"},
    {"name": "Juinagar", "lat": 19.0562946, "lng": 73.0178235, "tier": "hot", "kind": "rail"},
    {"name": "Nerul", "lat": 19.0333801, "lng": 73.0183566, "tier": "hot", "kind": "rail"},
    {"name": "Seawoods-Darave", "lat": 19.0219794, "lng": 73.0193133, "tier": "hot", "kind": "rail"},
    {"name": "Belapur CBD", "lat": 19.0188208, "lng": 73.0388390, "tier": "hot", "kind": "rail"},
    {"name": "Sagar Sangam", "lat": 19.0106630, "lng": 73.0247210, "tier": "hot", "kind": "rail"},
    {"name": "Kharghar", "lat": 19.0263639, "lng": 73.0594488, "tier": "hot", "kind": "rail"},
    {"name": "Mansarovar", "lat": 19.0165576, "lng": 73.0806949, "tier": "hot", "kind": "rail"},
    {"name": "Khandeshwar", "lat": 19.0073656, "lng": 73.0952632, "tier": "hot", "kind": "rail"},
    {"name": "Panvel", "lat": 18.9911172, "lng": 73.1206460, "tier": "hot", "kind": "rail"},
    {"name": "Targhar", "lat": 18.9918840, "lng": 73.0370475, "tier": "hot", "kind": "rail"},
    {"name": "Bamandongri", "lat": 18.9751506, "lng": 73.0243313, "tier": "hot", "kind": "rail"},
    {"name": "Kharkopar", "lat": 18.9599051, "lng": 73.0141460, "tier": "hot", "kind": "rail"},
    {"name": "Belpada", "lat": 19.0254324, "lng": 73.0552703, "tier": "hot", "kind": "metro"},
    {"name": "Utsav Chowk", "lat": 19.0327270, "lng": 73.0590980, "tier": "hot", "kind": "metro"},
    {"name": "Kendriya Vihar", "lat": 19.0376857, "lng": 73.0641924, "tier": "hot", "kind": "metro"},
    {"name": "Kharghar Village", "lat": 19.0433150, "lng": 73.0744660, "tier": "hot", "kind": "metro"},
    {"name": "Central Park", "lat": 19.0536592, "lng": 73.0760829, "tier": "hot", "kind": "metro"},
    {"name": "Pethpada", "lat": 19.0640100, "lng": 73.0774620, "tier": "hot", "kind": "metro"},
    {"name": "Amandoot", "lat": 19.0737820, "lng": 73.0818660, "tier": "hot", "kind": "metro"},
    {"name": "Pethali-Taloja", "lat": 19.0746640, "lng": 73.0907640, "tier": "hot", "kind": "metro"},
    {"name": "Pendhar", "lat": 19.0719003, "lng": 73.0981910, "tier": "hot", "kind": "metro"},
    {"name": "RBI", "lat": 19.0217000, "lng": 73.0468000, "tier": "hot", "kind": "metro"},
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_overpass_once(timeout_sec: int = 15) -> None:
    """Run a single Overpass query within 1.5 km of the 14 rail stations."""
    rail_only = [n for n in HOT_NODES if n["kind"] == "rail"]
    coords_str = ",".join(f"{n['lat']},{n['lng']}" for n in rail_only)
    query = f"""[out:json][timeout:{timeout_sec}];
(
  node["highway"="bus_stop"]["name"](around:1500,{coords_str});
  node["amenity"="taxi"]["name"](around:1500,{coords_str});
  node["amenity"="taxi"]["taxi_vehicle"="auto_rickshaw"]["name"](around:1500,{coords_str});
);
out body;
"""
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
        headers={"User-Agent": "OptigoCollegeProject/1.0 (https://github.com/krs-kaustubh/optigo)"},
    )
    with urllib.request.urlopen(req, timeout=timeout_sec + 5) as resp:
        raw = resp.read().decode("utf-8")

    RAW_JSON_PATH.write_text(raw, encoding="utf-8")
    data = json.loads(raw)
    elements = data.get("elements", [])

    rows = []
    seen_names = {n["name"].lower() for n in HOT_NODES}
    for el in elements:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        kind = "auto_stand" if tags.get("amenity") == "taxi" else "bus_stop"
        confidence = "high" if tags.get("operator") or tags.get("public_transport") else "medium"
        rows.append({
            "name": name,
            "lat": f"{float(el['lat']):.7f}",
            "lng": f"{float(el['lon']):.7f}",
            "tier": "warm",
            "kind": kind,
            "source": "osm_overpass",
            "confidence": confidence,
            "osm_id": str(el.get("id", "")),
            "notes": "OpenStreetMap contributors (ODbL)",
        })
        if len(rows) >= MAX_OVERPASS_ROWS:
            break

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["name", "lat", "lng", "tier", "kind", "source", "confidence", "osm_id", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved raw response to {RAW_JSON_PATH} and {len(rows)} rows to {CSV_PATH}")


def load_warm_nodes_from_csv(allow_examples: bool = False) -> list[dict]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing {CSV_PATH}")
    warm = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = (row.get("source") or "").strip()
            if source == "example_template_replace_before_import" and not allow_examples:
                continue
            warm.append({
                "name": row["name"].strip(),
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
                "tier": (row.get("tier") or "warm").strip(),
                "kind": (row.get("kind") or "bus_stop").strip(),
                "source": source or "osm_overpass",
                "confidence": (row.get("confidence") or "medium").strip(),
                "osm_id": int(row["osm_id"]) if (row.get("osm_id") or "").strip().isdigit() else None,
            })
    return warm


def compute_road_edge_pairs(
    hot_nodes: list[dict],
    warm_nodes: list[dict],
    k: int = K_NEAREST,
    max_radius_km: float = MAX_RADIUS_KM,
) -> list[tuple[str, str, float]]:
    """Compute bidirectional road edges (u_name, v_name, road_distance_km).

    Rules (Trap a + Correction C):
    1. Each warm node connects to its k nearest nodes (hot or warm) within
       `max_radius_km` (straight-line haversine <= max_radius_km).
    2. Connectedness guarantee: if none of a warm node's selected neighbours is
       a hot node, also connect it to its single nearest hot node.
    3. Each hot node also connects to its k nearest hot nodes within
       `max_radius_km` so road legs can bridge nearby stations.
    4. Every undirected pair {u, v} produces BOTH directed edges (u, v) and (v, u)
       with distance = round(haversine_km * 1.30, 2).
    """
    all_nodes = hot_nodes + warm_nodes
    undirected: dict[tuple[str, str], float] = {}

    def add_pair(a: dict, b: dict, hav_km: float) -> None:
        u, v = (a["name"], b["name"]) if a["name"] < b["name"] else (b["name"], a["name"])
        road_km = max(0.1, round(hav_km * CIRCUITY_FACTOR, 2))
        undirected[(u, v)] = road_km

    # 1 & 2. Warm node connections
    for w in warm_nodes:
        dists = []
        for other in all_nodes:
            if other["name"] == w["name"]:
                continue
            d = haversine_km(w["lat"], w["lng"], other["lat"], other["lng"])
            dists.append((d, other))
        dists.sort(key=lambda x: x[0])

        chosen = [(d, n) for d, n in dists if d <= max_radius_km][:k]
        has_hot = any(n["tier"] == "hot" for _, n in chosen)
        if not has_hot:
            nearest_hot = min(
                ((haversine_km(w["lat"], w["lng"], h["lat"], h["lng"]), h) for h in hot_nodes),
                key=lambda x: x[0],
            )
            chosen.append(nearest_hot)

        for d, n in chosen:
            add_pair(w, n, d)

    # 3. Nearby hot-to-hot road connections
    for h in hot_nodes:
        dists = []
        for other in hot_nodes:
            if other["name"] == h["name"]:
                continue
            d = haversine_km(h["lat"], h["lng"], other["lat"], other["lng"])
            if d <= max_radius_km:
                dists.append((d, other))
        dists.sort(key=lambda x: x[0])
        for d, other in dists[:k]:
            add_pair(h, other, d)

    # 4. Expand into BOTH directions
    directed: list[tuple[str, str, float]] = []
    for (u, v), dist_km in sorted(undirected.items()):
        directed.append((u, v, dist_km))
        directed.append((v, u, dist_km))
    return directed


def sql_str(val: str) -> str:
    return "'" + val.replace("'", "''") + "'"


def generate_sql(allow_examples: bool = False) -> None:
    warm_nodes = load_warm_nodes_from_csv(allow_examples=allow_examples)
    directed_edges = compute_road_edge_pairs(HOT_NODES, warm_nodes)

    lines = [
        "-- ============================================================================",
        "-- Generated by backend/scripts/seed_warm_nodes.py",
        "-- Inserts curated warm nodes from sql-schema/warm_nodes.csv and bidirectional",
        "-- road_edges (distance = round(haversine * 1.30, 2), distance_source='estimated').",
        "-- Data attribution: OpenStreetMap contributors (ODbL) where source='osm_overpass'.",
        "-- ============================================================================",
        "",
        "BEGIN;",
        "",
    ]

    if warm_nodes:
        lines.append("-- 1. Warm Nodes")
        for w in warm_nodes:
            osm_val = str(w["osm_id"]) if w["osm_id"] is not None else "NULL"
            lines.append(
                "INSERT INTO nodes (name, location, type, tier, kind, source, confidence, osm_id) "
                f"VALUES ({sql_str(w['name'])}, ST_SetSRID(ST_MakePoint({w['lng']:.7f}, {w['lat']:.7f}), 4326), "
                f"{sql_str(w['kind'])}, {sql_str(w['tier'])}, {sql_str(w['kind'])}, "
                f"{sql_str(w['source'])}, {sql_str(w['confidence'])}, {osm_val}) "
                "ON CONFLICT DO NOTHING;"
            )
        lines.append("")
    else:
        lines.append(
            "-- No non-example warm nodes in warm_nodes.csv yet (only hot-to-hot road_edges emitted below)."
        )
        lines.append("")

    lines.append("-- 2. Bidirectional road_edges (k=3 within 3.0 km + connectedness guarantee)")
    for u_name, v_name, dist_km in directed_edges:
        lines.append(
            "INSERT INTO road_edges (from_node, to_node, distance, distance_source) VALUES ("
            f"(SELECT id FROM nodes WHERE name={sql_str(u_name)} LIMIT 1), "
            f"(SELECT id FROM nodes WHERE name={sql_str(v_name)} LIMIT 1), "
            f"{dist_km:.2f}, 'estimated') "
            "ON CONFLICT (from_node, to_node) DO UPDATE SET "
            "distance = EXCLUDED.distance, distance_source = EXCLUDED.distance_source;"
        )

    lines.extend(["", "COMMIT;", ""])
    OUT_SQL_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"Wrote {OUT_SQL_PATH} with {len(warm_nodes)} warm nodes and "
        f"{len(directed_edges)} directed road_edges."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Warm node Overpass fetcher & SQL seed generator")
    parser.add_argument("--fetch-overpass", action="store_true", help="Run one Overpass query and write CSV")
    parser.add_argument("--generate-sql", action="store_true", help="Generate seed_warm_nodes_and_roads.sql from CSV")
    parser.add_argument(
        "--allow-examples",
        action="store_true",
        help="Include example_template_replace_before_import rows when generating SQL",
    )
    args = parser.parse_args()

    if args.fetch_overpass:
        fetch_overpass_once()
    if args.generate_sql:
        generate_sql(allow_examples=args.allow_examples)
    if not args.fetch_overpass and not args.generate_sql:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
