"""Tests for Phase B: Local train correctness and edge cases.
Uses real live-batch-1 fixtures and tests ghost trains, midnight wrap,
tz normalization, parse failure isolation, and rate-limiting.
"""

import json
import os
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import mock

os.environ.setdefault("RAILRADAR_API_KEY", "test-key")

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


class PhaseBJourneysTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boards = load_fixture_boards()
        cls.fixture_nodes, cls.fixture_edges = load_graph_fixtures()
        cls.name_to_id = {v["name"]: k for k, v in cls.fixture_nodes.items()}

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

    def _test_journey(self, src_name, dst_name, expected_line):
        src_id = self.name_to_id[src_name]
        dst_id = self.name_to_id[dst_name]
        routes = graph.compare_routes(src_id, dst_id)
        route = routes[0]
        rr.annotate_route_with_live_status(route, limit=5)
        st = route["live_status"]
        self.assertTrue(st["applicable"])
        self.assertEqual(st["reason"], "ok")
        self.assertEqual(st["line"], expected_line)
        self.assertGreater(len(route["live_trains"]), 0)
        return route

    def test_panvel_to_vashi(self):
        self._test_journey("Panvel", "Vashi", "harbour")

    def test_vashi_to_panvel(self):
        self._test_journey("Vashi", "Panvel", "harbour")

    def test_belapur_to_kharkopar(self):
        self._test_journey("Belapur CBD", "Kharkopar", "uran-belapur")

    def test_kharkopar_to_belapur(self):
        self._test_journey("Kharkopar", "Belapur CBD", "uran-belapur")

    def test_nerul_to_kharkopar(self):
        self._test_journey("Nerul", "Kharkopar", "uran-nerul")

    def test_seawoods_to_kharkopar(self):
        self._test_journey("Seawoods-Darave", "Kharkopar", "uran-nerul")

    def test_kharghar_to_vashi(self):
        self._test_journey("Kharghar", "Vashi", "harbour")

    def test_khandeshwar_to_nerul(self):
        self._test_journey("Khandeshwar", "Nerul", "harbour")


class PhaseBBugFixesTests(unittest.TestCase):
    def test_ghost_train_past_departure_classified_as_departed(self):
        """Train scheduled in past (beyond grace period) must be classified as departed, not upcoming."""
        board = {
            "meta": {"timestamp": "2026-10-05T18:30:00+05:30"},
            "data": {
                "trains": [
                    {
                        "train": {"number": "11111", "name": "Past Local", "type": "EMU", "source": "PNVL", "destination": "CSMT"},
                        "stop": {"departure": "18:20", "platform": "2"},
                        "live": {"type": "scheduled"}
                    },
                    {
                        "train": {"number": "22222", "name": "Future Local", "type": "EMU", "source": "PNVL", "destination": "CSMT"},
                        "stop": {"departure": "18:40", "platform": "2"},
                        "live": {"type": "scheduled"}
                    }
                ]
            }
        }
        selected, stats = rr.select_relevant_trains(board, "PNVL", "VSH", limit=3)
        train_map = {t["train_number"]: t for t in selected}
        self.assertIn("11111", train_map)
        self.assertEqual(train_map["11111"]["status"], "departed")
        self.assertEqual(train_map["22222"]["status"], "scheduled")

    def test_symmetric_midnight_wrap(self):
        """When board time is 00:10 and train departure is 23:50, it is 20 min in the past, not 23h40m in the future."""
        board_time = datetime(2026, 10, 6, 0, 10, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        stop = {"departure": "23:50"}
        live = {}
        dt = rr._departure_datetime(stop, live, board_time)
        self.assertEqual(dt.day, 5)
        self.assertEqual(dt.hour, 23)
        self.assertEqual(dt.minute, 50)
        self.assertEqual(board_time - dt, timedelta(minutes=20))

    def test_timezone_naive_and_aware_sorting_no_crash(self):
        """Offset-naive expectedDepartureTime should not cause TypeError when sorted with offset-aware datetimes."""
        board = {
            "meta": {"timestamp": "2026-10-05T18:30:00+05:30"},
            "data": {
                "trains": [
                    {
                        "train": {"number": "99991", "name": "Naive Time Local", "type": "EMU", "source": "PNVL", "destination": "CSMT"},
                        "stop": {"departure": "18:35"},
                        "live": {"type": "upcoming", "expectedDepartureTime": "2026-10-05T18:35:00"}
                    },
                    {
                        "train": {"number": "99992", "name": "Aware Time Local", "type": "EMU", "source": "PNVL", "destination": "CSMT"},
                        "stop": {"departure": "18:40"},
                        "live": {"type": "upcoming", "expectedDepartureTime": "2026-10-05T18:40:00+05:30"}
                    }
                ]
            }
        }
        selected, stats = rr.select_relevant_trains(board, "PNVL", "VSH", limit=3)
        self.assertEqual(len(selected), 2)

    def test_parse_failure_isolated(self):
        """Malformed item in board does not cause uncaught 500 in annotate_route_with_live_status."""
        bad_board = {"meta": {"timestamp": "invalid"}, "data": "not-a-dict"}
        with mock.patch.object(rr, "get_station_live_board", return_value=bad_board):
            route = {
                "edges": [{"from": "Panvel", "to": "Khandeshwar", "mode": "train"}]
            }
            res = rr.annotate_route_with_live_status(route)
            self.assertEqual(res["live_trains"], [])
            self.assertIn(res["live_status"]["reason"], ("no_relevant_trains", "parse_failed", "fetch_failed"))


if __name__ == "__main__":
    unittest.main()
