# Errand Route Optimizer

A small Flask web app that finds the fastest **walking** route to run a set of
errands within a time budget. Given a starting address and a list of errand
categories (pharmacy, supermarket, café, …), it searches several candidate shops
per category and chooses *which* specific shops and *what order* minimizes total
time — using real street walking times, not straight-line distance.

Built as a Python class final project.

## How it works

1. **Geocode** the starting address with **Nominatim**.
2. For each chosen errand, **search ~4 candidate locations** nearby (Nominatim).
3. Build an N×N **walking-time matrix** between the start and all candidates
   with **OSRM**.
4. **Optimize**: brute-force every combination of one shop per errand × every
   visit order, scoring `walking time + per-stop visit time`. With ≤6 errands
   and ≤4 candidates each (~17k routes) this is instant and provably optimal.
5. **Render** the result: a verdict ("fits in X min" / "drop the farthest
   stop"), an ordered stop list, and a **Folium** Leaflet map with numbered
   markers and the OSRM walking polyline.

## Project layout

```
errand_optimizer/
├── app.py                  # Flask routes / pipeline wiring
├── api/
│   ├── nominatim.py        # geocoding + POI search (rate-limited, cached)
│   └── osrm.py             # walking-time matrix + route polylines
├── core/
│   ├── errands.py          # category → query map + visit-time table
│   └── optimizer.py        # permutation search over shop choices + order
├── ui/
│   ├── map_builder.py      # Folium map generation
│   ├── templates/index.html
│   └── static/style.css
├── requirements.txt
└── README.md
```

## Running it

```bash
cd errand_optimizer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5000>.

## Notes & limits

- Uses the **public** Nominatim and OSRM demo servers. Nominatim is rate-limited
  to 1 request/second (enforced in `api/nominatim.py` with a descriptive
  User-Agent, per their usage policy); both clients cache responses in-process so
  re-running a search is fast.
- The OSRM demo server can occasionally be slow or unavailable — that surfaces as
  a friendly error message rather than a crash.
- No accounts, persistence, or non-walking modes — out of scope for the demo.
