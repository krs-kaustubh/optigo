import networkx as nx

# Real corridor: New Panvel <-> Seawoods
# Two entry points to rail line: Khandeshwar or Panvel (terminal)
# Local trains from Panvel run same track till Seawoods-Darave-Karawe

NODES = {
    1: {"name": "New Panvel (Origin - Zudio/Prajapati Oval)", "lat": 19.0330, "lng": 73.1050},
    2: {"name": "Khandeshwar Station", "lat": 19.0130, "lng": 73.1160},
    3: {"name": "Panvel Station (Terminal)", "lat": 18.9894, "lng": 73.1175},
    4: {"name": "Mansarowar Station", "lat": 19.0230, "lng": 73.0980},
    5: {"name": "Kharghar Station", "lat": 19.0470, "lng": 73.0660},
    6: {"name": "Belapur CBD Station", "lat": 19.0233, "lng": 73.0353},
    7: {"name": "Seawoods-Darave-Karawe Station", "lat": 19.0110, "lng": 73.0180},
}

# (from, to, mode, distance_km, time_min, cost_rs)
# NOTE: distances are placeholder estimates - refine later
EDGES = [
    # Bus legs: New Panvel -> either rail entry point
    (1, 2, "bus", 4.0, 20, 18),   # New Panvel -> Khandeshwar
    (1, 3, "bus", 5.0, 20, 18),   # New Panvel -> Panvel Station

    # Train legs (same line, both entry points feed into it)
    # Flat fare: Rs 5 covers the ENTIRE train journey regardless of stops.
    # Modeled as: first hop carries the full fare, rest are free (Rs 0),
    # so total cost stays flat at 5 no matter how many stations you pass.
    (3, 2, "train", 3.0, 5, 5),   # Panvel -> Khandeshwar (fare charged here)
    (2, 4, "train", 3.0, 5, 0),   # Khandeshwar -> Mansarowar
    (4, 5, "train", 3.5, 6, 0),   # Mansarowar -> Kharghar
    (5, 6, "train", 4.0, 7, 0),   # Kharghar -> Belapur CBD
    (6, 7, "train", 3.0, 5, 0),   # Belapur CBD -> Seawoods

    # Direct cab (mock, Ola/Uber/Rapido)
    (1, 7, "cab", 14.0, 35, 250),
]


def build_graph(weight="time"):
    G = nx.DiGraph()
    for nid, attrs in NODES.items():
        G.add_node(nid, **attrs)
    for u, v, mode, dist, time, cost in EDGES:
        w = {"distance": dist, "time": time, "cost": cost}[weight]
        G.add_edge(u, v, mode=mode, distance=dist, time=time, cost=cost, weight=w)
        # bus/cab bidirectional; train direction fixed (Panvel-side -> Seawoods-side)
        if mode in ("bus", "cab"):
            G.add_edge(v, u, mode=mode, distance=dist, time=time, cost=cost, weight=w)
    return G


def shortest_path(source: int, target: int, weight: str = "time"):
    G = build_graph(weight)
    path = nx.shortest_path(G, source, target, weight="weight")
    total = {"distance": 0, "time": 0, "cost": 0}
    edges_used = []
    for u, v in zip(path, path[1:]):
        edge = G[u][v]
        total["distance"] += edge["distance"]
        total["time"] += edge["time"]
        total["cost"] += edge["cost"]
        edges_used.append({"from": NODES[u]["name"], "to": NODES[v]["name"], "mode": edge["mode"]})
    return {
        "path": [NODES[n]["name"] for n in path],
        "edges": edges_used,
        "totals": total,
    }


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