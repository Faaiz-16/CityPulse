"""Build ``app/geo/jaipur_roads.json`` from an OpenStreetMap Overpass export.

The map highlights congestion along Jaipur's real main roads. Road shapes come from
OpenStreetMap (© OpenStreetMap contributors, available under the ODbL). To regenerate:

1. Download the raw roads (one request):

       curl -s https://overpass-api.de/api/interpreter --data-urlencode \\
         'data=[out:json][timeout:120];way["highway"~"^(motorway|trunk|primary|secondary)$"]
          (26.79,75.695,27.00,75.93);out geom;' -o jaipur_roads_raw.json

2. Run from ``backend/``:  ``python scripts/build_jaipur_roads.py jaipur_roads_raw.json``

Each road is simplified (Douglas–Peucker, ≈ 8 m), split at grid-cell edges and tagged with the
cell it runs through, so the map can colour each stretch by that cell's traffic.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.geo.zones import CELL_LAT, CELL_LON, COLS, GRID_NORTH, GRID_WEST, ROWS, cell_of, cell_ref  # noqa: E402

MAJOR = {"motorway", "trunk", "primary"}
KEEP = MAJOR | {"secondary"}
TOLERANCE = 0.00008  # degrees ≈ 8 m
OUT = Path(__file__).resolve().parents[1] / "app" / "geo" / "jaipur_roads.json"


def simplify(points: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    a, b = points[0], points[-1]
    best, index = 0.0, 0
    for i in range(1, len(points) - 1):
        d = _segment_distance(points[i], a, b)
        if d > best:
            best, index = d, i
    if best <= tol:
        return [a, b]
    return simplify(points[: index + 1], tol)[:-1] + simplify(points[index:], tol)


def _segment_distance(p, a, b) -> float:
    (py, px), (ay, ax), (by, bx) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def split_by_cell(points: list[tuple[float, float]]) -> list[tuple[str, list[tuple[float, float]]]]:
    """Cut a polyline wherever it crosses a grid line; return (cell, piece) runs."""
    lat_lines = [GRID_NORTH - k * CELL_LAT for k in range(ROWS + 1)]
    lon_lines = [GRID_WEST + k * CELL_LON for k in range(COLS + 1)]
    runs: list[tuple[str, list[tuple[float, float]]]] = []
    for p, q in zip(points, points[1:], strict=False):
        cuts = {0.0, 1.0}
        for lat in lat_lines:
            if (p[0] - lat) * (q[0] - lat) < 0:
                cuts.add((lat - p[0]) / (q[0] - p[0]))
        for lon in lon_lines:
            if (p[1] - lon) * (q[1] - lon) < 0:
                cuts.add((lon - p[1]) / (q[1] - p[1]))
        ts = sorted(cuts)
        for t0, t1 in zip(ts, ts[1:], strict=False):
            a = (p[0] + (q[0] - p[0]) * t0, p[1] + (q[1] - p[1]) * t0)
            b = (p[0] + (q[0] - p[0]) * t1, p[1] + (q[1] - p[1]) * t1)
            cell = cell_of((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if cell is None:
                continue
            ref = cell_ref(*cell)
            if runs and runs[-1][0] == ref and runs[-1][1][-1] == a:
                runs[-1][1].append(b)
            else:
                runs.append((ref, [a, b]))
    return runs


def main(raw_path: str) -> None:
    raw = json.loads(Path(raw_path).read_text())
    roads = []
    for el in raw["elements"]:
        kind = el.get("tags", {}).get("highway")
        if el.get("type") != "way" or kind not in KEEP or len(el.get("geometry", [])) < 2:
            continue
        pts = simplify([(g["lat"], g["lon"]) for g in el["geometry"]], TOLERANCE)
        for ref, piece in split_by_cell(pts):
            piece = simplify(piece, TOLERANCE)
            if len(piece) < 2 or math.dist(piece[0], piece[-1]) < 0.0015 and len(piece) < 3:
                continue  # drop tiny stubs at cell corners
            roads.append({
                "cell": ref, "kind": "major" if kind in MAJOR else "minor",
                "name": el["tags"].get("name", ""),
                "path": [[round(a, 5), round(b, 5)] for a, b in piece],
            })
    OUT.write_text(json.dumps({
        "source": "© OpenStreetMap contributors (ODbL) — main roads of Jaipur",
        "roads": roads,
    }, separators=(",", ":"), ensure_ascii=False))
    print(f"{len(roads)} road pieces, {sum(len(r['path']) for r in roads)} points → {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "jaipur_roads_raw.json")
