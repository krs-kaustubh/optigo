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

from app.cabs import (
    AUTO_PER_KM_RATE_INR,
    URBAN_SPEED_KMH,
    get_all_cab_estimates,
    metered_auto_fare,
)

WEIGHTS = ("time", "distance", "cost")
ROAD_WEIGHTS = ("time", "distance", "cost", "convenient")

# ----------------------------------------------------------------------------
# Road & walking routing constants
# ----------------------------------------------------------------------------
WALK_SPEED_KMH = 5.0                 # Walking speed (km/h) -> 12 min/km
MAX_WALK_EDGE_KM = 1.0               # Walking allowed only on road edges <= 1.0 km
MAX_TOTAL_WALK_KM = 1.5              # Maximum cumulative walking distance per route (km)
MAX_WALK_CAP_ITERATIONS = 5          # Max re-runs removing longest walking edge when cap exceeded
CAB_PICKUP_WAIT_MIN = 4.0            # Added once per grouped cab leg (see 3-5 min eta_minutes in cabs.py)

# ----------------------------------------------------------------------------
# "Most convenient" scoring constants (in equivalent minutes of perceived effort)
# Formula:
#   score = total_time_min (including CAB_PICKUP_WAIT_MIN once per cab leg)
#         + (num_transfers * TRANSFER_PENALTY_MIN)
#         + (num_warm_boardings * WARM_NODE_BOARDING_PENALTY_MIN)
#         + (walk_time_min * (WALK_PENALTY_MULTIPLIER - 1.0))
# ----------------------------------------------------------------------------
TRANSFER_PENALTY_MIN = 8.0           # Penalty per mode change (e.g. cab -> train, train -> metro)
WARM_NODE_BOARDING_PENALTY_MIN = 5.0 # Extra uncertainty penalty when boarding at a warm node
WALK_PENALTY_MULTIPLIER = 2.0        # 1 min of walking is weighted as 2 min of perceived effort
CONVENIENT_K_PATHS = 10              # Number of shortest simple paths (by time) to score


class RoutingError(Exception):
    """Base class for errors a caller can act on (bad input, no route)."""


class InvalidWeight(RoutingError):
    def __init__(self, weight, allowed=WEIGHTS):
        super().__init__(f"weight must be one of {', '.join(allowed)}; got {weight!r}")


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
    if mode == "cab":
        return metered_auto_fare(km)
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


def fetch_all_nodes():
    """Opt-in node fetcher (`road=True` or `include_warm=True`) calling the extended RPC."""
    res = _with_reconnect(lambda: supabase.rpc("get_all_nodes_with_coords").execute())
    return {
        row["id"]: {
            "name": row["name"],
            "lat": row["lat"],
            "lng": row["lng"],
            "type": row.get("type"),
            "tier": row.get("tier", "hot"),
            "kind": row.get("kind", row.get("type", "rail")),
            "source": row.get("source", "seed"),
            "confidence": row.get("confidence", "high"),
        }
        for row in res.data
    }


def list_nodes(include_warm: bool = False):
    """All stations as a list sorted by id — for the frontend's pickers.
    When include_warm=False (default), calls fetch_nodes() and returns only hot stations."""
    nodes = fetch_all_nodes() if include_warm else fetch_nodes()
    return [{"id": nid, **attrs} for nid, attrs in sorted(nodes.items())]


def fetch_edges():
    res = _with_reconnect(lambda: supabase.table("edges").select("*").execute())
    return [(e["from_node"], e["to_node"], e["mode"], e["distance"], e["time"], e["cost"]) for e in res.data]


def fetch_railway_edges():
    res = _with_reconnect(lambda: supabase.table("railway_edges").select("*").execute())
    return [(e["from_node"], e["to_node"], e["mode"], e["distance"], e["time"], e["cost"]) for e in res.data]


def fetch_road_edges():
    res = _with_reconnect(lambda: supabase.table("road_edges").select("*").execute())
    return [
        (e["from_node"], e["to_node"], e["distance"], e.get("distance_source", "estimated"))
        for e in res.data
    ]


