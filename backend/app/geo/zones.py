"""Jaipur as a 9 × 9 grid of demonstration areas, plus simple geometry helpers.

The city is divided into 81 square cells of about 2.5 km × 2.5 km. Columns A–I run west → east
and rows 1–9 run north → south, like a paper city map: the Walled City is **F4**. Every cell is
an area in its own right — it has its own sensors, its own baselines and its own status.

Each cell is named after the best-known locality inside it; cells with no well-known locality
are called "Near <closest locality>". Cells are **demonstration areas**, not official wards.

Main-road shapes come from OpenStreetMap (© OpenStreetMap contributors, ODbL) — see
``jaipur_roads.json`` and ``scripts/build_jaipur_roads.py``. Traffic sensors sit on those roads.

Coordinates are (lat, lon). GeoJSON output uses (lon, lat) as the spec requires.
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

# ------------------------------------------------------------------ the grid

GRID_NORTH, GRID_WEST = 26.996, 75.692  # top-left corner
CELL_LAT, CELL_LON = 0.0225, 0.0252  # ≈ 2.5 km each way at Jaipur's latitude
ROWS = COLS = 9
COL_LETTERS = "ABCDEFGHI"
GRID_SOUTH = GRID_NORTH - ROWS * CELL_LAT
GRID_EAST = GRID_WEST + COLS * CELL_LON
CITY_CENTER = ((GRID_NORTH + GRID_SOUTH) / 2, (GRID_WEST + GRID_EAST) / 2)

# Well-known localities (lat, lon). Earlier entries win when two fall in the same cell.
LOCALITIES: tuple[tuple[str, float, float], ...] = (
    ("Walled City", 26.9239, 75.8267), ("Amer", 26.9855, 75.8513), ("Jal Mahal", 26.9535, 75.8462),
    ("Nahargarh Hills", 26.9373, 75.8155), ("C-Scheme", 26.9070, 75.8070), ("Raja Park", 26.9000, 75.8300),
    ("Malviya Nagar", 26.8540, 75.8200), ("Mansarovar", 26.8580, 75.7650), ("Vaishali Nagar", 26.9110, 75.7430),
    ("Jhotwara", 26.9430, 75.7400), ("Vidhyadhar Nagar", 26.9600, 75.7800), ("Sanganer", 26.8200, 75.7900),
    ("Airport", 26.8242, 75.8122), ("Jagatpura", 26.8300, 75.8600), ("Pratap Nagar", 26.8030, 75.8200),
    ("Durgapura", 26.8500, 75.7950), ("Gopalpura", 26.8700, 75.7900), ("Tonk Phatak", 26.8800, 75.8000),
    ("Jawahar Nagar", 26.8870, 75.8340), ("Sodala", 26.9020, 75.7740), ("Civil Lines", 26.9050, 75.7920),
    ("Bani Park", 26.9310, 75.7930), ("Shastri Nagar", 26.9450, 75.7920), ("Murlipura", 26.9570, 75.7560),
    ("VKI Industrial Area", 26.9870, 75.7700), ("Galta Ji", 26.9166, 75.8585), ("Transport Nagar", 26.9230, 75.8500),
    ("Heerapura", 26.8830, 75.7240), ("Bhankrota", 26.8700, 75.6960), ("Chitrakoot", 26.9000, 75.7280),
    ("Khatipura", 26.9280, 75.7470), ("Kho Nagoriyan", 26.8830, 75.8820), ("Jamdoli", 26.9060, 75.8780),
    ("Muhana", 26.8000, 75.7600), ("Goner Road", 26.8600, 75.9000), ("Mahal Road", 26.8400, 75.8800),
    ("Sirsi Road", 26.9050, 75.7100), ("Kalwar Road", 26.9500, 75.7150), ("Benar Road", 26.9750, 75.7350),
    ("Harmada", 26.9950, 75.7550), ("Jaisinghpura Khor", 26.9800, 75.8700), ("Mansarovar Extension", 26.8400, 75.7400),
    ("Sitapura", 26.7990, 75.8450), ("Delhi Road", 26.9650, 75.8600), ("Agra Road", 26.9050, 75.9000),
    ("Kanakpura", 26.9280, 75.7000), ("Mahapura", 26.8500, 75.7050), ("Kamla Nehru Nagar", 26.8750, 75.7450),
    ("Lal Kothi", 26.8850, 75.7950), ("Nindar", 26.9750, 75.8000), ("Jaisinghpura", 26.9900, 75.8250),
    ("Vatika Road", 26.7990, 75.8000), ("Bagru Road", 26.8250, 75.7050), ("Goner", 26.8200, 75.9050),
    ("Jamwa Ramgarh Road", 26.9650, 75.8900),
)


def cell_ref(row: int, col: int) -> str:
    return f"{COL_LETTERS[col]}{row + 1}"


def cell_of(lat: float, lon: float) -> tuple[int, int] | None:
    """(row, col) of the cell containing the point, or None outside the grid."""
    row = math.floor((GRID_NORTH - lat) / CELL_LAT)
    col = math.floor((lon - GRID_WEST) / CELL_LON)
    return (row, col) if 0 <= row < ROWS and 0 <= col < COLS else None


def cell_bounds(row: int, col: int) -> tuple[float, float, float, float]:
    """(north, south, west, east) edges of a cell."""
    north = GRID_NORTH - row * CELL_LAT
    west = GRID_WEST + col * CELL_LON
    return north, north - CELL_LAT, west, west + CELL_LON


def cell_center(row: int, col: int) -> tuple[float, float]:
    n, s, w, e = cell_bounds(row, col)
    return (n + s) / 2, (w + e) / 2


# ------------------------------------------------------------------- roads

_ROADS_FILE = Path(__file__).with_name("jaipur_roads.json")


def load_roads() -> list[dict]:
    """Main-road polylines clipped to cells: {cell, kind, name, path: [[lat, lon], …]}."""
    try:
        return json.loads(_ROADS_FILE.read_text())["roads"]
    except (OSError, ValueError, KeyError):
        return []


def _road_points(roads: list[dict]) -> dict[str, list[tuple[float, float]]]:
    """For each cell, points on its longest main roads (where traffic sensors are placed)."""
    by_cell: dict[str, list[list[list[float]]]] = {}
    for r in roads:
        by_cell.setdefault(r["cell"], []).append(r["path"])
    out = {}
    for cell, paths in by_cell.items():
        paths = sorted(paths, key=lambda p: -_length(p))
        pts = [p[len(p) // 2] for p in paths[:2]]
        if len(pts) == 1 and len(paths[0]) >= 3:
            pts.append(paths[0][len(paths[0]) // 4])
        out[cell] = [(round(p[0], 5), round(p[1], 5)) for p in pts]
    return out


def _length(path: list[list[float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(path, path[1:], strict=False))


# ------------------------------------------------------------------- zones

@dataclass(frozen=True)
class Zone:
    id: str  # grid reference, e.g. "F4"
    number: int  # 1…81 in reading order (sorting only)
    name: str  # "Walled City (F4)"
    short_name: str  # "Walled City"
    row: int
    col: int
    polygon: tuple[tuple[float, float], ...]
    # Where the map label sits
    label_point: tuple[float, float] = (0.0, 0.0)
    # Sensors placed inside the area for the IoT layer: (sensor_id, kind, lat, lon)
    sensors: tuple[tuple[str, str, float, float], ...] = field(default=())

    @property
    def centroid(self) -> tuple[float, float]:
        return cell_center(self.row, self.col)

    def geojson_ring(self) -> list[list[float]]:
        ring = [[lon, lat] for lat, lon in self.polygon]
        return ring + [ring[0]]


def _locality_names() -> dict[tuple[int, int], str]:
    named: dict[tuple[int, int], str] = {}
    for name, lat, lon in LOCALITIES:
        cell = cell_of(lat, lon)
        if cell is not None and cell not in named:
            named[cell] = name
    for row in range(ROWS):
        for col in range(COLS):
            if (row, col) in named:
                continue
            clat, clon = cell_center(row, col)
            nearest = min(LOCALITIES, key=lambda loc: (loc[1] - clat) ** 2 + ((loc[2] - clon) * 0.89) ** 2)
            named[(row, col)] = f"Near {nearest[0]}"
    return named


def _sensors(ref: str, row: int, col: int, on_roads: list[tuple[float, float]]) -> tuple:
    n, s, w, e = cell_bounds(row, col)
    at = lambda fy, fx: (round(n - fy * CELL_LAT, 5), round(w + fx * CELL_LON, 5))  # noqa: E731
    traffic = (on_roads + [at(0.35, 0.3), at(0.65, 0.7)])[:2]
    return (
        (f"TS-{ref}-1", "traffic", *traffic[0]),
        (f"TS-{ref}-2", "traffic", *traffic[1]),
        (f"RG-{ref}", "rain_gauge", *at(0.3, 0.72)),
        (f"AQ-{ref}", "air_quality", *at(0.72, 0.28)),
        (f"WL-{ref}", "water_level", *at(0.58, 0.5)),
    )


def _build_zones() -> tuple[Zone, ...]:
    names = _locality_names()
    road_points = _road_points(load_roads())
    zones = []
    for row in range(ROWS):
        for col in range(COLS):
            ref = cell_ref(row, col)
            n, s, w, e = cell_bounds(row, col)
            locality = names[(row, col)]
            zones.append(Zone(
                id=ref, number=row * COLS + col + 1, name=f"{locality} ({ref})", short_name=locality,
                row=row, col=col, polygon=((n, w), (n, e), (s, e), (s, w)),
                label_point=cell_center(row, col),
                sensors=_sensors(ref, row, col, road_points.get(ref, [])),
            ))
    return tuple(zones)


ZONES: tuple[Zone, ...] = _build_zones()
ZONES_BY_ID: dict[str, Zone] = {z.id: z for z in ZONES}
ZONE_IDS: tuple[str, ...] = tuple(z.id for z in ZONES)

SENSOR_REGISTRY: dict[str, tuple[str, str, float, float]] = {
    s[0]: (z.id, s[1], s[2], s[3]) for z in ZONES for s in z.sensors
}


def cell_distance(a: str, b: str) -> float:
    """Distance between two cells' centres, in cells (neighbours = 1, diagonal ≈ 1.41)."""
    za, zb = ZONES_BY_ID[a], ZONES_BY_ID[b]
    return math.hypot(za.row - zb.row, za.col - zb.col)


def zone_for_point(lat: float, lon: float) -> str | None:
    """Return the area containing the point, or None if it is outside the grid."""
    cell = cell_of(lat, lon)
    return cell_ref(*cell) if cell else None
