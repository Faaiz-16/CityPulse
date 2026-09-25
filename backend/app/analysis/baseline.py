"""Baselines: what is "normal" for this zone, this metric, at this time of day?

Traffic at 9 a.m. is not comparable with traffic at 3 a.m., so baselines are learned per
half-hour slot of the local day from the stored history.

We use the **median** (middle value) and the **MAD** (median absolute deviation) instead of
mean and standard deviation. Both are "robust": a past storm in the history barely moves
them, so an old unusual event does not redefine what normal looks like.
"""

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.analysis.metrics import DERIVED_INCIDENT_METRICS

SLOTS_PER_DAY = 48  # half-hour slots


@dataclass(frozen=True)
class Baseline:
    median: float
    mad: float
    samples: int
    source: str  # "history" | "default"


# Used only when there is no history (e.g. database unavailable at start-up).
DEFAULT_BASELINES: dict[str, float] = {
    "congestion_pct": 35.0,
    "avg_speed_kmh": 29.0,
    "transit_delay_min": 4.0,
    "rain_mm_h": 0.0,
    "temperature_c": 30.0,
    "wind_kmh": 10.0,
    "pm25_ugm3": 28.0,
    "aqi": 85.0,
    "water_level_cm": 1.5,
}
# Per block (~1.5 km), so these are small.
DEFAULT_INCIDENT_RATE_PER_MIN = {"incident_reports": 0.008, "waterlogging_reports": 0.0002,
                                 "outage_signal_reports": 0.0004, "accident_reports": 0.0004}


def slot_of(t: datetime, tz: ZoneInfo) -> int:
    local = t.astimezone(tz)
    return (local.hour * 60 + local.minute) // 30


# Fitted results for history lists this process has already fitted (the lists are cached by
# persistence, so identity is a safe key; the entry keeps them alive).
_FIT_CACHE: dict[tuple[int, int, str], tuple[object, object, dict, dict, float]] = {}


class BaselineModel:
    def __init__(self, tz: ZoneInfo) -> None:
        self.tz = tz
        self._continuous: dict[tuple[str, str, int], Baseline] = {}
        self._incident_rate: dict[tuple[str, str, int], float] = {}
        self.history_days: float = 0.0

    # ------------------------------------------------------------------ build
    def fit(
        self,
        readings: list[tuple[str, str, datetime, float]],  # (zone, metric, ts, value)
        incidents: list[tuple[str, str, datetime]],  # (zone, category, ts)
    ) -> "BaselineModel":
        key = (id(readings), id(incidents), str(self.tz))
        if readings and key in _FIT_CACHE:
            _, _, self._continuous, self._incident_rate, self.history_days = _FIT_CACHE[key]
            return self
        self._fit(readings, incidents)
        if readings:
            _FIT_CACHE.clear()
            _FIT_CACHE[key] = (readings, incidents, self._continuous, self._incident_rate, self.history_days)
        return self

    def _fit(self, readings, incidents) -> None:
        buckets: dict[tuple[str, str, int], list[float]] = defaultdict(list)
        first, last = None, None
        for zone, metric, ts, value in readings:
            buckets[(zone, metric, slot_of(ts, self.tz))].append(value)
            first = ts if first is None or ts < first else first
            last = ts if last is None or ts > last else last

        # Smooth over neighbouring slots (±30 min) so each baseline has enough samples.
        keys = {(z, m) for z, m, _ in buckets}
        for zone, metric in keys:
            for slot in range(SLOTS_PER_DAY):
                values = []
                for d in (-1, 0, 1):
                    values += buckets.get((zone, metric, (slot + d) % SLOTS_PER_DAY), [])
                if len(values) >= 3:
                    med = statistics.median(values)
                    mad = statistics.median(abs(v - med) for v in values)
                    self._continuous[(zone, metric, slot)] = Baseline(med, mad, len(values), "history")

        days = max((last - first).total_seconds() / 86400, 1 / 24) if first and last else 0
        self.history_days = round(days, 2)

        # Report rate per minute, per derived metric, per slot. Computed per day and then the
        # MEDIAN across days is taken, so one stormy evening doesn't raise "normal" for every day.
        covered: set[tuple[object, int]] = set()  # (local date, slot) pairs the history covers
        for _, _, ts, _ in readings:
            local = ts.astimezone(self.tz)
            covered.add((local.date(), slot_of(ts, self.tz)))
        counts: dict[tuple[str, str, object, int], int] = defaultdict(int)
        for zone, category, ts in incidents:
            local = ts.astimezone(self.tz)
            slot = slot_of(ts, self.tz)
            for metric, cats in DERIVED_INCIDENT_METRICS.items():
                if cats is None or category in cats:
                    counts[(zone, metric, local.date(), slot)] += 1
        dates = sorted({d for d, _ in covered})
        zones = {z for z, _ in keys}
        for zone in zones:
            for metric in DERIVED_INCIDENT_METRICS:
                for slot in range(SLOTS_PER_DAY):
                    per_day = [
                        sum(counts.get((zone, metric, d, (slot + k) % SLOTS_PER_DAY), 0) for k in (-1, 0, 1)) / 90
                        for d in dates if (d, slot) in covered
                    ]
                    if per_day:
                        self._incident_rate[(zone, metric, slot)] = statistics.median(per_day)

    # ----------------------------------------------------------------- lookup
    def continuous(self, zone_id: str, metric: str, t: datetime) -> Baseline:
        b = self._continuous.get((zone_id, metric, slot_of(t, self.tz)))
        if b is not None:
            return b
        return Baseline(DEFAULT_BASELINES.get(metric, 0.0), 0.0, 0, "default")

    def expected_incidents(self, zone_id: str, metric: str, t: datetime, window_minutes: float) -> float:
        rate = self._incident_rate.get((zone_id, metric, slot_of(t, self.tz)))
        if rate is None:
            rate = DEFAULT_INCIDENT_RATE_PER_MIN.get(metric, 0.05)
        return rate * window_minutes
