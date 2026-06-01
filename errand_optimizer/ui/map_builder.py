"""Folium map generation.

Produces the interactive Leaflet map (as an HTML fragment) embedded in the
results page: a green start marker, numbered color-coded stop markers in visit
order, and the OSRM walking polyline connecting them.
"""

import folium

from api.nominatim import Place
from core.optimizer import RouteResult

# Distinct colors cycled across stops so each numbered marker is easy to find.
_STOP_COLORS = ["blue", "purple", "orange", "darkred", "cadetblue", "darkgreen"]


def build_map(start: Place, result: RouteResult, polyline: list[list[float]]) -> str:
    """Render the route to an HTML string for ``{{ map_html|safe }}``.

    `polyline` is the OSRM walking geometry as [lat, lon] points.
    """
    fmap = folium.Map(location=list(start.coords), zoom_start=15, tiles="cartodbpositron")

    # Start point.
    folium.Marker(
        location=list(start.coords),
        tooltip="Start",
        popup="Start",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(fmap)

    # Numbered stop markers in visit order. A DivIcon lets us draw the actual
    # visit number inside a colored circle (Font Awesome has no numeric icons).
    for i, stop in enumerate(result.stops, start=1):
        color = _STOP_COLORS[(i - 1) % len(_STOP_COLORS)]
        folium.Marker(
            location=list(stop.place.coords),
            tooltip=f"{i}. {stop.errand.label}",
            popup=f"<b>{i}. {stop.errand.label}</b><br>{stop.place.name}",
            icon=folium.DivIcon(
                icon_size=(30, 30),
                icon_anchor=(15, 15),
                html=(
                    f'<div style="background:{color};color:#fff;width:30px;'
                    f'height:30px;border-radius:50%;display:flex;align-items:center;'
                    f'justify-content:center;font-weight:700;font-size:14px;'
                    f'border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)">'
                    f"{i}</div>"
                ),
            ),
        ).add_to(fmap)

    # Walking route.
    if len(polyline) >= 2:
        folium.PolyLine(
            polyline, color="#2563eb", weight=4, opacity=0.8, tooltip="Walking route"
        ).add_to(fmap)
        fmap.fit_bounds(_bounds(polyline))

    return fmap._repr_html_()


def _bounds(points: list[list[float]]) -> list[list[float]]:
    """South-west and north-east corners enclosing all points, for fit_bounds."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]
