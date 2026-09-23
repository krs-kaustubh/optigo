"""Unit tests for railradar.py. No network: boards are synthetic but use the
exact shape and real train numbers/codes observed on RailRadar on 2026-09-23.

Run:  python -m unittest discover -s tests -v   (from backend/)
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("RAILRADAR_API_KEY", "test-key")

from app import railradar as rr  # noqa: E402

BOARD_TS = "2026-09-23T18:18:51+05:30"


def entry(number, name, src, dst, dep, arr=None, live_type="scheduled",
          delay=None, ttype="EMU", platform=None, expected_dep=None):
    live = {"type": live_type, "delayMinutes": delay}
    if expected_dep:
        live["expectedDepartureTime"] = expected_dep
    return {
        "train": {"number": number, "name": name, "type": ttype, "source": src, "destination": dst},
        "stop": {"arrival": arr or dep, "departure": dep, "platform": platform},
        "live": live,
    }


def board(*entries):
    return {"success": True, "data": {"trains": list(entries)}, "meta": {"timestamp": BOARD_TS}}


def route(*legs):
    """legs: (from, to, mode) -> route dict shaped like graph.shortest_path()."""
    edges = [{"from": a, "to": b, "mode": m} for a, b, m in legs]
    path = [legs[0][0]] + [b for _, b, _ in legs]
    return {"path": path, "edges": edges, "totals": {}}


# Real boards, trimmed. Arrivals that terminate at the station have dep=None.
PNVL_BOARD = board(
    entry("98175", "Mumbai CSMT - Panvel Local", "CSMT", "PNVL", None, arr="18:11", live_type="upcoming", delay=2),
    entry("99043", "Thane - Panvel Local", "TNA", "PNVL", None, arr="18:15", live_type="upcoming", delay=2),
    entry("12431", "Trivandrum - Hazrat Nizamuddin Rajdhani Express", "TVC", "NZM", "17:55",
          live_type="upcoming", delay=40, ttype="Rajdhani Express", platform="5"),
    entry("98180", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "18:14", live_type="scheduled", platform="2"),
    entry("98182", "Panvel - Vadala Road Local", "PNVL", "VDLR", "18:18", live_type="scheduled", platform="3"),
    entry("99058", "Panvel - Thane Local", "PNVL", "TNA", "18:22", live_type="scheduled", platform="3"),
    entry("98915", "Panvel - Goregoan Local", "PNVL", "GMN", "18:33", live_type="scheduled", platform="3"),
    entry("98184", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "18:37", live_type="scheduled", platform="2"),
    entry("69161", "Panvel - Dahanu Road MEMU", "PNVL", "DRD", "19:05", live_type="not-started", ttype="MEMU"),
    entry("98176", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "17:59", live_type="departed", delay=0, platform="2"),
    entry("98178", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "18:06", live_type="departed", delay=1, platform="2"),
    entry("98174", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "17:51", live_type="departed", delay=0, platform="2"),
)

BEPR_BOARD = board(
    entry("98179", "Mumbai CSMT - Panvel Special", "CSMT", "PNVL", "18:13", live_type="upcoming", delay=1, platform="1"),
    entry("98180", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "18:29", live_type="not-started"),
    entry("99045", "Thane - Panvel Local", "TNA", "PNVL", "18:31", live_type="upcoming", delay=0),
    entry("99720", "Uran - Belapur Cbd Local", "URAN", "BEPR", None, arr="19:08", live_type="not-started"),
    entry("98370", "Belapur Cbd - Mumbai CSMT Local", "BEPR", "CSMT", "18:16", live_type="scheduled"),
    entry("98353", "Mumbai CSMT - Belapur Cbd Local", "CSMT", "BEPR", None, arr="18:21", live_type="scheduled"),
    entry("99719", "Belapur Cbd - Uran Local", "BEPR", "URAN", "18:30", live_type="scheduled"),
    entry("99058", "Panvel - Thane Local", "PNVL", "TNA", "18:37", live_type="scheduled"),
    entry("98374", "Belapur Cbd - Vadala Road Local", "BEPR", "VDLR", "19:20", live_type="scheduled"),
    entry("98177", "Vadala Road - Panvel Local", "VDLR", "PNVL", "18:04", live_type="departed", delay=2),
    entry("98176", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "18:05", live_type="departed", delay=0),
)

VSH_BOARD = board(
    entry("98183", "Mumbai CSMT - Panvel Local", "CSMT", "PNVL", "18:09", live_type="departed", delay=0, platform="3"),
    entry("98176", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "18:20", live_type="upcoming", delay=0, platform="4"),
    entry("98185", "Mumbai CSMT - Panvel Local", "CSMT", "PNVL", "18:22", live_type="upcoming", delay=0, platform="3"),
    entry("98353", "Mumbai CSMT - Belapur Cbd Local", "CSMT", "BEPR", "18:12", live_type="scheduled"),
    entry("99711", "Thane - Vashi Local", "TNA", "VSH", None, arr="18:25", live_type="scheduled"),
    entry("98910", "Goregoan - Panvel Local", "GMN", "PNVL", "19:30", live_type="scheduled"),
)


def numbers(route_result):
    return [t["train_number"] for t in route_result["live_trains"]]


class TrainServesTests(unittest.TestCase):
    def test_harbour_towards_mumbai(self):
        self.assertEqual(rr.train_serves("PNVL", "CSMT", "PNVL", "VSH"), "harbour")
        self.assertEqual(rr.train_serves("BEPR", "VDLR", "BEPR", "VSH"), "harbour")

    def test_harbour_towards_panvel(self):
        self.assertEqual(rr.train_serves("CSMT", "PNVL", "VSH", "PNVL"), "harbour")
        self.assertEqual(rr.train_serves("GMN", "PNVL", "VSH", "KHAG"), "harbour")

    def test_wrong_direction_excluded(self):
        self.assertIsNone(rr.train_serves("PNVL", "CSMT", "VSH", "PNVL"))
        self.assertIsNone(rr.train_serves("CSMT", "PNVL", "PNVL", "VSH"))

    def test_terminating_before_alighting_excluded(self):
        self.assertIsNone(rr.train_serves("CSMT", "BEPR", "VSH", "PNVL"))
        self.assertEqual(rr.train_serves("CSMT", "BEPR", "VSH", "BEPR"), "harbour")

    def test_terminating_at_boarding_excluded(self):
        self.assertIsNone(rr.train_serves("CSMT", "PNVL", "PNVL", "VSH"))
        self.assertIsNone(rr.train_serves("URAN", "BEPR", "BEPR", "KHAG"))

    def test_trans_harbour_skips_sanpada_and_vashi(self):
        self.assertIsNone(rr.train_serves("PNVL", "TNA", "PNVL", "VSH"))
        self.assertIsNone(rr.train_serves("PNVL", "TNA", "PNVL", "SNCR"))
        self.assertEqual(rr.train_serves("PNVL", "TNA", "PNVL", "NEU"), "trans-harbour")
        self.assertEqual(rr.train_serves("TNA", "PNVL", "JNJ", "KHAG"), "trans-harbour")

    def test_thane_vashi_serves_sanpada_only(self):
        self.assertEqual(rr.train_serves("TNA", "VSH", "SNCR", "VSH"), "trans-harbour-vashi")
        self.assertIsNone(rr.train_serves("TNA", "VSH", "JNJ", "VSH"))

    def test_uran_branches(self):
        self.assertEqual(rr.train_serves("BEPR", "URAN", "BEPR", "KARP"), "uran-belapur")
        self.assertEqual(rr.train_serves("NEU", "URAN", "NEU", "KARP"), "uran-nerul")
        self.assertEqual(rr.train_serves("NEU", "URAN", "SWDK", "TRGR"), "uran-nerul")
        self.assertIsNone(rr.train_serves("BEPR", "URAN", "NEU", "KARP"))
        self.assertIsNone(rr.train_serves("BEPR", "URAN", "BEPR", "KHAG"))

    def test_unknown_termini_excluded(self):
        self.assertIsNone(rr.train_serves("TVC", "NZM", "PNVL", "VSH"))
        self.assertIsNone(rr.train_serves("PNVL", "DRD", "PNVL", "VSH"))


class FirstTrainLegTests(unittest.TestCase):
    def test_no_train_leg(self):
        r = route(("Belapur CBD", "RBI", "metro"), ("RBI", "Belpada", "metro"))
        self.assertIsNone(rr.first_train_leg(r))

    def test_single_corridor_segment(self):
        r = route(("Panvel", "Khandeshwar", "train"), ("Khandeshwar", "Mansarovar", "train"),
                  ("Mansarovar", "Kharghar", "train"), ("Kharghar", "Belpada", "walking"))
        self.assertEqual(rr.first_train_leg(r), ("Panvel", "Kharghar", "harbour"))

    def test_alight_is_end_of_train_segment_not_route(self):
        r = route(("Vashi", "Sanpada", "train"), ("Sanpada", "Juinagar", "train"),
                  ("Juinagar", "Nerul", "train"), ("Nerul", "Seawoods-Darave", "train"),
                  ("Seawoods-Darave", "Belapur CBD", "train"), ("Belapur CBD", "RBI", "metro"),
                  ("RBI", "Belpada", "metro"), ("Belpada", "Kharghar", "walking"),
                  ("Kharghar", "Panvel", "train"))
        self.assertEqual(rr.first_train_leg(r), ("Vashi", "Belapur CBD", "harbour"))

    def test_segment_crossing_corridors_stops_at_interchange(self):
        r = route(("Vashi", "Sanpada", "train"), ("Sanpada", "Juinagar", "train"),
                  ("Juinagar", "Nerul", "train"), ("Nerul", "Seawoods-Darave", "train"),
                  ("Seawoods-Darave", "Sagar Sangam", "train"), ("Sagar Sangam", "Targhar", "train"),
                  ("Targhar", "Bamandongri", "train"), ("Bamandongri", "Kharkopar", "train"))
        self.assertEqual(rr.first_train_leg(r), ("Vashi", "Seawoods-Darave", "harbour"))

    def test_uran_segment(self):
        r = route(("Belapur CBD", "Sagar Sangam", "train"), ("Sagar Sangam", "Targhar", "train"),
                  ("Targhar", "Bamandongri", "train"), ("Bamandongri", "Kharkopar", "train"))
        self.assertEqual(rr.first_train_leg(r), ("Belapur CBD", "Kharkopar", "uran-belapur"))


class AnnotateTests(unittest.TestCase):
    def setUp(self):
        rr.clear_board_cache()
        self.boards = {"PNVL": PNVL_BOARD, "BEPR": BEPR_BOARD, "VSH": VSH_BOARD}
        self.fetch = mock.patch.object(rr, "get_station_live_board",
                                       side_effect=lambda code, hours=2, use_cache=True: self.boards[code])
        self.fetch.start()
        self.addCleanup(self.fetch.stop)

    def harbour(self, a, b):
        stations = ["Vashi", "Sanpada", "Juinagar", "Nerul", "Seawoods-Darave", "Belapur CBD",
                    "Kharghar", "Mansarovar", "Khandeshwar", "Panvel"]
        i, j = stations.index(a), stations.index(b)
        seq = stations[i:j + 1] if i < j else stations[j:i + 1][::-1]
        return route(*[(x, y, "train") for x, y in zip(seq, seq[1:])])

    def test_panvel_to_vashi_only_mumbai_bound_departures(self):
        r = rr.annotate_route_with_live_status(self.harbour("Panvel", "Vashi"), limit=3)
        # last 2 departed by time, then first 3 upcoming by time
        self.assertEqual(numbers(r), ["98176", "98178", "98180", "98182", "98915"])
        self.assertEqual(r["live_status"]["reason"], "ok")
        self.assertEqual(r["live_status"]["boarding_code"], "PNVL")
        self.assertEqual(r["live_status"]["alighting_code"], "VSH")
        self.assertEqual(r["live_status"]["not_suburban"], 2)
        for t in r["live_trains"]:
            self.assertIn(t["destination_code"], {"CSMT", "VDLR", "GMN"})
            self.assertEqual(t["line"], "harbour")

    def test_panvel_to_nerul_includes_thane_trains(self):
        r = rr.annotate_route_with_live_status(self.harbour("Panvel", "Nerul"), limit=10)
        self.assertIn("99058", numbers(r))
        self.assertNotIn("99043", numbers(r))  # arrival from Thane, terminates here

    def test_vashi_to_panvel_excludes_wrong_direction_and_short_turn(self):
        r = rr.annotate_route_with_live_status(self.harbour("Vashi", "Panvel"), limit=5)
        self.assertEqual(numbers(r), ["98183", "98185", "98910"])
        self.assertNotIn("98176", numbers(r))  # Panvel -> CSMT, wrong way
        self.assertNotIn("98353", numbers(r))  # terminates at Belapur
        self.assertNotIn("99711", numbers(r))  # Thane -> Vashi, terminates here

    def test_vashi_to_belapur_includes_short_turn(self):
        r = rr.annotate_route_with_live_status(self.harbour("Vashi", "Belapur CBD"), limit=5)
        self.assertIn("98353", numbers(r))

    def test_belapur_to_kharkopar_uran_only(self):
        r = route(("Belapur CBD", "Sagar Sangam", "train"), ("Sagar Sangam", "Targhar", "train"),
                  ("Targhar", "Bamandongri", "train"), ("Bamandongri", "Kharkopar", "train"))
        r = rr.annotate_route_with_live_status(r, limit=5)
        self.assertEqual(numbers(r), ["99719"])
        self.assertEqual(r["live_trains"][0]["line"], "uran-belapur")
        self.assertEqual(r["live_trains"][0]["towards"], "Uran")

    def test_belapur_to_vashi_mumbai_bound_only(self):
        r = rr.annotate_route_with_live_status(self.harbour("Belapur CBD", "Vashi"), limit=5)
        # sorted by departure: 18:05 departed, then 18:16, 18:29, 19:20
        self.assertEqual(numbers(r), ["98176", "98370", "98180", "98374"])

    def test_train_then_walk_then_metro_uses_train_alighting_station(self):
        r = route(("Belapur CBD", "Kharghar", "train"), ("Kharghar", "Belpada", "walking"),
                  ("Belpada", "Utsav Chowk", "metro"))
        r = rr.annotate_route_with_live_status(r, limit=5)
        self.assertEqual(r["live_status"]["alighting_station"], "Kharghar")
        self.assertEqual(numbers(r), ["98177", "98179", "99045"])

    def test_all_metro_not_applicable(self):
        r = route(("Belapur CBD", "RBI", "metro"), ("RBI", "Belpada", "metro"))
        r = rr.annotate_route_with_live_status(r)
        self.assertEqual(r["live_trains"], [])
        self.assertEqual(r["live_status"], {"applicable": False, "reason": "no_train_leg"})

    def test_sagar_sangam_boarding_not_in_railradar(self):
        r = route(("Sagar Sangam", "Targhar", "train"))
        r = rr.annotate_route_with_live_status(r)
        self.assertEqual(r["live_status"]["reason"], "station_not_in_railradar")
        self.assertTrue(r["live_status"]["applicable"])

    def test_fetch_failure_is_reported_not_silent(self):
        self.fetch.stop()
        with mock.patch.object(rr, "get_station_live_board", side_effect=rr.requests.HTTPError("429")):
            r = rr.annotate_route_with_live_status(self.harbour("Panvel", "Vashi"))
        self.fetch.start()
        self.assertEqual(r["live_trains"], [])
        self.assertEqual(r["live_status"]["reason"], "fetch_failed")
        self.assertEqual(r["live_status"]["error"], "HTTPError")

    def test_entry_shape_and_time_fields(self):
        r = rr.annotate_route_with_live_status(self.harbour("Panvel", "Vashi"), limit=1)
        t = r["live_trains"][-1]
        self.assertEqual(set(t), {"train_number", "route_name", "towards", "destination_code", "line",
                                  "departure_time", "expected_departure", "platform", "status",
                                  "delay_minutes"})
        self.assertEqual(t["departure_time"], "18:14")
        self.assertEqual(t["expected_departure"], "2026-09-23T18:14:00+05:30")
        self.assertIsNone(t["delay_minutes"])  # scheduled trains report null, not 0

    def test_sorting_uses_expected_time_over_board_order(self):
        late_first = board(
            entry("B", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "18:40", live_type="upcoming", delay=10,
                  expected_dep="2026-09-23T18:50:00+05:30"),
            entry("A", "Panvel - Mumbai CSMT Local", "PNVL", "CSMT", "18:45", live_type="scheduled"),
        )
        self.boards["PNVL"] = late_first
        r = rr.annotate_route_with_live_status(self.harbour("Panvel", "Vashi"), limit=5)
        self.assertEqual(numbers(r), ["A", "B"])


class CacheTests(unittest.TestCase):
    def setUp(self):
        rr.clear_board_cache()

    def test_board_fetched_once_within_ttl(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = PNVL_BOARD
        with mock.patch.object(rr.requests, "get", return_value=resp) as get:
            rr.get_station_live_board("PNVL")
            rr.get_station_live_board("PNVL")
            rr.get_station_live_board("VSH")
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args.kwargs["params"], {"hours": 2})

    def test_missing_key_raises(self):
        with mock.patch.object(rr, "RAILRADAR_KEY", ""):
            with self.assertRaises(RuntimeError):
                rr.get_station_live_board("PNVL")


if __name__ == "__main__":
    unittest.main()
