"""The CityPulse analysis engine.

    recent normalized data (store) + baselines
        → per-metric assessment (current, baseline, deviation, anomaly, severity)
        → anomalies
        → rolling-window relationships
        → risk insights
        → zone status (GREEN / YELLOW / RED)

It is a pure function of (store contents, baselines, time), so the same engine powers the
live view, historical replay and the tests.
"""

from datetime import datetime, timedelta

from app.analysis.anomaly import (
    assess_continuous,
    assess_incident_count,
    onset,
    value_check,
)
from app.analysis.baseline import BaselineModel
from app.analysis.correlation import ZoneSignals, evaluate_zone, window_bins
from app.analysis.metrics import (
    CONTINUOUS_METRICS,
    DERIVED_INCIDENT_METRICS,
    INCIDENT_CATEGORIES,
    METRICS,
    usual_reports,
    verb_for,
)
from app.analysis.risk import STATUS_LABELS, assess_risks, zone_status
from app.config import Settings
from app.geo.zones import ZONES
from app.schemas import (
    Anomaly,
    IncidentView,
    MetricAssessment,
    PulseInfo,
    ZoneState,
    ZoneStatus,
)
from app.services.store import ReadingStore

# Metrics that take part in relationship rules and need binned series for co-movement.
_BINNED = ("rain_mm_h", "congestion_pct", "transit_delay_min", "aqi", "water_level_cm",
           "waterlogging_reports", "outage_signal_reports")

_SHORT_PHRASE = {
    "rain_mm_h": "Heavy rain",
    "congestion_pct": "Traffic unusually heavy",
    "transit_delay_min": "Bus delays above normal",
    "aqi": "Air quality worse than usual",
    "water_level_cm": "Standing water detected",
    "incident_reports": "More civic reports than usual",
    "waterlogging_reports": "Waterlogging reports rising",
    "outage_signal_reports": "Outage reports rising",
}

_SEV_RANK = {"none": 0, "low": 1, "moderate": 2, "high": 3}


def describe_anomaly(m: MetricAssessment) -> str:
    """Observed-fact sentence for an anomaly (no interpretation)."""
    if m.metric == "rain_mm_h":
        return f"Rainfall is {m.current:g} mm/h — heavy rain."
    if m.metric == "water_level_cm":
        return f"Street water-level sensor reads {m.current:g} cm."
    if METRICS[m.metric].source.value == "incidents":
        return f"{m.current:g} {m.label.lower()} in the last window ({usual_reports(m.baseline, m.deviation_pct)})."
    unit = "%" if m.unit == "%" else f" {m.unit}"
    return (f"{m.label} {verb_for(m.label)} {m.current:g}{unit}, {m.deviation_pct:+.0f}% compared with the usual "
            f"{m.baseline:g}{unit} for this time of day.")


