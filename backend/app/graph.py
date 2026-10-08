import os
import httpx
import networkx as nx
import math
from supabase import ClientOptions, create_client
from dotenv import load_dotenv

load_dotenv()

# Supabase closes idle connections server-side; a pooled connection reused after
# that raises httpx.RemoteProtocolError("Server disconnected"). Keep idle
# connections briefly so they are dropped before Supabase drops them, and
# retry once on a transport error as a second line of defence.
KEEPALIVE_EXPIRY_SECONDS = 15
TRANSPORT_ERRORS = (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError, httpx.ConnectError)

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
    options=ClientOptions(
        httpx_client=httpx.Client(
            timeout=httpx.Timeout(20.0),
            limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=KEEPALIVE_EXPIRY_SECONDS),
        ),
    ),
)


class UpstreamError(Exception):
    """Supabase could not be reached or answered with a transport error."""


def _with_reconnect(call):
    """Run `call()`; on a stale-connection transport error retry once, then
    surface UpstreamError so main.py can answer 502 instead of a raw 500."""
    for attempt in (1, 2):
        try:
            return call()
        except TRANSPORT_ERRORS as exc:
            if attempt == 2:
                raise UpstreamError(f"Supabase unreachable: {type(exc).__name__}: {exc}") from exc

WEIGHTS = ("time", "distance", "cost")


class RoutingError(Exception):
    """Base class for errors a caller can act on (bad input, no route)."""


class InvalidWeight(RoutingError):
    def __init__(self, weight):
        super().__init__(f"weight must be one of {', '.join(WEIGHTS)}; got {weight!r}")


class UnknownNode(RoutingError):
    def __init__(self, node_id):
        self.node_id = node_id
        super().__init__(f"unknown node id {node_id}")


class SameNode(RoutingError):
    def __init__(self, node_id):
        super().__init__(f"source and target are the same node ({node_id})")


class NoPath(RoutingError):
    def __init__(self, source, target):
        super().__init__(f"no route between node {source} and node {target}")


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
    res = _with_reconnect(lambda: supabase.rpc("get_nodes_with_coords").execute())
    return {
        row["id"]: {"name": row["name"], "lat": row["lat"], "lng": row["lng"], "type": row.get("type")}
        for row in res.data
    }


def list_nodes():
    """All stations as a list sorted by id — for the frontend's pickers."""
    return [{"id": nid, **attrs} for nid, attrs in sorted(fetch_nodes().items())]


def fetch_edges():
    res = _with_reconnect(lambda: supabase.table("edges").select("*").execute())
    return [(e["from_node"], e["to_node"], e["mode"], e["distance"], e["time"], e["cost"]) for e in res.data]


def build_graph(weight="time"):
    """One Supabase round trip for nodes + one for edges -> (DiGraph, NODES).

    Every edge carries distance/time/cost, so any of them can be used directly
    as a Dijkstra weight attribute. `weight` is kept for backwards
    compatibility and mirrored into a `weight` attribute.
    """
    if weight not in WEIGHTS:
        raise InvalidWeight(weight)
    NODES = fetch_nodes()
    EDGES = fetch_edges()
    G = nx.DiGraph()
    for nid, attrs in NODES.items():
        G.add_node(nid, **attrs)
    for u, v, mode, dist, time, cost in EDGES:
        attrs = dict(mode=mode, distance=dist, time=time, cost=cost)
        attrs["weight"] = attrs[weight]
        attrs["fare_weight"] = fare_for_distance(dist, mode)
        G.add_edge(u, v, **attrs)
        if mode in ("bus", "cab", "train", "metro", "walking"):
            G.add_edge(v, u, **attrs)
    return G, NODES


def _validate_endpoints(G, source: int, target: int):
    for node in (source, target):
        if node not in G:
            raise UnknownNode(node)
    if source == target:
        raise SameNode(source)


def _find_path(G, source: int, target: int, weight_attr: str):
    _validate_endpoints(G, source, target)
    try:
        return nx.shortest_path(G, source, target, weight=weight_attr)
    except nx.NetworkXNoPath:
        raise NoPath(source, target) from None


