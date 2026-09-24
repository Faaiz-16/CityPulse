"""Demonstration zones and simple geometry helpers.

The five zones are **demonstration zones** drawn over a real basemap for context.
They are not official administrative boundaries.

Coordinates are (lat, lon). GeoJSON output uses (lon, lat) as the spec requires.
"""

from dataclasses import dataclass, field

CITY_CENTER = (28.6139, 77.2090)

# Corner points of the inner (Central) box and the outer boundary.
_IN_N, _IN_S, _IN_W, _IN_E = 28.645, 28.585, 77.175, 77.245
_OUT_N, _OUT_S, _OUT_W, _OUT_E = 28.725, 28.505, 77.075, 77.345


@dataclass(frozen=True)
class Zone:
    id: str
    number: int
    name: str
    short_name: str
    polygon: tuple[tuple[float, float], ...]
    # Sensors placed inside the zone for the IoT layer: (sensor_id, kind, lat, lon)
    sensors: tuple[tuple[str, str, float, float], ...] = field(default=())

    @property
    def centroid(self) -> tuple[float, float]:
        lats = [p[0] for p in self.polygon]
        lons = [p[1] for p in self.polygon]
        return (sum(lats) / len(lats), sum(lons) / len(lons))

    def geojson_ring(self) -> list[list[float]]:
        ring = [[lon, lat] for lat, lon in self.polygon]
        return ring + [ring[0]]


def _sensors(prefix: str, lat: float, lon: float) -> tuple[tuple[str, str, float, float], ...]:
    """Place one sensor of each kind around a zone's anchor point."""
    return (
        (f"TS-{prefix}-01", "traffic", lat + 0.006, lon - 0.010),
        (f"TS-{prefix}-02", "traffic", lat - 0.007, lon + 0.012),
        (f"RG-{prefix}-01", "rain_gauge", lat + 0.010, lon + 0.008),
        (f"AQ-{prefix}-01", "air_quality", lat - 0.010, lon - 0.006),
        (f"WL-{prefix}-01", "water_level", lat - 0.002, lon + 0.002),
    )


ZONES: tuple[Zone, ...] = (
    Zone(
        id="Z1", number=1, name="Zone 1 — Central", short_name="Central",
        polygon=((_IN_N, _IN_W), (_IN_N + 0.003, 77.210), (_IN_N, _IN_E),
                 (28.615, _IN_E + 0.004), (_IN_S, _IN_E), (_IN_S - 0.003, 77.212),
                 (_IN_S, _IN_W), (28.616, _IN_W - 0.004)),
        sensors=_sensors("C", 28.615, 77.210),
    ),
    Zone(
        id="Z2", number=2, name="Zone 2 — North", short_name="North",
        polygon=((_OUT_N, _OUT_W), (_OUT_N + 0.008, 77.210), (_OUT_N, _OUT_E),
                 (_IN_N, _IN_E), (_IN_N + 0.003, 77.210), (_IN_N, _IN_W)),
        sensors=_sensors("N", 28.685, 77.205),
    ),
    Zone(
        id="Z3", number=3, name="Zone 3 — East", short_name="East",
        polygon=((_OUT_N, _OUT_E), (28.615, _OUT_E + 0.010), (_OUT_S, _OUT_E),
                 (_IN_S, _IN_E), (28.615, _IN_E + 0.004), (_IN_N, _IN_E)),
        sensors=_sensors("E", 28.612, 77.292),
    ),
    Zone(
        id="Z4", number=4, name="Zone 4 — South", short_name="South",
        polygon=((_IN_S, _IN_W), (_IN_S - 0.003, 77.212), (_IN_S, _IN_E),
                 (_OUT_S, _OUT_E), (_OUT_S - 0.008, 77.210), (_OUT_S, _OUT_W)),
        sensors=_sensors("S", 28.545, 77.212),
    ),
    Zone(
        id="Z5", number=5, name="Zone 5 — West", short_name="West",
        polygon=((_OUT_N, _OUT_W), (_IN_N, _IN_W), (28.616, _IN_W - 0.004),
                 (_IN_S, _IN_W), (_OUT_S, _OUT_W), (28.615, _OUT_W - 0.010)),
        sensors=_sensors("W", 28.617, 77.125),
    ),
)

ZONES_BY_ID: dict[str, Zone] = {z.id: z for z in ZONES}
ZONE_IDS: tuple[str, ...] = tuple(z.id for z in ZONES)

SENSOR_REGISTRY: dict[str, tuple[str, str, float, float]] = {
    s[0]: (z.id, s[1], s[2], s[3]) for z in ZONES for s in z.sensors
}


def point_in_polygon(lat: float, lon: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    """Ray-casting test: count how many polygon edges a ray from the point crosses."""
    inside = False
    n = len(polygon)
    for i in range(n):
        lat1, lon1 = polygon[i]
        lat2, lon2 = polygon[(i + 1) % n]
        if (lon1 > lon) != (lon2 > lon):
            crossing_lat = lat1 + (lon - lon1) * (lat2 - lat1) / (lon2 - lon1)
            if lat < crossing_lat:
                inside = not inside
    return inside


def zone_for_point(lat: float, lon: float) -> str | None:
    """Return the zone containing the point, or None if it is outside every zone."""
    for zone in ZONES:
        if point_in_polygon(lat, lon, zone.polygon):
            return zone.id
    return None
