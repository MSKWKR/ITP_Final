"""Nominatim client: geocoding and POI candidate search.

Nominatim's usage policy requires a descriptive User-Agent and at most one
request per second. We enforce both here and cache responses in-process so that
re-running the same search during a session (and during the optimizer's repeated
lookups) doesn't hammer the public server.
"""

import threading
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ErrandRouteOptimizer/1.0 (Python class final project)"
MIN_INTERVAL_SECONDS = 1.0  # Nominatim policy: max 1 req/sec


class Place:
    """A geocoded point: a name and its latitude/longitude."""

    def __init__(self, name: str, lat: float, lon: float):
        self.name = name
        self.lat = lat
        self.lon = lon

    @property
    def coords(self) -> tuple[float, float]:
        """(lat, lon) tuple, the order Folium expects."""
        return (self.lat, self.lon)

    def __repr__(self) -> str:
        return f"Place({self.name!r}, {self.lat:.5f}, {self.lon:.5f})"


# A single shared rate-limiter + cache for the whole process. A lock keeps the
# 1-req/sec spacing correct even if Flask serves requests on multiple threads.
_rate_lock = threading.Lock()
_last_request_time = 0.0
_cache: dict[tuple, list[dict]] = {}


def _throttled_get(params: dict) -> list[dict]:
    """Perform a rate-limited, cached GET against Nominatim."""
    cache_key = tuple(sorted(params.items()))
    if cache_key in _cache:
        return _cache[cache_key]

    global _last_request_time
    with _rate_lock:
        elapsed = time.monotonic() - _last_request_time
        if elapsed < MIN_INTERVAL_SECONDS:
            time.sleep(MIN_INTERVAL_SECONDS - elapsed)

        resp = requests.get(
            NOMINATIM_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        _last_request_time = time.monotonic()

    resp.raise_for_status()
    data = resp.json()
    _cache[cache_key] = data
    return data


def geocode(address: str) -> Place:
    """Resolve a free-form address to a single Place. Raises if not found."""
    results = _throttled_get(
        {"q": address, "format": "json", "limit": 1, "addressdetails": 0}
    )
    if not results:
        raise ValueError(f"Could not geocode address: {address!r}")

    top = results[0]
    return Place(top.get("display_name", address), float(top["lat"]), float(top["lon"]))


def search_candidates(
    query: str,
    near: Place,
    limit: int = 4,
    radius_deg: float = 0.03,
) -> list[Place]:
    """Find up to `limit` POI candidates for a query near a starting point.

    `radius_deg` bounds the search to a box around `near` (~3km at 0.03°) so we
    get nearby, walkable candidates rather than matches across the whole city.
    """
    viewbox = (
        f"{near.lon - radius_deg},{near.lat + radius_deg},"
        f"{near.lon + radius_deg},{near.lat - radius_deg}"
    )
    results = _throttled_get(
        {
            "q": query,
            "format": "json",
            "limit": limit,
            "viewbox": viewbox,
            "bounded": 1,
            "addressdetails": 0,
        }
    )
    return [
        Place(r.get("display_name", query), float(r["lat"]), float(r["lon"]))
        for r in results
    ]
