"""Explainable anomaly detection.

For every metric we compute: current value, baseline, % deviation, a robust z-score,
the threshold rule that applies, whether it is an anomaly, and how severe it is.

Rules (all thresholds live in ``config.py`` and are documented in ARCHITECTURE.md):

  relative  (traffic, bus delays)  deviation ≥ threshold%          e.g. congestion ≥ +30%
  incidents (report counts)        count ≥ min_count AND ≥ +threshold% over expected AND
                                   statistically unlikely by chance (Poisson p < 0.001)
  absolute  (rain, water level)    value ≥ fixed physical limit    e.g. rain ≥ 7.6 mm/h
  hybrid    (air quality)          AQI ≥ 150  OR  deviation ≥ +25%

Severity grows with how far past the threshold the value is.
"""

import math
from collections.abc import Callable
from datetime import datetime

from app.analysis.baseline import Baseline
from app.analysis.metrics import MetricDef
from app.config import Settings
from app.schemas import MetricAssessment, Severity
from app.services.store import Point


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def deviation_pct(current: float, baseline: float) -> float | None:
    if baseline is None or abs(baseline) < 1e-9:
        return None
    return (current - baseline) / abs(baseline) * 100


def robust_z(current: float, b: Baseline) -> float | None:
    """How many "typical spreads" away from normal. 1.4826·MAD ≈ one standard deviation."""
    if b.mad <= 1e-9:
        return None
    return (current - b.median) / (1.4826 * b.mad)


