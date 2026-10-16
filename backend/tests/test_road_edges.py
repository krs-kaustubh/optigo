"""Offline unit tests for Phase C/D: Road edges, warm nodes, leg grouping,
CAB_PICKUP_WAIT_MIN, walking cap, convenience scoring, 24-node production
fixture checks, edge cases, and backwards-compatibility snapshots.

All warm nodes and road edges in this file are SYNTHETIC TEST-ONLY FIXTURES.
No network or Supabase connection is made.
"""

import json
import os
import unittest
from unittest import mock

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("RAILRADAR_API_KEY", "test-key")

with mock.patch("supabase.create_client"):
    from app import cabs, graph  # noqa: E402
    from app.main import app  # noqa: E402
    from scripts.seed_warm_nodes import HOT_NODES, compute_road_edge_pairs  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

# ----------------------------------------------------------------------------
# Canonical hot-only fixture (for byte-identical snapshot testing of road=False)
# ----------------------------------------------------------------------------
HOT_ONLY_NODES = {
    1: {"name": "Vashi", "lat": 19.0632517, "lng": 72.9988553, "type": "rail"},
    2: {"name": "Sanpada", "lat": 19.0659637, "lng": 73.0094849, "type": "rail"},
    3: {"name": "Juinagar", "lat": 19.0562946, "lng": 73.0178235, "type": "rail"},
    6: {"name": "Belapur CBD", "lat": 19.0188208, "lng": 73.0388390, "type": "rail_metro_uran_interchange"},
    8: {"name": "Kharghar", "lat": 19.0263639, "lng": 73.0594488, "type": "rail"},
    15: {"name": "Belpada", "lat": 19.0254324, "lng": 73.0552703, "type": "metro"},
}

RAILWAY_EDGES = [
    (1, 2, "train", 1.0, 3, 5),
    (2, 3, "train", 2.0, 3, 5),
    (3, 6, "train", 5.0, 10, 5),
    (6, 8, "train", 2.0, 5, 5),
    (6, 15, "metro", 2.0, 4, 4),
    (15, 8, "walking", 0.6, 8, 0),
]

# ----------------------------------------------------------------------------
# SYNTHETIC TEST-ONLY FIXTURE: Hot + Warm nodes and road_edges
# ----------------------------------------------------------------------------
SYNTHETIC_ALL_NODES = {
    nid: {
        **attrs,
        "tier": "hot",
        "kind": "metro" if attrs["type"] == "metro" else "rail",
        "source": "seed",
        "confidence": "high",
    }
    for nid, attrs in HOT_ONLY_NODES.items()
}
SYNTHETIC_ALL_NODES.update({
    101: {
        "name": "[TEST-ONLY] Sector 17 Auto Stand",
        "lat": 19.0700,
        "lng": 73.0000,
        "type": "auto_stand",
        "tier": "warm",
        "kind": "auto_stand",
        "source": "test_fixture",
        "confidence": "medium",
    },
    102: {
        "name": "[TEST-ONLY] Palm Beach Junction Stop",
        "lat": 19.0680,
        "lng": 73.0050,
        "type": "bus_stop",
        "tier": "warm",
        "kind": "bus_stop",
        "source": "test_fixture",
        "confidence": "medium",
    },
})

# Road edges: (from_node, to_node, distance_km, distance_source)
# - 101 -> 1 (0.8 km): <= 1.0 km, so walkable (9.6 min walk, ₹0, no wait, no cab_estimates)
# - 101 -> 102 (1.2 km) + 102 -> 2 (1.5 km): two consecutive cab edges (total 2.7 km)
#   that must be grouped into ONE road leg (101 -> 2 via 102), with CAB_PICKUP_WAIT_MIN (4 min)
#   added ONCE (6.48 + 4.0 = 10.48 min) and priced ONCE (₹48.86)!
SYNTHETIC_ROAD_EDGES = [
    (101, 1, 0.8, "estimated"),
    (101, 102, 1.2, "estimated"),
    (102, 2, 1.5, "estimated"),
]