def _make_road_edge_attrs(dist: float, distance_source: str = "estimated", force_cab: bool = False) -> dict:
    """Build per-edge attributes for a road edge of `dist` km.
    Walking is allowed only when `dist <= MAX_WALK_EDGE_KM` (1.0 km) and not forced to cab."""
    if not force_cab and dist <= MAX_WALK_EDGE_KM:
        mode = "walking"
        time_min = round((dist / WALK_SPEED_KMH) * 60.0, 2)
        marginal_cost = 0.0
    else:
        mode = "cab"
        time_min = round((dist / URBAN_SPEED_KMH) * 60.0, 2)
        marginal_cost = round(dist * AUTO_PER_KM_RATE_INR, 2)

    return {
        "mode": mode,
        "distance": dist,
        "time": time_min,
        "cost": marginal_cost,
        "weight": time_min,
        "fare_weight": marginal_cost,
        "is_road": True,
        "distance_source": distance_source or "estimated",
    }


def build_graph(weight="time", road: bool = False):
    """Build (DiGraph, NODES).

    When `road=False` (default): fetches `get_nodes_with_coords` + `edges` exactly as before.
    When `road=True`: fetches `get_all_nodes_with_coords` + `railway_edges` + `road_edges`
    (one fetch per table).
    """
    allowed = ROAD_WEIGHTS if road else WEIGHTS
    if weight not in allowed:
        raise InvalidWeight(weight, allowed=allowed)

    if not road:
        NODES = fetch_nodes()
        EDGES = fetch_edges()
        G = nx.DiGraph(road=False)
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

    # Opt-in road=True path: one fetch per table
    NODES = fetch_all_nodes()
    RAIL_EDGES = fetch_railway_edges()
    ROAD_EDGES = fetch_road_edges()

    G = nx.DiGraph(road=True)
    for nid, attrs in NODES.items():
        G.add_node(nid, **attrs)

    weight_key = "time" if weight in ("cost", "convenient") else weight
    for u, v, mode, dist, time, cost in RAIL_EDGES:
        attrs = dict(mode=mode, distance=dist, time=time, cost=cost, is_road=False)
        attrs["weight"] = attrs[weight_key]
        attrs["fare_weight"] = fare_for_distance(dist, mode)
        G.add_edge(u, v, **attrs)
        if mode in ("bus", "cab", "train", "metro", "walking"):
            G.add_edge(v, u, **attrs)

    for item in ROAD_EDGES:
        if len(item) >= 4:
            u, v, dist, dist_source = item[0], item[1], float(item[2]), item[3]
        else:
            u, v, dist, dist_source = item[0], item[1], float(item[2]), "estimated"

        if u not in G or v not in G:
            continue

        for src, dst in ((u, v), (v, u)):
            # Do not overwrite any existing non-road edge (train, metro, or railway walking transfer)
            if G.has_edge(src, dst) and not G[src][dst].get("is_road", False):
                continue
            attrs = _make_road_edge_attrs(dist, dist_source)
            attrs["weight"] = attrs[weight_key]
            G.add_edge(src, dst, **attrs)

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


def _path_walk_distance(G, path) -> float:
    return sum(
        G[u][v]["distance"]
        for u, v in zip(path, path[1:])
        if G[u][v].get("mode") == "walking"
    )


def _rail_only_best_path(G, source: int, target: int, weight_attr: str = "time"):
    """Return shortest path on `G` with all `is_road=True` edges removed, or None."""
    G_rail = nx.DiGraph()
    G_rail.add_nodes_from(G.nodes(data=True))
    for u, v, data in G.edges(data=True):
        if not data.get("is_road", False):
            G_rail.add_edge(u, v, **data)
    try:
        return nx.shortest_path(G_rail, source, target, weight=weight_attr)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def _find_path_with_walk_cap(G, source: int, target: int, weight_attr: str):
    """Run Dijkstra on `weight_attr`; if total walking exceeds MAX_TOTAL_WALK_KM,
    remove the longest walking edge in that path and re-run (at most 5 times)."""
    path = _find_path(G, source, target, weight_attr)
    if not G.graph.get("road") or _path_walk_distance(G, path) <= MAX_TOTAL_WALK_KM:
        return G, path

    G_work = G.copy()
    for _ in range(MAX_WALK_CAP_ITERATIONS):
        if _path_walk_distance(G_work, path) <= MAX_TOTAL_WALK_KM:
            break
        walk_edges = [
            (G_work[u][v]["distance"], u, v)
            for u, v in zip(path, path[1:])
            if G_work[u][v].get("mode") == "walking"
        ]
        if not walk_edges:
            break
        _, max_u, max_v = max(walk_edges, key=lambda x: x[0])
        saved = dict(G_work[max_u][max_v])
        G_work.remove_edge(max_u, max_v)
        try:
            path = nx.shortest_path(G_work, source, target, weight=weight_attr)
        except nx.NetworkXNoPath:
            if saved.get("is_road"):
                # Bridge road edge: upgrade from walking to cab so the graph stays connected
                cab_attrs = _make_road_edge_attrs(
                    saved["distance"], saved.get("distance_source", "estimated"), force_cab=True
                )
                G_work.add_edge(max_u, max_v, **cab_attrs)
                try:
                    path = nx.shortest_path(G_work, source, target, weight=weight_attr)
                except nx.NetworkXNoPath:
                    G_work.add_edge(max_u, max_v, **saved)
                    break
            else:
                G_work.add_edge(max_u, max_v, **saved)
                break

    return G_work, path


