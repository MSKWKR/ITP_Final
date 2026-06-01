"""OSRM client: walking-time matrix and route polylines.

Uses the public OSRM demo server, which can be slow, so the walking-time matrix
is cached per set of coordinates. All durations are returned in minutes to match
the rest of the app.
"""

import requests

OSRM_BASE = "https://router.project-osrm.org"

# Cache matrices keyed by the rounded coordinate list, so the optimizer's repeated
# lookups and re-submitted forms reuse one network round-trip.
_matrix_cache: dict[tuple, list[list[float]]] = {}


def _coord_string(places) -> str:
    """OSRM expects lon,lat pairs separated by semicolons."""
    return ";".join(f"{p.lon},{p.lat}" for p in places)


def _cache_key(places) -> tuple:
    return tuple((round(p.lat, 6), round(p.lon, 6)) for p in places)


def walking_time_matrix(places) -> list[list[float]]:
    """Return an N×N matrix of walking durations in minutes between places.

    matrix[i][j] is the time to walk from places[i] to places[j].
    """
    if len(places) < 2:
        return [[0.0]]

    key = _cache_key(places)
    if key in _matrix_cache:
        return _matrix_cache[key]

    url = f"{OSRM_BASE}/table/v1/walking/{_coord_string(places)}"
    resp = requests.get(url, params={"annotations": "duration"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table error: {data.get('message', data.get('code'))}")

    # OSRM returns seconds; convert to minutes.
    matrix = [[(d or 0.0) / 60.0 for d in row] for row in data["durations"]]
    _matrix_cache[key] = matrix
    return matrix


def route_geometry(places) -> list[list[float]]:
    """Return the walking route through `places` as a list of [lat, lon] points.

    Suitable for handing straight to a Folium PolyLine.
    """
    if len(places) < 2:
        return [list(p.coords) for p in places]

    url = f"{OSRM_BASE}/route/v1/walking/{_coord_string(places)}"
    resp = requests.get(
        url, params={"overview": "full", "geometries": "geojson"}, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError(f"OSRM route error: {data.get('message', data.get('code'))}")

    # GeoJSON coordinates are [lon, lat]; Folium wants [lat, lon].
    coords = data["routes"][0]["geometry"]["coordinates"]
    return [[lat, lon] for lon, lat in coords]
