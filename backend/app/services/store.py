"""In-memory rolling store of recent normalized data.

The analysis engine reads only from here, so the live pulse keeps working even if the
database has a problem. Data older than ``retention`` is pruned every tick.
"""

import threading
from bisect import bisect_left
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.schemas import CivicIncident, CivicReading


@dataclass(frozen=True)
class Point:
    ts: datetime
    value: float
    data_status: str
    sensor_id: str | None


class ReadingStore:
    def __init__(self, retention: timedelta = timedelta(minutes=40)) -> None:
        self.retention = retention
        self._lock = threading.RLock()
        self._series: dict[tuple[str, str], deque[Point]] = defaultdict(deque)
        self._incidents: deque[CivicIncident] = deque()
        self._incident_ids: set[str] = set()
        self.sensors: dict[str, dict] = {}  # latest value per physical sensor (map layer)

    # ------------------------------------------------------------------ writes
    def add_readings(self, readings: list[CivicReading]) -> None:
        with self._lock:
            for r in sorted(readings, key=lambda r: r.timestamp):
                series = self._series[(r.zone_id, r.metric)]
                point = Point(r.timestamp, r.value, r.data_status.value, r.sensor_id)
                if series and series[-1].ts > r.timestamp:  # late arrival: keep order
                    items = list(series)
                    items.insert(bisect_left([p.ts for p in items], r.timestamp), point)
                    self._series[(r.zone_id, r.metric)] = deque(items)
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
                added.append(inc)
        return added

    def prune(self, now: datetime) -> None:
        cutoff = now - self.retention
        with self._lock:
            for series in self._series.values():
                while series and series[0].ts < cutoff:
                    series.popleft()
            while self._incidents and self._incidents[0].timestamp < cutoff:
                self._incident_ids.discard(self._incidents.popleft().id)

    def clear(self) -> None:
        with self._lock:
            self._series.clear()
            self._incidents.clear()
            self._incident_ids.clear()
            self.sensors.clear()

    # ------------------------------------------------------------------- reads
    def series(self, zone_id: str, metric: str, start: datetime, end: datetime) -> list[Point]:
        with self._lock:
            return [p for p in self._series.get((zone_id, metric), ()) if start <= p.ts <= end]

    def latest(self, zone_id: str, metric: str) -> Point | None:
        with self._lock:
            s = self._series.get((zone_id, metric))
            return s[-1] if s else None

    def incidents(self, start: datetime, end: datetime, zone_id: str | None = None,
                  categories: tuple[str, ...] | None = None) -> list[CivicIncident]:
        with self._lock:
            return [
                i for i in self._incidents
                if start <= i.timestamp <= end
                and (zone_id is None or i.zone_id == zone_id)
                and (categories is None or i.category in categories)
            ]