class AnalysisEngine:
    def __init__(self, settings: Settings, baselines: BaselineModel) -> None:
        self.s = settings
        self.baselines = baselines

    # ------------------------------------------------------------------ public
    def analyze(self, store: ReadingStore, now: datetime, feed_intervals: dict[str, float],
                incidents_available: bool = True) -> tuple[list[ZoneState], PulseInfo]:
        zones = [self._analyze_zone(z, store, now, feed_intervals, incidents_available) for z in ZONES]
        return zones, self.pulse(zones)

    @staticmethod
    def pulse(zones: list[ZoneState]) -> PulseInfo:
        counts = {s.value: sum(1 for z in zones if z.status == s) for s in ZoneStatus}
        n_anom = sum(len(z.anomalies) for z in zones)
        n_rel = sum(len([r for r in z.relationships if r.strength != "weak"]) for z in zones)
        city = ZoneStatus.RED if counts["RED"] else ZoneStatus.YELLOW if counts["YELLOW"] else ZoneStatus.GREEN
        bpm = min(140, 62 + 6 * n_anom + 18 * counts["RED"])
        return PulseInfo(city_status=city, bpm=bpm, active_anomalies=n_anom,
                         active_relationships=n_rel, zones_by_status=counts)

    # ----------------------------------------------------------------- per zone
    def _analyze_zone(self, zone, store: ReadingStore, now: datetime, feed_intervals: dict[str, float],
                      incidents_available: bool) -> ZoneState:
        s = self.s
        rolling = timedelta(minutes=s.rolling_window_minutes)
        metrics: dict[str, MetricAssessment] = {}
        onsets: dict[str, datetime] = {}

        for key in CONTINUOUS_METRICS:
            mdef = METRICS[key]
            interval = feed_intervals.get(mdef.source.value, 10.0)
            window = timedelta(seconds=max(s.current_window_seconds, 2.5 * interval))
            points = store.series(zone.id, key, now - window, now)
            # Trend needs a handful of points: ≥ 3 minutes, longer for slower feeds (e.g. archives).
            trend_pts = store.series(zone.id, key, now - timedelta(seconds=max(180, 6 * interval)), now)
            base = self.baselines.continuous(zone.id, key, now)
            m = assess_continuous(mdef, points, trend_pts, base, s)
            metrics[key] = m
            if m.is_anomaly:
                history = store.series(zone.id, key, now - rolling, now)
                onsets[key] = onset(history, value_check(mdef, s, base.median)) or points[0].ts

        for key, cats in DERIVED_INCIDENT_METRICS.items():
            reports = store.incidents(now - rolling, now, zone.id, cats)
            expected = self.baselines.expected_incidents(zone.id, key, now, s.rolling_window_minutes)
            half = now - rolling / 2
            early, late = sum(1 for r in reports if r.timestamp < half), sum(1 for r in reports if r.timestamp >= half)
            trend = "rising" if late > early + 1 else "falling" if early > late + 1 else "steady"
            m = assess_incident_count(METRICS[key], len(reports), expected, s,
                                      reports[-1].timestamp if reports else None, incidents_available, trend)
            metrics[key] = m
            if m.is_anomaly and reports:
                onsets[key] = reports[0].timestamp

        anomalies = sorted(
            (Anomaly(id=f"{zone.id}:{m.metric}", zone_id=zone.id, metric=m.metric, label=m.label,
                     severity=m.severity, current=m.current, baseline=m.baseline,
                     deviation_pct=m.deviation_pct, unit=m.unit, since=onsets.get(m.metric, now),
                     description=describe_anomaly(m))
             for m in metrics.values() if m.is_anomaly),
            key=lambda a: -_SEV_RANK[a.severity],
        )

        signals = ZoneSignals(zone.id, zone.name, metrics, onsets, self._binned(store, zone.id, now))
        relationships, insufficient, cannot = evaluate_zone(signals, s)
        risks = assess_risks(zone.id, zone.name, metrics, anomalies, relationships, s)
        status = zone_status(anomalies, relationships, risks)

        window_incidents = store.incidents(now - rolling, now, zone.id)
        counts: dict[str, int] = {}
        for inc in window_incidents:
            counts[inc.category] = counts.get(inc.category, 0) + 1

        return ZoneState(
            id=zone.id, number=zone.number, name=zone.name, short_name=zone.short_name,
            status=status, status_label=STATUS_LABELS[status],
            headline=self._headline(status, anomalies, risks),
            issue_types=sorted({METRICS[a.metric].icon for a in anomalies}),
            metrics=metrics, anomalies=anomalies, relationships=relationships, risks=risks,
            insufficient_evidence=insufficient, cannot_assess=cannot, incident_counts=counts,
            recent_incidents=[
                IncidentView(id=i.id, zone_id=i.zone_id, category=i.category,
                             label=INCIDENT_CATEGORIES[i.category]["label"], severity=i.severity,
                             timestamp=i.timestamp, lat=i.lat, lon=i.lon, data_status=i.data_status.value)
                for i in reversed(window_incidents[-25:])
            ],
            anchor=zone.label_point,
        )

    @staticmethod
    def _headline(status: ZoneStatus, anomalies: list[Anomaly], risks) -> str:
        if status == ZoneStatus.RED:
            disruption = [r for r in risks if r.kind == "potential_disruption"]
            if disruption:
                return disruption[0].headline.split(" in Zone")[0]
            return "Several signals highly unusual"
        if risks:
            return risks[0].headline.split(" in Zone")[0]
        if anomalies:
            return _SHORT_PHRASE.get(anomalies[0].metric, "Unusual activity")
        return "Conditions normal"

    def _binned(self, store: ReadingStore, zone_id: str, now: datetime) -> dict[str, list[float | None]]:
        bins = window_bins(now, self.s.rolling_window_minutes)
        start, out = bins[0][0], {}
        for key in _BINNED:
            if key in DERIVED_INCIDENT_METRICS:
                reports = store.incidents(start - timedelta(minutes=3), now, zone_id, DERIVED_INCIDENT_METRICS[key])
                out[key] = [float(sum(1 for r in reports if b_end - timedelta(minutes=3) <= r.timestamp < b_end))
                            for _, b_end in bins]
                continue
            points = store.series(zone_id, key, start, now)
            values: list[float | None] = []
            idx, last = 0, None
            for b_start, b_end in bins:
                bucket = []
                while idx < len(points) and points[idx].ts < b_end:
                    if points[idx].ts >= b_start:
                        bucket.append(points[idx].value)
                    idx += 1
                if bucket:
                    last = sum(bucket) / len(bucket)
                values.append(last)  # carry the last value forward through empty bins
            out[key] = values
        return out