def _round(x):
    return round(x, 2) if isinstance(x, float) else x


def _route_result(G, NODES, path):
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
    total = {k: _round(v) for k, v in total.items()}

    return {"path": [NODES[n]["name"] for n in path], "edges": edges_used, "totals": total}


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _resolve_endpoint(G, NODES, endpoint_arg, custom_id, custom_name):
    if isinstance(endpoint_arg, str) and "," in endpoint_arg:
        try:
            lat, lng = map(float, endpoint_arg.split(","))
            if custom_id not in NODES:
                NODES[custom_id] = {"name": custom_name, "lat": lat, "lng": lng, "type": "custom"}
                G.add_node(custom_id, **NODES[custom_id])
                
                distances = []
                for nid, attrs in NODES.items():
                    if nid == custom_id or attrs.get("type") == "custom": continue
                    d = haversine(lat, lng, attrs["lat"], attrs["lng"])
                    distances.append((d, nid))
                distances.sort()
                
                for d, nid in distances[:3]:
                    time_mins = (d / 5.0) * 60.0
                    attrs = dict(mode="walking", distance=d, time=time_mins, cost=0, weight=time_mins, fare_weight=0)
                    G.add_edge(custom_id, nid, **attrs)
                    G.add_edge(nid, custom_id, **attrs)
            return custom_id
        except ValueError:
            pass
    try:
        return int(endpoint_arg)
    except (ValueError, TypeError):
        return endpoint_arg

def shortest_path(source, target, weight: str = "time", graph=None):
    """One Dijkstra run on `weight`. Pass `graph=(G, NODES)` to reuse a built graph."""
    if weight not in WEIGHTS:
        raise InvalidWeight(weight)
    G, NODES = graph or build_graph(weight)
    source_id = _resolve_endpoint(G, NODES, source, "custom_source", "Origin")
    target_id = _resolve_endpoint(G, NODES, target, "custom_target", "Destination")
    path = _find_path(G, source_id, target_id, weight)
    return _route_result(G, NODES, path)


def shortest_path_cost_approx(source, target, graph=None):
    """Approximate cost search: uses per-edge fare (fare_for_distance applied
    per-edge, not cumulative per-mode) as weight. Not exact — real_fare is a
    per-mode cumulative slab, not additive — but finds low-fare paths that
    time/distance optimal search can miss (e.g. routes using cheap walking
    edges or short train hops)."""
    G, NODES = graph or build_graph()
    source_id = _resolve_endpoint(G, NODES, source, "custom_source", "Origin")
    target_id = _resolve_endpoint(G, NODES, target, "custom_target", "Destination")
    path = _find_path(G, source_id, target_id, "fare_weight")
    return _route_result(G, NODES, path)


def compare_routes(source, target):
    """Three candidates tagged optimized_for = time / distance / cost.

    Raises RoutingError (UnknownNode, SameNode, NoPath) for bad input, and
    lets data-source errors propagate; it never returns an empty list.
    """
    graph = build_graph()  # one fetch, shared by all three searches
    candidates = {
        "time": shortest_path(source, target, "time", graph=graph),
        "distance": shortest_path(source, target, "distance", graph=graph),
        "fare_approx": shortest_path_cost_approx(source, target, graph=graph),
    }

    results = []
    for weight, r in candidates.items():
        if weight == "fare_approx":
            continue
        r = dict(r)
        r["optimized_for"] = weight
        results.append(r)

    cheapest = min(candidates.values(), key=lambda r: r["totals"]["real_fare"])
    cost_result = dict(cheapest)
    cost_result["optimized_for"] = "cost"
    results.append(cost_result)

    return results


if __name__ == "__main__":
    from pprint import pprint

    BELAPUR_CBD = 6
    PENDHAR = 23
    KHARKOPAR = 14

    print("=== Belapur CBD -> Pendhar ===")
    pprint(compare_routes(BELAPUR_CBD, PENDHAR))

    print("\n=== Belapur CBD -> Kharkopar ===")
    pprint(compare_routes(BELAPUR_CBD, KHARKOPAR))