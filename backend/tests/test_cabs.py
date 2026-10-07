"""Unit tests for Phase E: Cab Provider Layer (Uber, Ola, Rapido, Local Auto).
Tests calibrated fare estimates, road distance/duration calculation,
deep links, and the /cabs/estimate endpoint.
"""

import unittest
from unittest import mock
from fastapi.testclient import TestClient

from app.main import app
from app import cabs


class CabProviderTests(unittest.TestCase):
    def setUp(self):
        # Vashi Railway Station: (19.0771, 72.9986)
        # Belapur CBD Railway Station: (19.0185, 73.0402)
        # Straight-line ~7.9 km, road distance ~10.3 km
        self.vashi = (19.0771, 72.9986)
        self.belapur = (19.0185, 73.0402)

    def test_haversine_distance(self):
        straight = cabs.haversine_km(self.vashi[0], self.vashi[1], self.belapur[0], self.belapur[1])
        self.assertAlmostEqual(straight, 7.9, delta=0.5)

    def test_road_distance_and_duration(self):
        road_km, duration_min = cabs.estimate_road_distance_and_duration(
            self.vashi[0], self.vashi[1], self.belapur[0], self.belapur[1]
        )
        self.assertGreater(road_km, 9.0)
        self.assertLess(road_km, 12.0)
        self.assertGreater(duration_min, 15)
        self.assertLess(duration_min, 40)

    def test_auto_rickshaw_meter_fare(self):
        # Official MMRTA fare: base ₹28 for 1.5 km, ₹18.66/km after
        estimates = cabs.AutoRickshawProvider().estimate(
            self.vashi[0], self.vashi[1], self.belapur[0], self.belapur[1]
        )
        self.assertEqual(len(estimates), 1)
        auto = estimates[0]
        self.assertEqual(auto["provider"], "Auto Rickshaw")
        self.assertEqual(auto["tier"], "Metered Auto")
        # For ~10.3 km: 28 + (8.8 * 18.66) ~ ₹192
        self.assertGreaterEqual(auto["fare_low"], 170)
        self.assertLessEqual(auto["fare_high"], 230)
        self.assertTrue(auto["estimated"])

    def test_uber_estimates_and_deeplink(self):
        estimates = cabs.UberProvider().estimate(
            self.vashi[0], self.vashi[1], self.belapur[0], self.belapur[1]
        )
        self.assertGreaterEqual(len(estimates), 2)  # Uber Auto, Uber Go, etc.
        tiers = [e["tier"] for e in estimates]
        self.assertIn("Uber Go", tiers)
        self.assertIn("Uber Auto", tiers)

        for e in estimates:
            self.assertEqual(e["provider"], "Uber")
            self.assertIn("https://m.uber.com/ul/?action=setPickup", e["deeplink"])
            self.assertIn(f"pickup[latitude]={self.vashi[0]}", e["deeplink"])
            self.assertIn(f"dropoff[latitude]={self.belapur[0]}", e["deeplink"])
            self.assertGreater(e["fare_low"], 0)
            self.assertGreaterEqual(e["fare_high"], e["fare_low"])

    def test_ola_estimates_and_deeplink(self):
        estimates = cabs.OlaProvider().estimate(
            self.vashi[0], self.vashi[1], self.belapur[0], self.belapur[1]
        )
        self.assertGreaterEqual(len(estimates), 2)
        tiers = [e["tier"] for e in estimates]
        self.assertIn("Ola Mini", tiers)

        for e in estimates:
            self.assertEqual(e["provider"], "Ola")
            self.assertIn("book.olacabs.com", e["deeplink"])
            self.assertGreater(e["fare_low"], 0)

    def test_rapido_estimates_and_deeplink(self):
        estimates = cabs.RapidoProvider().estimate(
            self.vashi[0], self.vashi[1], self.belapur[0], self.belapur[1]
        )
        tiers = [e["tier"] for e in estimates]
        self.assertIn("Rapido Bike", tiers)
        bike = next(e for e in estimates if e["tier"] == "Rapido Bike")
        # Bike is cheaper than car
        self.assertLess(bike["fare_low"], 150)
        self.assertIn("rapido://", bike["deeplink"])

    def test_aggregate_all_cabs(self):
        all_cabs = cabs.get_all_cab_estimates(
            self.vashi[0], self.vashi[1], self.belapur[0], self.belapur[1]
        )
        self.assertGreaterEqual(len(all_cabs["estimates"]), 6)
        # Should be sorted by lowest fare first
        fares = [e["fare_low"] for e in all_cabs["estimates"]]
        self.assertEqual(fares, sorted(fares))
        self.assertIn("road_distance_km", all_cabs)
        self.assertIn("duration_minutes", all_cabs)


class CabEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_cabs_endpoint_valid_coords(self):
        resp = self.client.get(
            "/cabs/estimate",
            params={
                "pickup_lat": 19.0771,
                "pickup_lng": 72.9986,
                "dropoff_lat": 19.0185,
                "dropoff_lng": 73.0402,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("estimates", data)
        self.assertGreaterEqual(len(data["estimates"]), 5)
        self.assertEqual(data["pickup"]["lat"], 19.0771)

    @mock.patch("app.main.fetch_nodes")
    def test_cabs_endpoint_with_station_ids(self, mock_fetch):
        mock_fetch.return_value = {
            1: {"name": "Vashi", "lat": 19.0632517, "lng": 72.9988553, "type": "rail"},
            6: {"name": "Belapur CBD", "lat": 19.0188208, "lng": 73.038839, "type": "rail_junction"},
        }
        # Station 1 (Vashi) -> Station 6 (Belapur CBD)
        resp = self.client.get(
            "/cabs/estimate",
            params={"source_station_id": 1, "target_station_id": 6},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["pickup"]["name"], "Vashi")
        self.assertEqual(data["dropoff"]["name"], "Belapur CBD")
        self.assertGreater(len(data["estimates"]), 0)

    def test_cabs_endpoint_missing_params_422(self):
        resp = self.client.get("/cabs/estimate")
        self.assertEqual(resp.status_code, 422)

    def test_cabs_endpoint_invalid_coord_ranges_422(self):
        # Latitude > 90 should return 422
        resp = self.client.get(
            "/cabs/estimate",
            params={
                "pickup_lat": 95.0,
                "pickup_lng": 72.9986,
                "dropoff_lat": 19.0185,
                "dropoff_lng": 73.0402,
            },
        )
        self.assertEqual(resp.status_code, 422)