def _build_production_24_node_fixture():
    """Build the 24-node, 26-edge production topology from seed.sql plus
    k-NN hot-to-hot road edges at haversine * 1.30."""
    prod_nodes = {}
    name_to_id = {}
    for idx, n in enumerate(HOT_NODES, start=1):
        prod_nodes[idx] = {
            "name": n["name"],
            "lat": n["lat"],
            "lng": n["lng"],
            "type": n["kind"],
            "tier": "hot",
            "kind": n["kind"],
            "source": "seed",
            "confidence": "high",
        }
        name_to_id[n["name"]] = idx

    raw_rail_edges = [
        # Harbour (9)
        ("Vashi", "Sanpada", "train", 1.0, 3, 5),
        ("Sanpada", "Juinagar", "train", 2.0, 3, 5),
        ("Juinagar", "Nerul", "train", 2.0, 3, 5),
        ("Nerul", "Seawoods-Darave", "train", 1.0, 3, 5),
        ("Seawoods-Darave", "Belapur CBD", "train", 3.0, 4, 5),
        ("Belapur CBD", "Kharghar", "train", 2.0, 5, 5),
        ("Kharghar", "Mansarovar", "train", 3.0, 4, 5),
        ("Mansarovar", "Khandeshwar", "train", 2.0, 4, 5),
        ("Khandeshwar", "Panvel", "train", 3.0, 5, 5),
        # Uran branch (5)
        ("Belapur CBD", "Sagar Sangam", "train", 2.0, 3, 5),
        ("Seawoods-Darave", "Sagar Sangam", "train", 3.0, 3, 5),
        ("Sagar Sangam", "Targhar", "train", 2.0, 3, 5),
        ("Targhar", "Bamandongri", "train", 3.0, 3, 5),
        ("Bamandongri", "Kharkopar", "train", 2.0, 4, 5),
        # Metro Line 1 (10)
        ("Belapur CBD", "RBI", "metro", 1.0, 2, 4),
        ("RBI", "Belpada", "metro", 1.0, 2, 4),
        ("Belpada", "Utsav Chowk", "metro", 0.7, 3, 4),
        ("Utsav Chowk", "Kendriya Vihar", "metro", 0.8, 3, 4),
        ("Kendriya Vihar", "Kharghar Village", "metro", 1.3, 3, 4),
        ("Kharghar Village", "Central Park", "metro", 1.4, 3, 4),
        ("Central Park", "Pethpada", "metro", 1.6, 3, 4),
        ("Pethpada", "Amandoot", "metro", 1.2, 3, 4),
        ("Amandoot", "Pethali-Taloja", "metro", 1.1, 3, 4),
        ("Pethali-Taloja", "Pendhar", "metro", 1.1, 3, 4),
        # Walking interchange (2)
        ("Belpada", "Kharghar", "walking", 0.6, 8, 0),
        ("Kharghar", "Belpada", "walking", 0.6, 8, 0),
    ]
    prod_rail_edges = [
        (name_to_id[u], name_to_id[v], mode, dist, t, c)
        for u, v, mode, dist, t, c in raw_rail_edges
    ]

    directed_road = compute_road_edge_pairs(HOT_NODES, [])
    prod_road_edges = [
        (name_to_id[u], name_to_id[v], dist, "estimated")
        for u, v, dist in directed_road
    ]
    return prod_nodes, prod_rail_edges, prod_road_edges, name_to_id


class RoadEdgesAndSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_default_road_false_snapshot_is_byte_identical(self):
        """Requirement 4 & Correction D: road=False output is byte-identical to the
        pre-Phase-C snapshot for /nodes, /route, and /compare, and never touches
        the new RPC or tables."""
        with mock.patch.object(graph, "fetch_nodes", return_value=HOT_ONLY_NODES) as fn, \
             mock.patch.object(graph, "fetch_edges", return_value=RAILWAY_EDGES) as fe, \
             mock.patch.object(graph, "fetch_all_nodes") as fall, \
             mock.patch.object(graph, "fetch_railway_edges") as frail, \
             mock.patch.object(graph, "fetch_road_edges") as froad:

            nodes_resp = self.client.get("/nodes")
            route_resp = self.client.get("/route?source=1&target=8&weight=time")
            compare_resp = self.client.get("/compare?source=1&target=8")

        self.assertEqual(nodes_resp.status_code, 200)
        self.assertEqual(route_resp.status_code, 200)
        self.assertEqual(compare_resp.status_code, 200)

        fall.assert_not_called()
        frail.assert_not_called()
        froad.assert_not_called()
        self.assertEqual(fn.call_count, 3)
        self.assertEqual(fe.call_count, 2)

        expected_nodes = [
            {"id": 1, "name": "Vashi", "lat": 19.0632517, "lng": 72.9988553, "type": "rail"},
            {"id": 2, "name": "Sanpada", "lat": 19.0659637, "lng": 73.0094849, "type": "rail"},
            {"id": 3, "name": "Juinagar", "lat": 19.0562946, "lng": 73.0178235, "type": "rail"},
            {"id": 6, "name": "Belapur CBD", "lat": 19.0188208, "lng": 73.0388390, "type": "rail_metro_uran_interchange"},
            {"id": 8, "name": "Kharghar", "lat": 19.0263639, "lng": 73.0594488, "type": "rail"},
            {"id": 15, "name": "Belpada", "lat": 19.0254324, "lng": 73.0552703, "type": "metro"},
        ]
        self.assertEqual(
            json.dumps(nodes_resp.json(), sort_keys=True),
            json.dumps(expected_nodes, sort_keys=True),
        )

        expected_compare = [
            {
                "path": ["Vashi", "Sanpada", "Juinagar", "Belapur CBD", "Kharghar"],
                "edges": [
                    {"from": "Vashi", "to": "Sanpada", "mode": "train"},
                    {"from": "Sanpada", "to": "Juinagar", "mode": "train"},
                    {"from": "Juinagar", "to": "Belapur CBD", "mode": "train"},
                    {"from": "Belapur CBD", "to": "Kharghar", "mode": "train"},
                ],
                "totals": {"distance": 10.0, "time": 21, "cost": 20, "real_fare": 5},
                "optimized_for": "time",
            },
            {
                "path": ["Vashi", "Sanpada", "Juinagar", "Belapur CBD", "Kharghar"],
                "edges": [
                    {"from": "Vashi", "to": "Sanpada", "mode": "train"},
                    {"from": "Sanpada", "to": "Juinagar", "mode": "train"},
                    {"from": "Juinagar", "to": "Belapur CBD", "mode": "train"},
                    {"from": "Belapur CBD", "to": "Kharghar", "mode": "train"},
                ],
                "totals": {"distance": 10.0, "time": 21, "cost": 20, "real_fare": 5},
                "optimized_for": "distance",
            },
            {
                "path": ["Vashi", "Sanpada", "Juinagar", "Belapur CBD", "Kharghar"],
                "edges": [
                    {"from": "Vashi", "to": "Sanpada", "mode": "train"},
                    {"from": "Sanpada", "to": "Juinagar", "mode": "train"},
                    {"from": "Juinagar", "to": "Belapur CBD", "mode": "train"},
                    {"from": "Belapur CBD", "to": "Kharghar", "mode": "train"},
                ],
                "totals": {"distance": 10.0, "time": 21, "cost": 20, "real_fare": 5},
                "optimized_for": "cost",
            },
        ]
        self.assertEqual(
            json.dumps(compare_resp.json(), sort_keys=True),
            json.dumps(expected_compare, sort_keys=True),
        )

    def test_nodes_include_warm_opt_in(self):
        with mock.patch.object(graph, "fetch_all_nodes", return_value=SYNTHETIC_ALL_NODES) as fall:
            resp = self.client.get("/nodes?include_warm=true")
        self.assertEqual(resp.status_code, 200)
        fall.assert_called_once()
        body = resp.json()
        tiers = {n["id"]: n["tier"] for n in body}
        self.assertEqual(tiers[1], "hot")
        self.assertEqual(tiers[101], "warm")
        self.assertEqual(tiers[102], "warm")

    def test_compare_road_true_cab_wait_and_cab_estimates_only_on_cab_legs(self):
        """Phase C changes 1 & 2:
        - CAB_PICKUP_WAIT_MIN (4 min) added once per grouped cab leg (not walking legs).
        - cab_estimates attached only to cab legs, not walking legs."""
        with mock.patch.object(graph, "fetch_all_nodes", return_value=SYNTHETIC_ALL_NODES) as fall, \
             mock.patch.object(graph, "fetch_railway_edges", return_value=RAILWAY_EDGES) as frail, \
             mock.patch.object(graph, "fetch_road_edges", return_value=SYNTHETIC_ROAD_EDGES) as froad:

            resp = self.client.get("/compare?source=101&target=3&road=true")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(fall.call_count, 1)
        self.assertEqual(frail.call_count, 1)
        self.assertEqual(froad.call_count, 1)

        routes = resp.json()
        self.assertEqual([r["optimized_for"] for r in routes], ["time", "distance", "cost", "convenient"])

        for r in routes:
            for leg in r["road_legs"]:
                self.assertEqual(leg["distance_source"], "estimated")
                self.assertEqual(leg["time_source"], "estimated")
                self.assertEqual(leg["fare_source"], "estimated")
                if leg["mode"] == "cab":
                    self.assertIn("cab_estimates", leg)
                    self.assertGreaterEqual(len(leg["cab_estimates"]), 6)
                else:
                    self.assertNotIn("cab_estimates", leg)

        # Fastest route: 2-hop cab leg (2.7 km @ 25 km/h = 6.48 min + 4.0 min CAB_PICKUP_WAIT_MIN = 10.48 min)
        # + train Sanpada -> Juinagar (3 min) = 13.48 min total.
        # (Whereas walking 101 -> Vashi is 9.6 min + train Vashi -> Sanpada -> Juinagar 6 min = 15.6 min).
        fastest = routes[0]
        cab_leg = fastest["road_legs"][0]
        self.assertEqual(cab_leg["mode"], "cab")
        self.assertEqual(cab_leg["via"], ["[TEST-ONLY] Palm Beach Junction Stop"])
        self.assertEqual(cab_leg["distance"], 2.7)
        self.assertEqual(cab_leg["time"], 10.48)
        self.assertEqual(cab_leg["cost"], 48.86)
        self.assertEqual(fastest["totals"]["time"], 13.48)
        self.assertEqual(fastest["totals"]["real_fare"], 53.86)
        # Note: edges has 2 entries (merged cab leg + 1 train edge) even though path has 4 nodes
        self.assertEqual(len(fastest["path"]), 4)
        self.assertEqual(len(fastest["edges"]), 2)

        # Cheapest route: walks 101 -> Vashi (0.8 km, 9.6 min, NO wait added, NO cab_estimates)
        cheapest = routes[2]
        walk_leg = cheapest["road_legs"][0]
        self.assertEqual(walk_leg["mode"], "walking")
        self.assertEqual(walk_leg["time"], 9.6)
        self.assertEqual(walk_leg["cost"], 0)
        self.assertNotIn("cab_estimates", walk_leg)
        self.assertEqual(cheapest["totals"]["real_fare"], 5.0)

    def test_real_data_adjacent_harbour_stations_use_train_not_cab(self):
        """Phase C change 3: On the 24-node, 26-edge production topology with hot-to-hot
        road edges at haversine * 1.30, routes between adjacent Harbour rail stations
        (Vashi->Sanpada, Nerul->Seawoods-Darave, Belapur CBD->Kharghar) still use the
        train, not a cab hop, for the time and cost criteria when road=true."""
        prod_nodes, prod_rail, prod_road, name_to_id = _build_production_24_node_fixture()

        pairs = [
            ("Vashi", "Sanpada"),
            ("Nerul", "Seawoods-Darave"),
            ("Belapur CBD", "Kharghar"),
        ]
        with mock.patch.object(graph, "fetch_all_nodes", return_value=prod_nodes), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=prod_rail), \
             mock.patch.object(graph, "fetch_road_edges", return_value=prod_road):

            for src_name, dst_name in pairs:
                routes = graph.compare_routes(name_to_id[src_name], name_to_id[dst_name], road=True)
                by_opt = {r["optimized_for"]: r for r in routes}
                for crit in ("time", "cost"):
                    route = by_opt[crit]
                    self.assertEqual(
                        route["path"],
                        [src_name, dst_name],
                        f"{src_name}->{dst_name} ({crit}) did not take direct hop",
                    )
                    self.assertEqual(
                        [e["mode"] for e in route["edges"]],
                        ["train"],
                        f"{src_name}->{dst_name} ({crit}) used {route['edges']} instead of train",
                    )
                    self.assertEqual(route["road_legs"], [])

    def test_walking_cap_removes_longest_walk_edge_and_reruns(self):
        """Correction B: When total walking on a candidate exceeds MAX_TOTAL_WALK_KM (1.5 km),
        remove the longest walking edge and re-run (up to 5 times)."""
        nodes = {
            1: {"name": "A", "lat": 19.00, "lng": 73.00, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
            2: {"name": "B", "lat": 19.01, "lng": 73.01, "type": "bus_stop", "tier": "warm", "kind": "bus_stop", "source": "test", "confidence": "low"},
            3: {"name": "C", "lat": 19.02, "lng": 73.02, "type": "bus_stop", "tier": "warm", "kind": "bus_stop", "source": "test", "confidence": "low"},
            4: {"name": "D", "lat": 19.03, "lng": 73.03, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
        }
        rail_edges = [(1, 4, "train", 3.0, 6, 5)]
        road_edges = [
            (1, 2, 0.6, "estimated"),
            (2, 3, 0.7, "estimated"),
            (3, 4, 0.8, "estimated"),
        ]
        with mock.patch.object(graph, "fetch_all_nodes", return_value=nodes), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=rail_edges), \
             mock.patch.object(graph, "fetch_road_edges", return_value=road_edges):

            res = graph.shortest_path_cost_approx(1, 4, road=True)

        self.assertEqual(res["path"], ["A", "D"])
        self.assertEqual(res["totals"]["real_fare"], 5.0)

    def test_walking_cap_iteration_limit_stops_at_five(self):
        """Phase D edge case: Walking-cap re-run loop stops after at most
        MAX_WALK_CAP_ITERATIONS (5) re-runs even when >5 parallel walk chains exist."""
        nodes = {
            1: {"name": "Start", "lat": 19.0, "lng": 73.0, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
            2: {"name": "End", "lat": 19.1, "lng": 73.1, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
        }
        road_edges = []
        # Create 7 disjoint 2-hop walking chains between 1 and 2, each 0.9 + 0.9 = 1.8 km (> 1.5 km cap)
        for i in range(7):
            mid = 10 + i
            nodes[mid] = {
                "name": f"WalkMid{i}",
                "lat": 19.05,
                "lng": 73.05,
                "type": "bus_stop",
                "tier": "warm",
                "kind": "bus_stop",
                "source": "test",
                "confidence": "low",
            }
            road_edges.append((1, mid, 0.9, "estimated"))
            road_edges.append((mid, 2, 0.9, "estimated"))

        with mock.patch.object(graph, "fetch_all_nodes", return_value=nodes), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=[]), \
             mock.patch.object(graph, "fetch_road_edges", return_value=road_edges):
            G, _ = graph.build_graph(road=True)
            with mock.patch("networkx.shortest_path", wraps=graph.nx.shortest_path) as spy_sp:
                graph._find_path_with_walk_cap(G, 1, 2, "fare_weight")
                # 1 initial call + at most 5 re-runs = 6 total calls
                self.assertEqual(spy_sp.call_count, 1 + graph.MAX_WALK_CAP_ITERATIONS)

    def test_warm_node_with_no_hot_neighbour_within_radius_is_connected_and_isolated_raises_nopath(self):
        """Phase D edge case:
        1. `compute_road_edge_pairs` connects a far warm node (>3 km from all hot nodes)
           to its single nearest hot node so it is never left isolated.
        2. If a warm node in the DB has no edges at all, routing from it raises NoPath (404)."""
        far_warm = [{
            "name": "[TEST-ONLY] Far Warm Stop",
            "lat": 19.1200,  # >6 km north of Vashi
            "lng": 72.9988,
            "tier": "warm",
            "kind": "bus_stop",
            "source": "test",
            "confidence": "low",
        }]
        edges = compute_road_edge_pairs(HOT_NODES, far_warm)
        far_touch = [dst for src, dst, _ in edges if src == "[TEST-ONLY] Far Warm Stop"]
        self.assertEqual(far_touch, ["Sanpada"])

        # Also test an isolated warm node in G raises NoPath (404)
        isolated_nodes = {
            **SYNTHETIC_ALL_NODES,
            999: {
                "name": "[TEST-ONLY] Isolated Warm Node",
                "lat": 19.2,
                "lng": 73.2,
                "type": "bus_stop",
                "tier": "warm",
                "kind": "bus_stop",
                "source": "test",
                "confidence": "low",
            },
        }
        with mock.patch.object(graph, "fetch_all_nodes", return_value=isolated_nodes), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=RAILWAY_EDGES), \
             mock.patch.object(graph, "fetch_road_edges", return_value=SYNTHETIC_ROAD_EDGES):
            r = self.client.get("/compare?source=999&target=1&road=true")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "NoPath")

    def test_unknown_node_and_same_node_with_road_true(self):
        """Phase D edge cases: node not in graph (404 UnknownNode) and same source/target (400 SameNode)."""
        with mock.patch.object(graph, "fetch_all_nodes", return_value=SYNTHETIC_ALL_NODES), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=RAILWAY_EDGES), \
             mock.patch.object(graph, "fetch_road_edges", return_value=SYNTHETIC_ROAD_EDGES):
            r_unknown = self.client.get("/compare?source=8888&target=1&road=true")
            r_same = self.client.get("/compare?source=101&target=101&road=true")

        self.assertEqual(r_unknown.status_code, 404)
        self.assertEqual(r_unknown.json()["error"], "UnknownNode")
        self.assertEqual(r_same.status_code, 400)
        self.assertEqual(r_same.json()["error"], "SameNode")

    def test_road_leg_of_exactly_1_5_km(self):
        """Phase D edge case: A road leg of exactly 1.5 km is a cab leg (since 1.5 > 1.0 km walk cap),
        priced at the exact base fare ₹27.00 with duration (1.5 / 25)*60 + 4.0 = 7.6 min."""
        nodes = {
            1: {"name": "Vashi", "lat": 19.0632517, "lng": 72.9988553, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
            200: {"name": "[TEST-ONLY] 1.5km Stop", "lat": 19.0750, "lng": 73.0050, "type": "auto_stand", "tier": "warm", "kind": "auto_stand", "source": "test", "confidence": "medium"},
        }
        road_edges = [(200, 1, 1.5, "estimated")]
        with mock.patch.object(graph, "fetch_all_nodes", return_value=nodes), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=[]), \
             mock.patch.object(graph, "fetch_road_edges", return_value=road_edges):
            res = graph.shortest_path(200, 1, "time", road=True)

        self.assertEqual(len(res["road_legs"]), 1)
        leg = res["road_legs"][0]
        self.assertEqual(leg["mode"], "cab")
        self.assertEqual(leg["distance"], 1.5)
        self.assertEqual(leg["cost"], 27.0)
        self.assertEqual(leg["time"], 7.6)  # 3.6 min driving + 4.0 min CAB_PICKUP_WAIT_MIN
        self.assertEqual(res["totals"]["real_fare"], 27.0)
        self.assertEqual(res["totals"]["time"], 7.6)

    def test_convenient_weight_requires_road_true(self):
        with mock.patch.object(graph, "fetch_nodes", return_value=HOT_ONLY_NODES), \
             mock.patch.object(graph, "fetch_edges", return_value=RAILWAY_EDGES):
            r_false = self.client.get("/route?source=1&target=3&weight=convenient")
        self.assertEqual(r_false.status_code, 422)

        with mock.patch.object(graph, "fetch_all_nodes", return_value=SYNTHETIC_ALL_NODES), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=RAILWAY_EDGES), \
             mock.patch.object(graph, "fetch_road_edges", return_value=SYNTHETIC_ROAD_EDGES):
            r_true = self.client.get("/route?source=101&target=3&weight=convenient&road=true")
        self.assertEqual(r_true.status_code, 200)
        self.assertIn("convenience_score", r_true.json())

    def test_option_2_auto_tariff_values(self):
        """Requirement 7: Option 2 tariff (₹27 base for 1.5 km + ₹18.22/km)."""
        self.assertEqual(cabs.metered_auto_fare(1.0), 27.0)
        self.assertEqual(cabs.metered_auto_fare(1.5), 27.0)
        self.assertEqual(cabs.metered_auto_fare(2.5), round(27.0 + 18.22, 2))

    def test_kharghar_belpada_railway_walk_not_overwritten_by_road_edge(self):
        """Follow-up 1: In build_graph(road=True), skip any pair where an edge already exists
        and is not itself a road edge (is_road False), not only train/metro.
        Kharghar <-> Belpada keeps its railway walking values (0.6 km, 8 min) with road=true."""
        prod_nodes, prod_rail, prod_road, name_to_id = _build_production_24_node_fixture()
        kharghar_id = name_to_id["Kharghar"]
        belpada_id = name_to_id["Belpada"]

        with mock.patch.object(graph, "fetch_all_nodes", return_value=prod_nodes), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=prod_rail), \
             mock.patch.object(graph, "fetch_road_edges", return_value=prod_road):
            G, _ = graph.build_graph(road=True)
            res = graph.shortest_path(kharghar_id, belpada_id, "time", road=True)

        for u, v in [(kharghar_id, belpada_id), (belpada_id, kharghar_id)]:
            edge = G[u][v]
            self.assertFalse(edge["is_road"])
            self.assertEqual(edge["mode"], "walking")
            self.assertEqual(edge["distance"], 0.6)
            self.assertEqual(edge["time"], 8)

        self.assertEqual(res["path"], ["Kharghar", "Belpada"])
        self.assertEqual(res["totals"]["distance"], 0.6)
        self.assertEqual(res["totals"]["time"], 8)
        self.assertEqual(res["road_legs"], [])

    def test_rail_only_path_added_to_candidate_pool_and_wins_convenient(self):
        """Follow-up 2: In shortest_path_convenient and road time search, add the best path
        on the graph with all road edges removed (rail-only) to the candidate pool before scoring.
        Test where the rail-only path is not in the top 10 by raw edge time, but wins on convenience."""
        nodes = {
            1: {"name": "Start", "lat": 19.00, "lng": 73.00, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
            2: {"name": "End", "lat": 19.10, "lng": 73.10, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
        }
        # Direct rail-only edge: 20 min raw time, 0 transfers, 0 cab wait -> convenience score = 20.0
        rail_edges = [(1, 2, "train", 10.0, 20.0, 10)]
        road_edges = []

        # Create 12 distinct 2-hop road (cab) paths through warm nodes 10..21:
        # Each hop is 1.5 km -> 3.6 min raw edge time; 2 hops = 7.2 min raw time (< 20 min rail),
        # so the first 10 simple paths by raw edge time are all road paths!
        # Wait: if both hops are road, they merge into 1 cab leg of 3.0 km (7.2 min + 4 min wait = 11.2 min).
        # To make them score worse on convenience (and time with pickup wait), make each path:
        # road cab (1.5 km, 3.6 min) -> intermediate rail node -> train (1 km, 2.0 min) -> road cab (1.5 km, 3.6 min)
        # Raw time = 3.6 + 2.0 + 3.6 = 9.2 min (< 20.0 min rail-only!),
        # but with 2 separate cab legs (+8.0 min pickup wait) and 2 mode transfers (+16.0 min penalty),
        # convenience score = (9.2 + 8.0) + 16.0 = 33.2 > 20.0!
        for i in range(12):
            a = 100 + i * 2
            b = 100 + i * 2 + 1
            nodes[a] = {"name": f"MidA_{i}", "lat": 19.03, "lng": 73.03, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"}
            nodes[b] = {"name": f"MidB_{i}", "lat": 19.06, "lng": 73.06, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"}
            road_edges.append((1, a, 1.5, "estimated"))
            rail_edges.append((a, b, "train", 1.0, 2.0 + i * 0.01, 5))
            road_edges.append((b, 2, 1.5, "estimated"))

        with mock.patch.object(graph, "fetch_all_nodes", return_value=nodes), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=rail_edges), \
             mock.patch.object(graph, "fetch_road_edges", return_value=road_edges):
            conv = graph.shortest_path_convenient(1, 2)

        self.assertEqual(conv["path"], ["Start", "End"])
        self.assertEqual(conv["edges"], [{"from": "Start", "to": "End", "mode": "train"}])
        self.assertEqual(conv["convenience_score"], 20.0)

    def test_separate_contiguous_train_runs_priced_separately(self):
        """Follow-up 3: In _route_result(road=True), price each contiguous train run and each
        contiguous metro run separately instead of summing distances per mode across the whole route.
        Train 3 km -> cab -> train 5 km gives two train fares (₹5 + ₹5 = ₹10) plus cab fare."""
        nodes = {
            1: {"name": "S1", "lat": 19.00, "lng": 73.00, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
            2: {"name": "S2", "lat": 19.02, "lng": 73.02, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
            3: {"name": "S3", "lat": 19.04, "lng": 73.04, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
            4: {"name": "S4", "lat": 19.08, "lng": 73.08, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
        }
        rail_edges = [
            (1, 2, "train", 3.0, 4.0, 5),
            (3, 4, "train", 5.0, 6.0, 5),
        ]
        road_edges = [
            (2, 3, 2.0, "estimated"),
        ]
        with mock.patch.object(graph, "fetch_all_nodes", return_value=nodes), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=rail_edges), \
             mock.patch.object(graph, "fetch_road_edges", return_value=road_edges):
            res = graph.shortest_path(1, 4, "time", road=True)

        # Train 3 km -> ₹5; Train 5 km -> ₹5 (if summed as 8 km it would have been a single ₹5 slab!).
        # Cab 2.0 km -> ₹27 + 0.5 * 18.22 = ₹36.11.
        # Total real_fare = 5 + 5 + 36.11 = ₹46.11.
        expected_cab_fare = cabs.metered_auto_fare(2.0)
        self.assertEqual(expected_cab_fare, 36.11)
        self.assertEqual(res["totals"]["real_fare"], round(5 + 5 + expected_cab_fare, 2))

    def test_walking_cap_exceeded_adds_warning(self):
        """Follow-up 4: If the walking-cap loop ends with the route still above MAX_TOTAL_WALK_KM,
        add "warnings": ["walking_cap_exceeded"] to the route."""
        nodes = {
            1: {"name": "Start", "lat": 19.0, "lng": 73.0, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
            2: {"name": "End", "lat": 19.1, "lng": 73.1, "type": "rail", "tier": "hot", "kind": "rail", "source": "seed", "confidence": "high"},
        }
        road_edges = []
        for i in range(7):
            mid = 10 + i
            nodes[mid] = {
                "name": f"WalkMid{i}",
                "lat": 19.05,
                "lng": 73.05,
                "type": "bus_stop",
                "tier": "warm",
                "kind": "bus_stop",
                "source": "test",
                "confidence": "low",
            }
            road_edges.append((1, mid, 0.9, "estimated"))
            road_edges.append((mid, 2, 0.9, "estimated"))

        with mock.patch.object(graph, "fetch_all_nodes", return_value=nodes), \
             mock.patch.object(graph, "fetch_railway_edges", return_value=[]), \
             mock.patch.object(graph, "fetch_road_edges", return_value=road_edges):
            res = graph.shortest_path_cost_approx(1, 2, road=True)

        self.assertEqual(res.get("warnings"), ["walking_cap_exceeded"])


if __name__ == "__main__":
    unittest.main()
