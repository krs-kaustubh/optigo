"""Error-handling tests for graph.py and the /route and /compare endpoints.
Supabase is replaced with a small fixture graph; no network.

Run:  python -m unittest discover -s tests -v   (from backend/)
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("RAILRADAR_API_KEY", "test-key")

with mock.patch("supabase.create_client"):
    from app import graph  # noqa: E402
    from app.main import app  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

# Two disconnected components: {1,2,3} train line and {10,11} metro line.
NODES = {
    1: {"name": "Vashi", "lat": 0, "lng": 0},
    2: {"name": "Sanpada", "lat": 0, "lng": 0},
    3: {"name": "Juinagar", "lat": 0, "lng": 0},
    10: {"name": "Belpada", "lat": 0, "lng": 0},
    11: {"name": "Utsav Chowk", "lat": 0, "lng": 0},
}
EDGES = [
    (1, 2, "train", 1.0, 3, 5),
    (2, 3, "train", 2.0, 3, 5),
    (10, 11, "metro", 0.7, 3, 4),
]


class FixtureGraphMixin:
    def setUp(self):
        self._nodes_patch = mock.patch.object(graph, "fetch_nodes", return_value=NODES)
        self._edges_patch = mock.patch.object(graph, "fetch_edges", return_value=EDGES)
        self._nodes_patch.start()
        self._edges_patch.start()
        self.addCleanup(self._safe_stop, self._nodes_patch)
        self.addCleanup(self._safe_stop, self._edges_patch)

    @staticmethod
    def _safe_stop(p):
        try:
            p.stop()
        except RuntimeError:
            pass  # already stopped by the test

    def fetch_nodes_patch_stop(self):
        self._safe_stop(self._nodes_patch)


class GraphErrorTests(FixtureGraphMixin, unittest.TestCase):
    def test_invalid_weight(self):
        with self.assertRaises(graph.InvalidWeight):
            graph.shortest_path(1, 3, "bogus")

    def test_unknown_source_and_target(self):
        with self.assertRaises(graph.UnknownNode) as cm:
            graph.shortest_path(999, 1)
        self.assertEqual(cm.exception.node_id, 999)
        with self.assertRaises(graph.UnknownNode):
            graph.shortest_path(1, 999)

    def test_same_node(self):
        with self.assertRaises(graph.SameNode):
            graph.shortest_path(1, 1)

    def test_no_path_between_components(self):
        with self.assertRaises(graph.NoPath):
            graph.shortest_path(1, 10)
        with self.assertRaises(graph.NoPath):
            graph.shortest_path_cost_approx(1, 10)

    def test_compare_routes_raises_instead_of_empty_list(self):
        with self.assertRaises(graph.UnknownNode):
            graph.compare_routes(1, 999)
        with self.assertRaises(graph.NoPath):
            graph.compare_routes(1, 10)
        with self.assertRaises(graph.SameNode):
            graph.compare_routes(2, 2)

    def test_compare_routes_lets_data_source_errors_propagate(self):
        with mock.patch.object(graph, "fetch_nodes", side_effect=ConnectionError("supabase down")):
            with self.assertRaises(ConnectionError):
                graph.compare_routes(1, 3)

    def test_compare_routes_fetches_graph_once(self):
        with mock.patch.object(graph, "fetch_nodes", return_value=NODES) as fn, \
             mock.patch.object(graph, "fetch_edges", return_value=EDGES) as fe:
            graph.compare_routes(1, 3)
        self.assertEqual(fn.call_count, 1)
        self.assertEqual(fe.call_count, 1)

    def test_totals_are_rounded(self):
        noisy = [(1, 2, "metro", 0.1, 3, 4), (2, 3, "metro", 0.2, 3, 4), (3, 10, "walking", 0.4, 8, 0)]
        with mock.patch.object(graph, "fetch_edges", return_value=noisy):
            r = graph.shortest_path(1, 10)
        # 0.1 + 0.2 + 0.4 == 0.7000000000000001 without rounding
        self.assertEqual(r["totals"]["distance"], 0.7)
        self.assertEqual(r["totals"]["real_fare"], 10)

    def test_stale_connection_is_retried_once(self):
        import httpx
        calls = {"n": 0}
        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.RemoteProtocolError("Server disconnected")
            return mock.Mock(data=[{"id": 1, "name": "Vashi", "lat": 0, "lng": 0, "type": "rail"}])
        with mock.patch.object(graph.supabase, "rpc") as rpc:
            rpc.return_value.execute.side_effect = flaky
            self.fetch_nodes_patch_stop()
            nodes = graph.fetch_nodes()
        self.assertEqual(calls["n"], 2)
        self.assertEqual(nodes[1]["name"], "Vashi")

    def test_persistent_transport_error_becomes_upstream_error(self):
        import httpx
        self.fetch_nodes_patch_stop()
        with mock.patch.object(graph.supabase, "rpc") as rpc:
            rpc.return_value.execute.side_effect = httpx.RemoteProtocolError("Server disconnected")
            with self.assertRaises(graph.UpstreamError):
                graph.fetch_nodes()
            self.assertEqual(rpc.return_value.execute.call_count, 2)

    def test_happy_path_still_works(self):
        r = graph.shortest_path(1, 3, "time")
        self.assertEqual(r["path"], ["Vashi", "Sanpada", "Juinagar"])
        self.assertEqual(r["totals"]["real_fare"], 5)
        self.assertEqual([c["optimized_for"] for c in graph.compare_routes(3, 1)],
                         ["time", "distance", "cost"])


class EndpointErrorTests(FixtureGraphMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_bad_weight_is_422(self):
        r = self.client.get("/route?source=1&target=3&weight=bogus")
        self.assertEqual(r.status_code, 422)

    def test_unknown_node_is_404_with_detail(self):
        r = self.client.get("/route?source=1&target=999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json(), {"detail": "unknown node id 999", "error": "UnknownNode"})
        r = self.client.get("/compare?source=1&target=999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "UnknownNode")

    def test_no_path_is_404(self):
        r = self.client.get("/compare?source=1&target=10")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "NoPath")

    def test_same_node_is_400(self):
        r = self.client.get("/route?source=1&target=1")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "SameNode")
        r = self.client.get("/compare?source=1&target=1")
        self.assertEqual(r.status_code, 400)

    def test_non_integer_node_is_422(self):
        self.assertEqual(self.client.get("/route?source=abc&target=1").status_code, 422)

    def test_data_source_failure_is_500_not_empty_200(self):
        with mock.patch.object(graph, "fetch_nodes", side_effect=ConnectionError("supabase down")):
            r = self.client.get("/compare?source=1&target=3")
        self.assertEqual(r.status_code, 500)

    def test_upstream_error_is_502_with_detail(self):
        with mock.patch.object(graph, "fetch_nodes", side_effect=graph.UpstreamError("Supabase unreachable: x")):
            r = self.client.get("/nodes")
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.json(), {"detail": "Supabase unreachable: x", "error": "UpstreamError"})

    def test_nodes_endpoint(self):
        r = self.client.get("/nodes")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual([n["id"] for n in body], [1, 2, 3, 10, 11])
        self.assertEqual(body[0], {"id": 1, "name": "Vashi", "lat": 0, "lng": 0})

    def test_happy_path_shapes(self):
        r = self.client.get("/route?source=1&target=3&weight=cost")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), {"path", "edges", "totals"})
        r = self.client.get("/compare?source=1&target=3")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 3)


if __name__ == "__main__":
    unittest.main()