def _round(x):
    return round(x, 2) if isinstance(x, float) else x


def _path_total_time_with_cab_wait(G, path) -> float:
    """Total travel time for `path`, adding CAB_PICKUP_WAIT_MIN once per grouped cab leg."""
    total_time = 0.0
    prev_mode = None
    for u, v in zip(path, path[1:]):
        edge = G[u][v]
        mode = edge["mode"]
        total_time += edge["time"]
        if mode == "cab" and prev_mode != "cab":
            total_time += CAB_PICKUP_WAIT_MIN
        prev_mode = mode
    return _round(total_time)


def _convenience_score(G, NODES, path) -> float:
    """Compute documented convenience score (lower is more convenient):
    time (including CAB_PICKUP_WAIT_MIN once per cab leg) + transfer penalty
    + warm-node boarding penalty + extra walking penalty."""
    total_time = 0.0
    walk_time = 0.0
    transfers = 0
    warm_boardings = 0
    prev_mode = None

    for idx, (u, v) in enumerate(zip(path, path[1:])):
        edge = G[u][v]
        mode = edge["mode"]
        total_time += edge["time"]
        if mode == "cab" and prev_mode != "cab":
            total_time += CAB_PICKUP_WAIT_MIN
        if mode == "walking":
            walk_time += edge["time"]

        if idx == 0:
            if NODES.get(u, {}).get("tier") == "warm":
                warm_boardings += 1
        elif mode != prev_mode:
            transfers += 1
            if NODES.get(u, {}).get("tier") == "warm":
                warm_boardings += 1

        prev_mode = mode

    score = (
        total_time
        + (transfers * TRANSFER_PENALTY_MIN)
        + (warm_boardings * WARM_NODE_BOARDING_PENALTY_MIN)
        + (walk_time * (WALK_PENALTY_MULTIPLIER - 1.0))
    )
    return _round(score)


