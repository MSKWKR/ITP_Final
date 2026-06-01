"""Flask entry point for the Errand Route Optimizer.

Wires the pieces together: the form posts a start address, chosen errands, a time
budget, and a round-trip toggle; we geocode, fetch candidates, build a walking
matrix, optimize, draw the map, and render the verdict.
"""

from flask import Flask, render_template, request

from api import nominatim, osrm
from core import errands as errands_mod
from core.errands import get_errand
from core.optimizer import CandidateGroup, farthest_stop, optimize
from ui.map_builder import build_map

app = Flask(__name__, template_folder="ui/templates", static_folder="ui/static")

CANDIDATES_PER_ERRAND = 4
MAX_ERRANDS = 6


@app.route("/", methods=["GET", "POST"])
def index():
    context = {
        "errands": errands_mod.all_errands(),
        "max_errands": MAX_ERRANDS,
        # Sticky form defaults / previous submission.
        "form": {"address": "", "budget": 45, "round_trip": True, "selected": []},
    }

    if request.method == "GET":
        return render_template("index.html", **context)

    # --- Parse and validate the form ----------------------------------------
    address = request.form.get("address", "").strip()
    selected = request.form.getlist("errands")
    round_trip = request.form.get("round_trip") == "on"
    try:
        budget = int(request.form.get("budget", 45))
    except ValueError:
        budget = 45

    context["form"] = {
        "address": address,
        "budget": budget,
        "round_trip": round_trip,
        "selected": selected,
    }

    if not address:
        context["error"] = "Please enter a starting address."
        return render_template("index.html", **context)
    if not selected:
        context["error"] = "Please choose at least one errand."
        return render_template("index.html", **context)
    if len(selected) > MAX_ERRANDS:
        context["error"] = f"Please choose at most {MAX_ERRANDS} errands."
        return render_template("index.html", **context)

    # --- Run the pipeline ----------------------------------------------------
    try:
        start = nominatim.geocode(address)

        groups: list[CandidateGroup] = []
        for key in selected:
            errand = get_errand(key)
            candidates = nominatim.search_candidates(
                errand.query, start, limit=CANDIDATES_PER_ERRAND
            )
            if not candidates:
                context["error"] = (
                    f"No {errand.label} found near that address. "
                    "Try a different address or remove that errand."
                )
                return render_template("index.html", **context)
            groups.append(CandidateGroup(errand=errand, candidates=candidates))

        # Flat place list: start first, then every candidate, in group order.
        flat_places = [start]
        for g in groups:
            flat_places.extend(g.candidates)

        matrix = osrm.walking_time_matrix(flat_places)
        result = optimize(start, groups, matrix, budget, round_trip)

        # Draw the chosen route via OSRM geometry.
        route_points = [start] + result.ordered_places
        if round_trip:
            route_points.append(start)
        polyline = osrm.route_geometry(route_points)
        map_html = build_map(start, result, polyline)

    except Exception as exc:  # surface a friendly message rather than a 500 page
        context["error"] = f"Something went wrong: {exc}"
        return render_template("index.html", **context)

    context.update(
        {
            "result": result,
            "map_html": map_html,
            "start_name": start.name,
            "drop_suggestion": None if result.fits else farthest_stop(start, result),
        }
    )
    return render_template("index.html", **context)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