def trend_of(points: list[Point]) -> str:
    if len(points) < 4:
        return "unknown"
    third = max(1, len(points) // 3)
    early, late = _mean([p.value for p in points[:third]]), _mean([p.value for p in points[-third:]])
    scale = max(abs(early), 1.0)
    change = (late - early) / scale
    if change > 0.08:
        return "rising"
    if change < -0.08:
        return "falling"
    return "steady"


def poisson_tail(count: int, expected: float) -> float:
    """P(X ≥ count) when X ~ Poisson(expected): how likely this many reports is by pure chance.

    Reports arrive randomly, so a few extra is normal. We only call it a spike when seeing this
    many would happen less than 0.1% of the time on a normal day.
    """
    if count <= 0:
        return 1.0
    term = math.exp(-expected)
    below = term
    for k in range(1, count):
        term *= expected / k
        below += term
    return max(0.0, 1.0 - below)


def relative_severity(dev: float, threshold: float) -> Severity:
    if dev >= 2 * threshold:
        return "high"
    if dev >= 1.4 * threshold:
        return "moderate"
    return "low"


def threshold_text(m: MetricDef, s: Settings) -> str:
    match m.key:
        case "rain_mm_h":
            return f"≥ {s.heavy_rain_mm_h} mm/h (heavy rain)"
        case "water_level_cm":
            return f"≥ {s.water_level_threshold_cm:g} cm standing water"
        case "aqi":
            return f"AQI ≥ {s.aqi_threshold:g} or ≥ {s.aqi_threshold_pct:g}% above normal"
        case "congestion_pct":
            return f"≥ {s.traffic_threshold_pct:g}% above normal"
        case "transit_delay_min":
            return f"≥ {s.transit_threshold_pct:g}% above normal"
    if m.source.value == "incidents":
        return (f"≥ {s.incident_min_count} reports, ≥ {s.incident_threshold_pct:g}% above normal "
                f"and unlikely by chance (p < {s.incident_p_value:g})")
    return "context only"


def value_check(m: MetricDef, s: Settings, baseline: float | None) -> Callable[[float], bool]:
    """Per-reading test used to find when an anomaly started."""
    match m.key:
        case "rain_mm_h":
            return lambda v: v >= s.heavy_rain_mm_h
        case "water_level_cm":
            return lambda v: v >= s.water_level_threshold_cm
        case "aqi":
            return lambda v: v >= s.aqi_threshold or (
                bool(baseline) and (v - baseline) / baseline * 100 >= s.aqi_threshold_pct)
        case "congestion_pct":
            return lambda v: bool(baseline) and (v - baseline) / baseline * 100 >= s.traffic_threshold_pct
        case "transit_delay_min":
            return lambda v: bool(baseline) and (v - baseline) / baseline * 100 >= s.transit_threshold_pct
    return lambda v: False


def assess_continuous(
    m: MetricDef, points: list[Point], trend_points: list[Point], b: Baseline, s: Settings,
) -> MetricAssessment:
    """Assess a measured metric from the readings inside its current window."""
    if not points:
        return MetricAssessment(
            metric=m.key, label=m.label, unit=m.unit, source=m.source.value, current=None,
            baseline=round(b.median, 2), deviation_pct=None, robust_z=None,
            threshold=threshold_text(m, s), is_anomaly=False, severity="none", trend="unknown",
            samples=0, last_updated=trend_points[-1].ts if trend_points else None,
            data_status=trend_points[-1].data_status if trend_points else None, available=False,
        )

    current = _mean([p.value for p in points])
    base = b.median
    dev = deviation_pct(current, base)
    z = robust_z(current, b)
    is_anomaly, severity = False, "none"

    if m.mode == "relative":
        limit = s.traffic_threshold_pct if m.key == "congestion_pct" else s.transit_threshold_pct
        if dev is not None and dev >= limit:
            is_anomaly, severity = True, relative_severity(dev, limit)
    elif m.key == "rain_mm_h":
        if current >= s.heavy_rain_mm_h:
            is_anomaly = True
            severity = "high" if current >= 2 * s.heavy_rain_mm_h else "moderate"
    elif m.key == "water_level_cm":
        if current >= s.water_level_threshold_cm:
            is_anomaly = True
            severity = "high" if current >= 2 * s.water_level_threshold_cm else "moderate"
    elif m.key == "aqi":
        # Relative comparison is only meaningful when the baseline was learned from the same
        # kind of source; for live API values we rely on the absolute health threshold.
        live = points[-1].data_status == "live"
        if current >= s.aqi_threshold:
            is_anomaly = True
            severity = "high" if current >= s.aqi_threshold + 50 else "moderate"
        elif not live and dev is not None and dev >= s.aqi_threshold_pct:
            is_anomaly, severity = True, relative_severity(dev, s.aqi_threshold_pct)

    if m.key == "aqi" and points[-1].data_status == "live":
        # The AQI baseline was learned from synthetic history, so it isn't a fair "normal" for
        # real measurements: report only the absolute health threshold, no baseline or % change.
        base, dev, z = None, None, None

    return MetricAssessment(
        metric=m.key, label=m.label, unit=m.unit, source=m.source.value,
        current=round(current, 1), baseline=round(base, 1) if base is not None else None,
        deviation_pct=round(dev, 1) if dev is not None else None,
        robust_z=round(z, 1) if z is not None else None,
        threshold=threshold_text(m, s), is_anomaly=is_anomaly, severity=severity,
        trend=trend_of(trend_points), samples=len(points), last_updated=points[-1].ts,
        data_status=points[-1].data_status, available=True,
    )


def assess_incident_count(
    m: MetricDef, count: int, expected: float, s: Settings, last_updated: datetime | None,
    available: bool, trend: str,
) -> MetricAssessment:
    """Report counts in the rolling window vs. how many we'd normally expect."""
    expected_floor = max(expected, 0.5)  # avoid "+900%" from a near-zero expectation
    dev = (count - expected_floor) / expected_floor * 100
    p_value = poisson_tail(count, max(expected, 0.05))
    is_anomaly = (available and count >= s.incident_min_count and dev >= s.incident_threshold_pct
                  and p_value < s.incident_p_value)
    severity: Severity = "none"
    if is_anomaly:
        severity = "high" if count >= 2 * s.incident_min_count + 2 and dev >= 3 * s.incident_threshold_pct \
            else "moderate" if count >= 2 * s.incident_min_count else "low"
    return MetricAssessment(
        metric=m.key, label=m.label, unit=m.unit, source=m.source.value,
        current=float(count) if available else None, baseline=round(expected, 2),
        deviation_pct=round(dev, 1) if available else None, robust_z=None,
        threshold=threshold_text(m, s), is_anomaly=is_anomaly, severity=severity, trend=trend,
        samples=count, last_updated=last_updated, data_status=None, available=available,
    )


def onset(points: list[Point], check: Callable[[float], bool]) -> datetime | None:
    """Start of the most recent run of anomalous readings (tolerating 2 noisy gaps in a row)."""
    start, misses = None, 0
    for p in reversed(points):
        if check(p.value):
            start, misses = p.ts, 0
        elif start is not None:
            misses += 1
            if misses > 2:
                break
    return start
