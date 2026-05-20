from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt


@dataclass(frozen=True)
class TunisiaRegion:
    name: str
    lat: float
    lon: float


REGIONS: list[TunisiaRegion] = [
    TunisiaRegion("Sfax", 34.7406, 10.7603),
    TunisiaRegion("Sousse", 35.8256, 10.6084),
    TunisiaRegion("Mahdia", 35.5047, 11.0622),
    TunisiaRegion("Kairouan", 35.6781, 10.0963),
    TunisiaRegion("Bizerte", 37.2744, 9.8739),
    TunisiaRegion("Zaghouan", 36.4029, 10.1429),
    TunisiaRegion("Sidi Bouzid", 35.0382, 9.4858),
    TunisiaRegion("Nabeul", 36.4513, 10.7357),
    TunisiaRegion("Gabes", 33.8815, 10.0982),
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return r * c


def nearest_region(latitude: float, longitude: float) -> dict[str, float | str]:
    if not REGIONS:
        return {"region": "Unknown", "distance_km": 0.0}

    nearest = min(REGIONS, key=lambda r: _haversine_km(latitude, longitude, r.lat, r.lon))
    distance = _haversine_km(latitude, longitude, nearest.lat, nearest.lon)
    return {"region": nearest.name, "distance_km": round(distance, 2)}


def list_regions() -> list[dict[str, float | str]]:
    return [{"name": r.name, "latitude": r.lat, "longitude": r.lon} for r in REGIONS]
