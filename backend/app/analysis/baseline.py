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
DEFAULT_INCIDENT_RATE_PER_MIN = {"incident_reports": 0.25, "waterlogging_reports": 0.006,
                                 "outage_signal_reports": 0.012}


def slot_of(t: datetime, tz: ZoneInfo) -> int:
    local = t.astimezone(tz)
    return (local.hour * 60 + local.minute) // 30


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

        # Incident rate per minute, per derived metric, per slot (averaged over the history).
        counts: dict[tuple[str, str, int], int] = defaultdict(int)
        for zone, category, ts in incidents:
            slot = slot_of(ts, self.tz)
            for metric, cats in DERIVED_INCIDENT_METRICS.items():
                if cats is None or category in cats:
                    counts[(zone, metric, slot)] += 1
        if days:
            zones = {z for z, _ in keys} | {z for z, _, _ in counts}
            for zone in zones:
                for metric in DERIVED_INCIDENT_METRICS:
                    for slot in range(SLOTS_PER_DAY):
                        n = sum(counts.get((zone, metric, (slot + d) % SLOTS_PER_DAY), 0) for d in (-1, 0, 1))
                        # 3 slots × 30 min × number of days of history
                        self._incident_rate[(zone, metric, slot)] = n / (90 * days)
        return self

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
