"""Unit tests for Phase C: Shared Alternatives Engine (Ideas 1 and 2).
Tests backing, forward switching, edge cases (origin boarding, branch mismatch,
no train leg, pivot caps) against real live-batch-1 fixtures.
"""

import json
import os
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("RAILRADAR_API_KEY", "test-key")

from fastapi.testclient import TestClient
from app.main import app
from app import alternatives as alt
from app import railradar as rr
from app import graph

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "boards" / "live-batch-1"
GRAPH_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "graph_network.json"


def load_fixture_boards():
    boards = {}
    for p in FIXTURES_DIR.glob("*.json"):
        if p.name == "manifest.json":
            continue
        data = json.loads(p.read_text())
        boards[data["code"]] = data["body"]
    return boards


def load_graph_fixtures():
    data = json.loads(GRAPH_FIXTURE_PATH.read_text())
    nodes = {int(k): v for k, v in data["nodes"].items()}
    edges = [tuple(e) for e in data["edges"]]
    return nodes, edges


class PhaseCAlternativesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boards = load_fixture_boards()
        cls.fixture_nodes, cls.fixture_edges = load_graph_fixtures()
        cls.name_to_id = {v["name"]: k for k, v in cls.fixture_nodes.items()}
        cls.client = TestClient(app)

    def setUp(self):
        rr.clear_board_cache()
        self.node_patch = mock.patch.object(graph, "fetch_nodes", return_value=self.fixture_nodes)
        self.edge_patch = mock.patch.object(graph, "fetch_edges", return_value=self.fixture_edges)
        self.node_patch.start()
        self.edge_patch.start()
        self.addCleanup(self.node_patch.stop)
        self.addCleanup(self.edge_patch.stop)

        self.patcher = mock.patch.object(
            rr, "get_station_live_board",
            side_effect=lambda code, hours=2, use_cache=True: self.boards[code]
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_find_pivots_kharghar_to_vashi(self):
        """Kharghar to Vashi heading towards Mumbai should find Belapur CBD as a switching pivot."""
        pivots = alt.find_pivots("KHAG", "VSH", "harbour")
        codes = [p["code"] for p in pivots]
        self.assertIn("BEPR", codes)
        self.assertTrue(any(p["kind"] == "switch" for p in pivots if p["code"] == "BEPR"))

    def test_find_pivots_khandeshwar_to_nerul(self):
        """Khandeshwar to Nerul should find Panvel as a backing pivot and Belapur as switching."""
        pivots = alt.find_pivots("KNDS", "NEU", "harbour")
        codes = [p["code"] for p in pivots]
        self.assertIn("PNVL", codes)
        self.assertTrue(any(p["kind"] == "back" for p in pivots if p["code"] == "PNVL"))

    def test_find_pivots_capped_at_max(self):
        """Pivots returned should never exceed max_pivots (default 2)."""
        pivots = alt.find_pivots("KNDS", "VSH", "harbour", max_pivots=2)
        self.assertLessEqual(len(pivots), 2)

    def test_kharghar_to_vashi_forward_switch_at_belapur(self):
        """Idea 2: Kharghar to Vashi should produce a forward switch alternative via Belapur CBD."""
        src_id = self.name_to_id["Kharghar"]
        dst_id = self.name_to_id["Vashi"]
        routes = graph.compare_routes(src_id, dst_id)
        route = routes[0]

        alt.annotate_route_with_alternatives(
            route,
            prefer_seat=True,
            threshold_minutes=25,
            fetch_board_fn=lambda c: self.boards[c],
        )

        st = route["live_alternatives_status"]
        self.assertTrue(st["applicable"])
        self.assertEqual(st["reason"], "ok")
        self.assertIn("BEPR", st["pivots_checked"])

        alts = route["live_alternatives"]
        self.assertGreater(len(alts), 0)
        switch_alt = next((a for a in alts if a["kind"] == "switch"), None)
        self.assertIsNotNone(switch_alt)
        self.assertEqual(switch_alt["via"], "Belapur CBD")
        self.assertTrue(switch_alt["seat"])
        self.assertIn("leg1", switch_alt)
        self.assertIn("leg2", switch_alt)
        self.assertIn("direct", switch_alt)
        self.assertIn("likely seat", switch_alt["note"])

    def test_khandeshwar_to_nerul_backing_via_panvel(self):
        """Idea 1: Khandeshwar to Nerul should evaluate backing via Panvel."""
        src_id = self.name_to_id["Khandeshwar"]
        dst_id = self.name_to_id["Nerul"]
        routes = graph.compare_routes(src_id, dst_id)
        route = routes[0]

        alt.annotate_route_with_alternatives(
            route,
            prefer_seat=True,
            threshold_minutes=35,
            fetch_board_fn=lambda c: self.boards[c],
        )

        st = route["live_alternatives_status"]
        self.assertTrue(st["applicable"])
        self.assertIn("PNVL", st["pivots_checked"])

        alts = route["live_alternatives"]
        back_alt = next((a for a in alts if a["kind"] == "back"), None)
        self.assertIsNotNone(back_alt)
        self.assertEqual(back_alt["via"], "Panvel")
        self.assertTrue(back_alt["seat"])
        self.assertIn("detour via Panvel", back_alt["note"])

    def test_boarding_at_origin_no_alternatives_needed(self):
        """When boarding station is already an origin (Panvel), no backing pivots are generated."""
        pivots = alt.find_pivots("PNVL", "VSH", "harbour")
        backing_pivots = [p for p in pivots if p["kind"] == "back"]
        self.assertEqual(backing_pivots, [])

    def test_no_train_leg_not_applicable(self):
        """Route with no train edges returns applicable=False for alternatives."""
        route = {
            "edges": [
                {"from": "Belapur CBD", "to": "RBI", "mode": "metro"},
                {"from": "RBI", "to": "Belpada", "mode": "metro"}
            ]
        }
        res = alt.annotate_route_with_alternatives(route, prefer_seat=True)
        self.assertFalse(res["live_alternatives_status"]["applicable"])
        self.assertEqual(res["live_alternatives_status"]["reason"], "no_train_leg")
        self.assertEqual(res["live_alternatives"], [])

    def test_compare_endpoint_prefer_seat(self):
        """GET /compare with prefer_seat=true returns live_alternatives."""
        src_id = self.name_to_id["Kharghar"]
        dst_id = self.name_to_id["Vashi"]
        response = self.client.get(f"/compare?source={src_id}&target={dst_id}&prefer_seat=true")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 3)
        for r in data:
            self.assertIn("live_alternatives", r)
            self.assertIn("live_alternatives_status", r)


if __name__ == "__main__":
    unittest.main()
