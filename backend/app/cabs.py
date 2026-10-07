"""Cab Provider Layer for Navi Mumbai / Mumbai Metropolitan Region.

Provides calibrated fare matrix estimates and universal one-tap deep links
for Uber, Ola, Rapido, and metered Auto Rickshaw.
"""

from abc import ABC, abstractmethod
import math
from typing import Optional


# Earth radius in kilometers
EARTH_RADIUS_KM = 6371.0

# Road tortuosity factor: accounts for urban street grid winding vs straight line
ROAD_TORTUOSITY_FACTOR = 1.30

# Average urban driving speed (km/h) including traffic lights and congestion
URBAN_SPEED_KMH = 25.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance between two GPS coordinates in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def estimate_road_distance_and_duration(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> tuple[float, int]:
    """Calculate estimated road distance (km) and driving duration (minutes)."""
    straight_km = haversine_km(lat1, lon1, lat2, lon2)
    road_km = round(straight_km * ROAD_TORTUOSITY_FACTOR, 2)
    # Base 3 mins for pickup/junction delays + travel time
    duration_min = max(5, round((road_km / URBAN_SPEED_KMH) * 60) + 3)
    return road_km, duration_min


class CabProvider(ABC):
    """Abstract base class for ride-hailing / cab providers."""

    @abstractmethod
    def estimate(
        self, pickup_lat: float, pickup_lng: float, dropoff_lat: float, dropoff_lng: float
    ) -> list[dict]:
        """Return list of estimate dicts for this provider's vehicle tiers."""
        pass


class AutoRickshawProvider(CabProvider):
    """Official MMRTA metered auto rickshaw for Navi Mumbai / Mumbai."""

    def estimate(
        self, pickup_lat: float, pickup_lng: float, dropoff_lat: float, dropoff_lng: float
    ) -> list[dict]:
        road_km, duration_min = estimate_road_distance_and_duration(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
        )

        # Official MMRTA fare: ₹28 base for first 1.5 km, ₹18.66 per km after
        if road_km <= 1.5:
            base_fare = 28.0
        else:
            base_fare = 28.0 + (road_km - 1.5) * 18.66

        low = round(base_fare * 0.95)
        high = round(base_fare * 1.10)

        return [
            {
                "provider": "Auto Rickshaw",
                "tier": "Metered Auto",
                "category": "auto",
                "fare_low": low,
                "fare_high": high,
                "currency": "INR",
                "eta_minutes": 3,
                "duration_minutes": duration_min,
                "deeplink": f"geo:{pickup_lat},{pickup_lng}?q=auto+stand",
                "estimated": True,
                "note": "Official MMRTA meter rate (₹28 base + ₹18.66/km). Street hail / auto stand.",
            }
        ]


class UberProvider(CabProvider):
    """Uber India (Uber Auto, Uber Go, Uber Premier) with universal deep links."""

    def estimate(
        self, pickup_lat: float, pickup_lng: float, dropoff_lat: float, dropoff_lng: float
    ) -> list[dict]:
        road_km, duration_min = estimate_road_distance_and_duration(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
        )

        deeplink = (
            f"https://m.uber.com/ul/?action=setPickup&client_id=optigo"
            f"&pickup[latitude]={pickup_lat}&pickup[longitude]={pickup_lng}"
            f"&dropoff[latitude]={dropoff_lat}&dropoff[longitude]={dropoff_lng}"
        )

        # 1. Uber Auto
        auto_base = 30.0 + (road_km * 16.0) + (duration_min * 1.5)
        auto_fare = max(40.0, auto_base)

        # 2. Uber Go (Hatchback)
        go_base = 60.0 + (road_km * 15.0) + (duration_min * 1.8)
        go_fare = max(85.0, go_base)

        # 3. Uber Premier (Sedan)
        premier_base = 80.0 + (road_km * 19.0) + (duration_min * 2.2)
        premier_fare = max(120.0, premier_base)

        return [
            {
                "provider": "Uber",
                "tier": "Uber Auto",
                "category": "auto",
                "fare_low": round(auto_fare),
                "fare_high": round(auto_fare * 1.15),
                "currency": "INR",
                "eta_minutes": 4,
                "duration_minutes": duration_min,
                "deeplink": deeplink,
                "estimated": True,
                "note": "Affordable doorstep 3-wheeler auto.",
            },
            {
                "provider": "Uber",
                "tier": "Uber Go",
                "category": "cab_mini",
                "fare_low": round(go_fare),
                "fare_high": round(go_fare * 1.18),
                "currency": "INR",
                "eta_minutes": 5,
                "duration_minutes": duration_min,
                "deeplink": deeplink,
                "estimated": True,
                "note": "Comfortable AC compact hatchback (WagonR, Indica).",
            },
            {
                "provider": "Uber",
                "tier": "Uber Premier",
                "category": "cab_sedan",
                "fare_low": round(premier_fare),
                "fare_high": round(premier_fare * 1.20),
                "currency": "INR",
                "eta_minutes": 6,
                "duration_minutes": duration_min,
                "deeplink": deeplink,
                "estimated": True,
                "note": "Spacious premium sedan (Dzire, Etios) with top-rated drivers.",
            },
        ]


class OlaProvider(CabProvider):
    """Ola Cabs (Ola Auto, Ola Mini, Ola Prime Sedan)."""

    def estimate(
        self, pickup_lat: float, pickup_lng: float, dropoff_lat: float, dropoff_lng: float
    ) -> list[dict]:
        road_km, duration_min = estimate_road_distance_and_duration(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
        )

        deeplink = (
            f"https://book.olacabs.com/?lat={pickup_lat}&lng={pickup_lng}"
            f"&drop_lat={dropoff_lat}&drop_lng={dropoff_lng}"
        )

        # 1. Ola Auto
        auto_base = 30.0 + (road_km * 15.5) + (duration_min * 1.5)
        auto_fare = max(40.0, auto_base)

        # 2. Ola Mini
        mini_base = 60.0 + (road_km * 14.5) + (duration_min * 1.8)
        mini_fare = max(80.0, mini_base)

        # 3. Ola Prime Sedan
        prime_base = 85.0 + (road_km * 18.5) + (duration_min * 2.2)
        prime_fare = max(115.0, prime_base)

        return [
            {
                "provider": "Ola",
                "tier": "Ola Auto",
                "category": "auto",
                "fare_low": round(auto_fare),
                "fare_high": round(auto_fare * 1.15),
                "currency": "INR",
                "eta_minutes": 4,
                "duration_minutes": duration_min,
                "deeplink": deeplink,
                "estimated": True,
                "note": "Doorstep auto with OTP verification.",
            },
            {
                "provider": "Ola",
                "tier": "Ola Mini",
                "category": "cab_mini",
                "fare_low": round(mini_fare),
                "fare_high": round(mini_fare * 1.18),
                "currency": "INR",
                "eta_minutes": 5,
                "duration_minutes": duration_min,
                "deeplink": deeplink,
                "estimated": True,
                "note": "Pocket-friendly AC hatchback.",
            },
            {
                "provider": "Ola",
                "tier": "Ola Prime Sedan",
                "category": "cab_sedan",
                "fare_low": round(prime_fare),
                "fare_high": round(prime_fare * 1.20),
                "currency": "INR",
                "eta_minutes": 7,
                "duration_minutes": duration_min,
                "deeplink": deeplink,
                "estimated": True,
                "note": "Top sedans with free in-cab Wi-Fi.",
            },
        ]


class RapidoProvider(CabProvider):
    """Rapido (Rapido Bike Taxi and Rapido Auto)."""

    def estimate(
        self, pickup_lat: float, pickup_lng: float, dropoff_lat: float, dropoff_lng: float
    ) -> list[dict]:
        road_km, duration_min = estimate_road_distance_and_duration(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
        )

        deeplink = (
            f"rapido://ride?pickup_lat={pickup_lat}&pickup_lng={pickup_lng}"
            f"&drop_lat={dropoff_lat}&drop_lng={dropoff_lng}"
        )

        # 1. Rapido Bike (faster through traffic, ~15% shorter duration)
        bike_duration = max(4, round(duration_min * 0.85))
        bike_base = 25.0 + (road_km * 9.0) + (bike_duration * 1.0)
        bike_fare = max(35.0, bike_base)

        # 2. Rapido Auto
        auto_base = 30.0 + (road_km * 15.0) + (duration_min * 1.5)
        auto_fare = max(38.0, auto_base)

        return [
            {
                "provider": "Rapido",
                "tier": "Rapido Bike",
                "category": "bike",
                "fare_low": round(bike_fare),
                "fare_high": round(bike_fare * 1.12),
                "currency": "INR",
                "eta_minutes": 3,
                "duration_minutes": bike_duration,
                "deeplink": deeplink,
                "estimated": True,
                "note": "Fast, solo bike taxi for beating peak-hour traffic.",
            },
            {
                "provider": "Rapido",
                "tier": "Rapido Auto",
                "category": "auto",
                "fare_low": round(auto_fare),
                "fare_high": round(auto_fare * 1.15),
                "currency": "INR",
                "eta_minutes": 4,
                "duration_minutes": duration_min,
                "deeplink": deeplink,
                "estimated": True,
                "note": "Standard auto with low commission rates.",
            },
        ]


PROVIDERS: list[CabProvider] = [
    AutoRickshawProvider(),
    UberProvider(),
    OlaProvider(),
    RapidoProvider(),
]


def get_all_cab_estimates(
    pickup_lat: float,
    pickup_lng: float,
    dropoff_lat: float,
    dropoff_lng: float,
    pickup_name: Optional[str] = None,
    dropoff_name: Optional[str] = None,
) -> dict:
    """Aggregate estimates from all providers, sorted by lowest fare."""
    road_km, duration_min = estimate_road_distance_and_duration(
        pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
    )

    all_estimates = []
    for provider in PROVIDERS:
        try:
            all_estimates.extend(
                provider.estimate(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
            )
        except Exception:
            pass

    # Sort estimates by lowest fare first
    all_estimates.sort(key=lambda x: x["fare_low"])

    return {
        "pickup": {
            "name": pickup_name or "Pickup Location",
            "lat": pickup_lat,
            "lng": pickup_lng,
        },
        "dropoff": {
            "name": dropoff_name or "Dropoff Location",
            "lat": dropoff_lat,
            "lng": dropoff_lng,
        },
        "road_distance_km": road_km,
        "duration_minutes": duration_min,
        "estimates_count": len(all_estimates),
        "estimates": all_estimates,
        "disclaimer": (
            "Fares and ETAs are calibrated models based on official MMRTA meter rates and "
            "published provider base rates. Tapping a deep link opens the provider app "
            "with pickup and dropoff preloaded to view live surge and book directly."
        ),
    }