def _route_result(G, NODES, path, road: bool = False):
    if not road and not G.graph.get("road"):
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

    # Opt-in road=True path:
    # - Group consecutive road edges of the same mode into one leg.
    # - Price each contiguous train run and each contiguous metro run separately.
    # - Add CAB_PICKUP_WAIT_MIN once per grouped cab leg, and price cab legs once via cabs.py.
    total = {"distance": 0.0, "time": 0.0, "cost": 0.0, "real_fare": 0.0}
    edges_used = []
    road_legs = []
    rail_metro_fare = 0.0
    road_real_fare = 0.0

    hops = list(zip(path, path[1:]))
    i = 0
    while i < len(hops):
        u, v = hops[i]
        edge = G[u][v]
        is_road = bool(edge.get("is_road") or edge["mode"] == "cab")

        if not is_road:
            # Group contiguous run of the same non-road mode to price each contiguous
            # train or metro run separately.
            run_mode = edge["mode"]
            run_dist = 0.0
            j = i
            while j < len(hops):
                nu, nv = hops[j]
                nedge = G[nu][nv]
                n_is_road = bool(nedge.get("is_road") or nedge["mode"] == "cab")
                if not n_is_road and nedge["mode"] == run_mode:
                    total["distance"] += nedge["distance"]
                    total["time"] += nedge["time"]
                    total["cost"] += nedge["cost"]
                    run_dist += nedge["distance"]
                    edges_used.append({"from": NODES[nu]["name"], "to": NODES[nv]["name"], "mode": run_mode})
                    j += 1
                else:
                    break
            if run_mode in ("train", "metro"):
                rail_metro_fare += fare_for_distance(run_dist, run_mode)
            i = j
            continue

        # Group consecutive road edges with the same mode into one contiguous road leg
        leg_mode = edge["mode"]
        seg_nodes = [u, v]
        seg_edges = [edge]
        j = i + 1
        while j < len(hops):
            nu, nv = hops[j]
            nedge = G[nu][nv]
            n_is_road = bool(nedge.get("is_road") or nedge["mode"] == "cab")
            if n_is_road and nedge["mode"] == leg_mode:
                seg_nodes.append(nv)
                seg_edges.append(nedge)
                j += 1
            else:
                break

        start_id, end_id = seg_nodes[0], seg_nodes[-1]
        leg_dist = _round(sum(e["distance"] for e in seg_edges))
        raw_leg_time = sum(e["time"] for e in seg_edges)

        if leg_mode == "cab":
            leg_time = _round(raw_leg_time + CAB_PICKUP_WAIT_MIN)
            leg_fare = _round(metered_auto_fare(leg_dist))
            cab_bundle = get_all_cab_estimates(
                pickup_lat=NODES[start_id]["lat"],
                pickup_lng=NODES[start_id]["lng"],
                dropoff_lat=NODES[end_id]["lat"],
                dropoff_lng=NODES[end_id]["lng"],
                pickup_name=NODES[start_id]["name"],
                dropoff_name=NODES[end_id]["name"],
                road_km_override=leg_dist,
            )
            leg_entry = {
                "from": NODES[start_id]["name"],
                "to": NODES[end_id]["name"],
                "mode": "cab",
                "distance": leg_dist,
                "time": leg_time,
                "cost": leg_fare,
                "distance_source": "estimated",
                "time_source": "estimated",
                "fare_source": "estimated",
                "cab_estimates": cab_bundle["estimates"],
            }
        else:
            leg_time = _round(raw_leg_time)
            leg_fare = 0
            leg_entry = {
                "from": NODES[start_id]["name"],
                "to": NODES[end_id]["name"],
                "mode": "walking",
                "distance": leg_dist,
                "time": leg_time,
                "cost": 0,
                "distance_source": "estimated",
                "time_source": "estimated",
                "fare_source": "estimated",
            }

        if len(seg_nodes) > 2:
            leg_entry["via"] = [NODES[nid]["name"] for nid in seg_nodes[1:-1]]

        edges_used.append(leg_entry)
        road_legs.append(leg_entry)

        total["distance"] += leg_dist
        total["time"] += leg_time
        total["cost"] += leg_fare
        road_real_fare += leg_fare
        i = j

    total["real_fare"] = rail_metro_fare + road_real_fare
    total = {k: _round(v) for k, v in total.items()}

    result = {
        "path": [NODES[n]["name"] for n in path],
        "edges": edges_used,
        "road_legs": road_legs,
        "totals": total,
    }
    if _path_walk_distance(G, path) > MAX_TOTAL_WALK_KM:
        result["warnings"] = ["walking_cap_exceeded"]
    return result


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
                    if nid == custom_id or attrs.get("type") == "custom":
                        continue
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


def _candidate_paths_for_scoring(G, source_id: int, target_id: int):
    """Collect up to CONVENIENT_K_PATHS simple paths ordered by raw edge time,
    plus the best rail-only path (with all road edges removed) if one exists."""
    try:
        gen = nx.shortest_simple_paths(G, source_id, target_id, weight="time")
        raw_paths = []
        for p in gen:
            raw_paths.append(p)
            if len(raw_paths) >= CONVENIENT_K_PATHS:
                break
    except nx.NetworkXNoPath:
        raise NoPath(source_id, target_id) from None

    if not raw_paths:
        raise NoPath(source_id, target_id)

    rail_path = _rail_only_best_path(G, source_id, target_id, "time")
    if rail_path is not None and rail_path not in raw_paths:
        raw_paths.append(rail_path)

    return [p for p in raw_paths if _path_walk_distance(G, p) <= MAX_TOTAL_WALK_KM]


