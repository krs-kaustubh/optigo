import os
import networkx as nx
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

TRAIN_FARE_SLABS = [(10, 5), (20, 10), (25, 15), (30, 20), (float("inf"), 30)]
METRO_FARE_SLABS = [(2, 10), (4, 15), (6, 20), (8, 25), (10, 30), (float("inf"), 40)]


def fare_for_distance(km, mode):
    if mode == "walking":
        return 0
    slabs = METRO_FARE_SLABS if mode == "metro" else TRAIN_FARE_SLABS
    for limit, price in slabs:
        if km <= limit:
            return price
    return slabs[-1][1]


def fetch_nodes():
    # RPC needed — Supabase client can't unpack PostGIS GEOMETRY directly
    res = supabase.rpc("get_nodes_with_coords").execute()
    return {row["id"]: {"name": row["name"], "lat": row["lat"], "lng": row["lng"]} for row in res.data}


def fetch_edges():
    res = supabase.table("edges").select("*").execute()
    return [(e["from_node"], e["to_node"], e["mode"], e["distance"], e["time"], e["cost"]) for e in res.data]


def build_graph(weight="time"):
    NODES = fetch_nodes()
    EDGES = fetch_edges()
    G = nx.DiGraph()
    for nid, attrs in NODES.items():
        G.add_node(nid, **attrs)
    for u, v, mode, dist, time, cost in EDGES:
        w = {"distance": dist, "time": time, "cost": cost}[weight]
        G.add_edge(u, v, mode=mode, distance=dist, time=time, cost=cost, weight=w)
        if mode in ("bus", "cab", "train", "metro", "walking"):
            G.add_edge(v, u, mode=mode, distance=dist, time=time, cost=cost, weight=w)
    return G, NODES


def shortest_path(source: int, target: int, weight: str = "time"):
    G, NODES = build_graph(weight)
    path = nx.shortest_path(G, source, target, weight="weight")
    total = {"distance": 0, "time": 0, "cost": 0, "real_fare": 0}
    edges_used = []
    mode_distances = {}

    for u, v in zip(path, path[1:]):
        edge = G[u][v]
        total["distance"] += edge["distance"]
        total["time"] += edge["time"]
        total["cost"] += edge["cost"]
        mode_distances[edge["mode"]] = mode_distances.get(edge["mode"], 0) + edge["distance"]
        edges_used.append({"from": NODES[u]["name"], "to": NODES[v]["name"], "mode": edge["mode"]})

    total["real_fare"] = sum(fare_for_distance(km, mode) for mode, km in mode_distances.items())

    return {"path": [NODES[n]["name"] for n in path], "edges": edges_used, "totals": total}


def compare_routes(source: int, target: int):
    # "cost" isn't searched directly — real_fare is a per-mode cumulative slab,
    # not a per-edge additive weight, so Dijkstra can't optimize it exactly.
    # Instead: compute the time- and distance-optimal paths, then report
    # whichever of those two actually has the lower real_fare as "cost".
    candidates = {}
    for weight in ["time", "distance"]:
        try:
            candidates[weight] = shortest_path(source, target, weight)
        except Exception:
            pass

    if not candidates:
        return []

    results = []
    for weight, r in candidates.items():
        r = dict(r)
        r["optimized_for"] = weight
        results.append(r)

    cheapest = min(candidates.values(), key=lambda r: r["totals"]["real_fare"])
    cost_result = dict(cheapest)
    cost_result["optimized_for"] = "cost"
    results.append(cost_result)

    return results