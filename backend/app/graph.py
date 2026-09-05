import os
import networkx as nx
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


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
        if mode in ("bus", "cab", "train", "metro"):
            G.add_edge(v, u, mode=mode, distance=dist, time=time, cost=cost, weight=w)
    return G, NODES


def shortest_path(source: int, target: int, weight: str = "time"):
    G, NODES = build_graph(weight)
    path = nx.shortest_path(G, source, target, weight="weight")
    total = {"distance": 0, "time": 0, "cost": 0}
    edges_used = []
    for u, v in zip(path, path[1:]):
        edge = G[u][v]
        total["distance"] += edge["distance"]
        total["time"] += edge["time"]
        total["cost"] += edge["cost"]
        edges_used.append({"from": NODES[u]["name"], "to": NODES[v]["name"], "mode": edge["mode"]})
    return {"path": [NODES[n]["name"] for n in path], "edges": edges_used, "totals": total}


def compare_routes(source: int, target: int):
    results = []
    for weight in ["time", "cost", "distance"]:
        try:
            r = shortest_path(source, target, weight)
            r["optimized_for"] = weight
            results.append(r)
        except Exception:
            pass
    return results