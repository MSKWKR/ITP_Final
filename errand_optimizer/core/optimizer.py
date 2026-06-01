"""Route optimizer.

The interesting part of this project: we don't just order a fixed set of stops.
For each errand category there are several candidate shops, so we jointly choose
*which* specific shop to use for each category *and* the order to visit them in,
minimizing total time (real OSRM walking time + per-stop visit time).

With N errands and up to K candidates each, the search space is K^N candidate
combinations × N! orderings. The brief keeps N ≤ 6, K ≤ 4 (~17k routes) so an
exhaustive search runs instantly and is guaranteed optimal.
"""

from dataclasses import dataclass
from itertools import permutations, product

from api.nominatim import Place
from core.errands import Errand


@dataclass
class Stop:
    """One chosen stop in the final route."""

    errand: Errand
    place: Place


@dataclass
class RouteResult:
    """The best route found, plus the numbers needed for the verdict panel."""

    stops: list[Stop]          # in visit order (excludes the start point)
    walking_minutes: float
    visit_minutes: float
    total_minutes: float
    fits: bool
    round_trip: bool

    @property
    def ordered_places(self) -> list[Place]:
        """Start → each stop (→ start, if round trip), for drawing the route."""
        return [s.place for s in self.stops]


@dataclass
class CandidateGroup:
    """All candidate shops found for one errand category."""

    errand: Errand
    candidates: list[Place]


def optimize(
    start: Place,
    groups: list[CandidateGroup],
    matrix: list[list[float]],
    time_budget_minutes: float,
    round_trip: bool,
) -> RouteResult:
    """Find the lowest-total-time route over all shop choices and orderings.

    `matrix` is the walking-time matrix (minutes) over the flat place list
    ``[start] + group0.candidates + group1.candidates + ...`` in that exact
    order; this function indexes into it rather than calling the network.
    """
    if not groups:
        raise ValueError("Need at least one errand to build a route.")

    # Map each candidate Place to its row/column index in `matrix`.
    index = 1  # row 0 is the start point
    group_indices: list[list[int]] = []
    for group in groups:
        if not group.candidates:
            raise ValueError(f"No candidates found for {group.errand.label}.")
        idxs = list(range(index, index + len(group.candidates)))
        group_indices.append(idxs)
        index += len(group.candidates)

    fixed_visit_minutes = sum(g.errand.visit_minutes for g in groups)

    best_total: float | None = None
    best_selection: tuple[int, ...] | None = None  # group-position -> candidate idx
    best_order: tuple[int, ...] | None = None       # permutation of group positions

    # Choose one candidate index per group, then try every visit order.
    for selection in product(*group_indices):
        for order in permutations(range(len(groups))):
            walking = matrix[0][selection[order[0]]]  # start -> first stop
            for a, b in zip(order, order[1:]):
                walking += matrix[selection[a]][selection[b]]
            if round_trip:
                walking += matrix[selection[order[-1]]][0]  # last stop -> start

            total = walking + fixed_visit_minutes
            if best_total is None or total < best_total:
                best_total = total
                best_selection = selection
                best_order = order

    assert best_selection is not None and best_order is not None

    # Rebuild the winning route as Stop objects in visit order.
    stops: list[Stop] = []
    for pos in best_order:
        group = groups[pos]
        chosen_idx = best_selection[pos]
        place = group.candidates[chosen_idx - group_indices[pos][0]]
        stops.append(Stop(errand=group.errand, place=place))

    walking_minutes = best_total - fixed_visit_minutes
    return RouteResult(
        stops=stops,
        walking_minutes=walking_minutes,
        visit_minutes=fixed_visit_minutes,
        total_minutes=best_total,
        fits=best_total <= time_budget_minutes,
        round_trip=round_trip,
    )


def farthest_stop(start: Place, result: RouteResult):
    """Pick the stop to suggest dropping when a route doesn't fit.

    Heuristic for the verdict panel: the stop farthest from the start (by
    straight-line distance) is usually the cheapest to cut. Returns its Stop, or
    None for a single-stop route.
    """
    if len(result.stops) <= 1:
        return None
    farthest = None
    worst = -1.0
    for stop in result.stops:
        d = _haversine_minutes(start, stop.place)
        if d > worst:
            worst = d
            farthest = stop
    return farthest


def _haversine_minutes(a: Place, b: Place) -> float:
    """Rough walking-time estimate (minutes) between two points.

    Only used to rank stops for the 'drop the farthest' suggestion, so a
    straight-line approximation at ~5 km/h is good enough.
    """
    from math import asin, cos, radians, sin, sqrt

    r_km = 6371.0
    dlat = radians(b.lat - a.lat)
    dlon = radians(b.lon - a.lon)
    h = sin(dlat / 2) ** 2 + cos(radians(a.lat)) * cos(radians(b.lat)) * sin(dlon / 2) ** 2
    km = 2 * r_km * asin(sqrt(h))
    return km / 5.0 * 60.0  # 5 km/h walking pace