def shortest_path(source, target, weight: str = "time", graph=None, road: bool = False):
    """One Dijkstra run on `weight`. Pass `graph=(G, NODES)` to reuse a built graph."""
    is_road = road or (graph is not None and bool(graph[0].graph.get("road")))
    allowed = ROAD_WEIGHTS if is_road else WEIGHTS
    if weight not in allowed:
        raise InvalidWeight(weight, allowed=allowed)

    G, NODES = graph or build_graph(weight, road=is_road)
    if is_road and weight == "convenient":
        return shortest_path_convenient(source, target, graph=(G, NODES))
    if is_road and weight == "cost":
        return shortest_path_cost_approx(source, target, graph=(G, NODES), road=True)

    source_id = _resolve_endpoint(G, NODES, source, "custom_source", "Origin")
    target_id = _resolve_endpoint(G, NODES, target, "custom_target", "Destination")

    if is_road and weight == "time":
        _validate_endpoints(G, source_id, target_id)
        valid_paths = _candidate_paths_for_scoring(G, source_id, target_id)
        if valid_paths:
            best_path = min(valid_paths, key=lambda p: _path_total_time_with_cab_wait(G, p))
            return _route_result(G, NODES, best_path, road=True)

    G_used, path = _find_path_with_walk_cap(G, source_id, target_id, weight)
    return _route_result(G_used, NODES, path, road=is_road)


def shortest_path_cost_approx(source, target, graph=None, road: bool = False):
    """Approximate cost search: uses per-edge marginal fare (`fare_weight`) in
    Dijkstra, applies the walking cap when `road=True`, and then groups/prices
    legs via `_route_result`."""
    is_road = road or (graph is not None and bool(graph[0].graph.get("road")))
    G, NODES = graph or build_graph(road=is_road)
    source_id = _resolve_endpoint(G, NODES, source, "custom_source", "Origin")
    target_id = _resolve_endpoint(G, NODES, target, "custom_target", "Destination")
    G_used, path = _find_path_with_walk_cap(G, source_id, target_id, "fare_weight")
    return _route_result(G_used, NODES, path, road=is_road)


def shortest_path_convenient(source, target, graph=None):
    """Generate up to CONVENIENT_K_PATHS candidate simple paths ordered by time
    (plus the best rail-only path if one exists), score each with `_convenience_score`,
    and return the minimum."""
    G, NODES = graph or build_graph("time", road=True)
    source_id = _resolve_endpoint(G, NODES, source, "custom_source", "Origin")
    target_id = _resolve_endpoint(G, NODES, target, "custom_target", "Destination")
    _validate_endpoints(G, source_id, target_id)

    valid_paths = _candidate_paths_for_scoring(G, source_id, target_id)
    if not valid_paths:
        G_used, fallback_path = _find_path_with_walk_cap(G, source_id, target_id, "time")
        best_score = _convenience_score(G_used, NODES, fallback_path)
        res = _route_result(G_used, NODES, fallback_path, road=True)
        res["convenience_score"] = best_score
        return res

    best_path = min(valid_paths, key=lambda p: _convenience_score(G, NODES, p))
    best_score = _convenience_score(G, NODES, best_path)
    res = _route_result(G, NODES, best_path, road=True)
    res["convenience_score"] = best_score
    return res


def compare_routes(source, target, road: bool = False):
    """Return route candidates tagged `optimized_for`.

    When `road=False` (default): 3 candidates (`time`, `distance`, `cost`).
    When `road=True`: 4 candidates (`time`, `distance`, `cost`, `convenient`),
    reusing a single graph build across all 4 searches.
    """
    graph = build_graph(road=road)  # one fetch, shared by all searches
    candidates = {
        "time": shortest_path(source, target, "time", graph=graph, road=road),
        "distance": shortest_path(source, target, "distance", graph=graph, road=road),
        "fare_approx": shortest_path_cost_approx(source, target, graph=graph, road=road),
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

    if road:
        conv_result = dict(shortest_path_convenient(source, target, graph=graph))
        conv_result["optimized_for"] = "convenient"
        results.append(conv_result)

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