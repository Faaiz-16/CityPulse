"""In-memory rolling store of recent normalized data.

The analysis engine reads only from here, so the live pulse keeps working even if the
database has a problem. Data older than ``retention`` is pruned every tick.

Series are kept sorted by time, so a window read is a binary search rather than a scan —
this matters with 225 blocks × several metrics read every few seconds.
"""

import threading
from bisect import bisect_left, bisect_right, insort
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.schemas import CivicIncident, CivicReading


@dataclass(frozen=True, slots=True)
class Point:
    """One normalized reading in a (zone, metric) series: every common-data-model field except
    zone and metric, which are the series key. Slots keep ~1M of them light in memory."""

    ts: datetime
    value: float
    data_status: str
    sensor_id: str | None
    source: str = ""
    source_type: str = ""
    provider: str = ""
    unit: str = ""
    confidence: float = 1.0
    ingested_at: datetime | None = None
    lat: float | None = None
    lon: float | None = None
    metadata: dict | None = None


class ReadingStore:
    def __init__(self, retention: timedelta = timedelta(minutes=40)) -> None:
        self.retention = retention
        self._lock = threading.RLock()
        self._series: dict[tuple[str, str], list[Point]] = defaultdict(list)
        self._incidents: deque[CivicIncident] = deque()
        self._by_zone: dict[str, list[CivicIncident]] = defaultdict(list)
        self._incident_ids: set[str] = set()
        self.sensors: dict[str, dict] = {}  # latest value per physical sensor (map layer)

    # ------------------------------------------------------------------ writes
    def add_readings(self, readings: list[CivicReading]) -> None:
        with self._lock:
            for r in sorted(readings, key=lambda r: r.timestamp):
                series = self._series[(r.zone_id, r.metric)]
                point = Point(r.timestamp, r.value, r.data_status.value, r.sensor_id, r.source, r.source_type.value,
                              r.provider, r.unit, r.confidence, r.ingested_at, r.lat, r.lon, r.metadata or None)
                if series and series[-1].ts > r.timestamp:  # late arrival: keep order
                    insort(series, point, key=_ts)
                else:
                    series.append(point)
                if r.sensor_id:
                    entry = self.sensors.setdefault(r.sensor_id, {"zone_id": r.zone_id, "lat": r.lat,
                                                                  "lon": r.lon, "values": {}})
                    entry["values"][r.metric] = {"value": r.value, "unit": r.unit,
                                                 "ts": r.timestamp, "data_status": r.data_status.value}

    def add_incidents(self, incidents: list[CivicIncident]) -> list[CivicIncident]:
        """Add incidents, ignoring duplicates (same report delivered twice). Returns new ones."""
        added = []
        with self._lock:
            for inc in sorted(incidents, key=lambda i: i.timestamp):
                if inc.id in self._incident_ids:
                    continue
                self._incident_ids.add(inc.id)
                self._incidents.append(inc)
                if inc.zone_id:
                    insort(self._by_zone[inc.zone_id], inc, key=_its)
                added.append(inc)
        return added

    def prune(self, now: datetime) -> None:
        cutoff = now - self.retention
        with self._lock:
            for series in self._series.values():
                if series and series[0].ts < cutoff:
                    del series[:bisect_left(series, cutoff, key=_ts)]
            while self._incidents and self._incidents[0].timestamp < cutoff:
                self._incident_ids.discard(self._incidents.popleft().id)
            for items in self._by_zone.values():
                if items and items[0].timestamp < cutoff:
                    del items[:bisect_left(items, cutoff, key=_its)]

    def clear(self) -> None:
        with self._lock:
            self._series.clear()
            self._incidents.clear()
            self._by_zone.clear()
            self._incident_ids.clear()
            self.sensors.clear()

    # ------------------------------------------------------------------- reads
    def series(self, zone_id: str, metric: str, start: datetime, end: datetime) -> list[Point]:
        with self._lock:
            s = self._series.get((zone_id, metric))
            if not s:
                return []
            return s[bisect_left(s, start, key=_ts):bisect_right(s, end, key=_ts)]

    def latest(self, zone_id: str, metric: str) -> Point | None:
        with self._lock:
            s = self._series.get((zone_id, metric))
            return s[-1] if s else None

    def incidents(self, start: datetime, end: datetime, zone_id: str | None = None,
                  categories: tuple[str, ...] | None = None) -> list[CivicIncident]:
        with self._lock:
            if zone_id is None:
                items = [i for i in self._incidents if start <= i.timestamp <= end]
            else:
                zs = self._by_zone.get(zone_id, [])
                items = zs[bisect_left(zs, start, key=_its):bisect_right(zs, end, key=_its)]
            return items if categories is None else [i for i in items if i.category in categories]


def _ts(p: Point) -> datetime:
    return p.ts


def _its(i: CivicIncident) -> datetime:
    return i.timestamp
