"""Builds the zone-detail view (charts, baselines, reports) from a rolling store.

Shared by the live pipeline and historical replay.
"""

from datetime import datetime, timedelta

from app.analysis.baseline import BaselineModel
from app.schemas import Alert, SummarySection, ZoneState
from app.services.store import Point, ReadingStore

CHART_METRICS = ("rain_mm_h", "congestion_pct", "transit_delay_min", "aqi", "water_level_cm", "temperature_c")


def downsample(points: list[Point], start: datetime, end: datetime, bin_s: int) -> list[dict]:
    """Average readings into fixed time bins; empty bins are None (gaps, not zeros)."""
    out, idx = [], 0
    t = start
    while t < end:
        t_next = t + timedelta(seconds=bin_s)
        bucket = []
        while idx < len(points) and points[idx].ts < t_next:
            if points[idx].ts >= t:
                bucket.append(points[idx].value)
            idx += 1
        out.append({"t": t_next, "v": round(sum(bucket) / len(bucket), 2) if bucket else None})
        t = t_next
    return out


def zone_detail(store: ReadingStore, baselines: BaselineModel, zone: ZoneState, now: datetime, *,
                explanation: SummarySection | None, explanation_by: str, alerts: list[Alert],
                agent_trace: list[str], sensors: list[dict], bin_s: int = 20) -> dict:
    start = now - timedelta(minutes=15)
    series = {key: downsample(store.series(zone.id, key, start, now), start, now, bin_s) for key in CHART_METRICS}
    per_minute: dict[str, int] = {}
    for r in store.incidents(start, now, zone.id):
        minute = r.timestamp.replace(second=0, microsecond=0).isoformat()
        per_minute[minute] = per_minute.get(minute, 0) + 1
    return {
        "zone": zone,
        "explanation": explanation,
        "explanation_by": explanation_by,
        "series": series,
        # Use the zone's own assessed baseline: it is None where no fair "normal" exists (live AQI).
        "baselines": {k: zone.metrics[k].baseline if k in zone.metrics else baselines.continuous(zone.id, k, now).median
                      for k in series},
        "reports_per_minute": [{"minute": k, "count": v} for k, v in sorted(per_minute.items())],
        "sensors": sensors,
        "alerts": [a for a in alerts if a.zone_id == zone.id],
        "agent_trace": agent_trace,
    }
