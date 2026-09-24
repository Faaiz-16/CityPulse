"""Anomaly detection, rolling-window correlation and possible-impact logic."""

from datetime import UTC, datetime, timedelta

import pytest

from app.analysis.anomaly import assess_continuous, assess_incident_count, poisson_tail
from app.analysis.baseline import Baseline
from app.analysis.correlation import ZoneSignals, evaluate_zone
from app.analysis.metrics import METRICS
from app.analysis.risk import assess_risks, zone_status
from app.config import Settings
from app.schemas import Anomaly, MetricAssessment, ZoneStatus
from app.services.store import Point

NOW = datetime(2026, 9, 24, 9, 30, tzinfo=UTC)
S = Settings(run_background_loop=False)
CAUSAL = ("caused", "because of", "due to", "led to", "triggered")


def pts(*values: float) -> list[Point]:
    return [Point(NOW - timedelta(seconds=5 * (len(values) - i)), v, "simulated", None)
            for i, v in enumerate(values)]


# ------------------------------------------------------------------- anomaly

def test_traffic_example_from_brief_147_vs_100_is_anomaly():
    m = assess_continuous(METRICS["congestion_pct"], pts(147, 147), pts(147), Baseline(100, 5, 50, "history"), S)
    assert m.deviation_pct == 47.0
    assert m.is_anomaly and m.severity == "moderate"
    assert m.threshold == "≥ 30% above normal"


def test_traffic_below_threshold_is_not_anomaly():
    m = assess_continuous(METRICS["congestion_pct"], pts(125), pts(125), Baseline(100, 5, 50, "history"), S)
    assert m.deviation_pct == 25.0 and not m.is_anomaly and m.severity == "none"


def test_rain_uses_absolute_threshold():
    base = Baseline(0, 0, 50, "history")
    assert not assess_continuous(METRICS["rain_mm_h"], pts(5), pts(5), base, S).is_anomaly
    heavy = assess_continuous(METRICS["rain_mm_h"], pts(10), pts(10), base, S)
    assert heavy.is_anomaly and heavy.severity == "moderate"
    assert assess_continuous(METRICS["rain_mm_h"], pts(20), pts(20), base, S).severity == "high"


def test_missing_data_is_marked_unavailable_not_zero():
    m = assess_continuous(METRICS["rain_mm_h"], [], [], Baseline(0, 0, 50, "history"), S)
    assert m.available is False and m.current is None and not m.is_anomaly


def test_trend_detection():
    m = assess_continuous(METRICS["congestion_pct"], pts(40), pts(30, 31, 33, 36, 39, 42),
                          Baseline(35, 2, 50, "history"), S)
    assert m.trend == "rising"


def test_incident_spike_requires_statistical_significance():
    # 4 reports when ~2 are expected happens often by chance → not a spike
    assert not assess_incident_count(METRICS["incident_reports"], 4, 2.2, S, NOW, True, "steady").is_anomaly
    # 8 reports when ~2.2 are expected: unusual but still plausible by chance across many checks
    assert not assess_incident_count(METRICS["incident_reports"], 8, 2.2, S, NOW, True, "rising").is_anomaly
    # 11 reports when ~2.2 are expected is very unlikely by chance → spike
    assert assess_incident_count(METRICS["incident_reports"], 11, 2.2, S, NOW, True, "rising").is_anomaly
    # 3 waterlogging reports when ~0.1 expected → spike
    assert assess_incident_count(METRICS["waterlogging_reports"], 3, 0.1, S, NOW, True, "rising").is_anomaly


def test_poisson_tail():
    assert poisson_tail(0, 2) == 1.0
    assert poisson_tail(8, 2.15) < 0.01 < poisson_tail(6, 2.15)


# --------------------------------------------------------------- correlation

def metric(key: str, current: float | None, baseline: float, dev: float | None, anomaly: bool,
           severity: str = "none", available: bool = True, trend: str = "steady") -> MetricAssessment:
    m = METRICS[key]
    return MetricAssessment(metric=key, label=m.label, unit=m.unit, source=m.source.value, current=current,
                            baseline=baseline, deviation_pct=dev, robust_z=None, threshold="rule",
                            is_anomaly=anomaly, severity=severity, trend=trend, samples=5,
                            last_updated=NOW, data_status="simulated", available=available)


def normal_zone() -> dict[str, MetricAssessment]:
    return {
        "rain_mm_h": metric("rain_mm_h", 0, 0, None, False),
        "congestion_pct": metric("congestion_pct", 36, 36, 0, False),
        "transit_delay_min": metric("transit_delay_min", 4, 4, 0, False),
        "aqi": metric("aqi", 78, 78, 0, False),
        "water_level_cm": metric("water_level_cm", 1.5, 1.5, 0, False),
        "waterlogging_reports": metric("waterlogging_reports", 0, 0.15, -100, False),
        "outage_signal_reports": metric("outage_signal_reports", 0, 0.1, -100, False),
        "incident_reports": metric("incident_reports", 2, 2.1, -5, False),
    }


def rising(n=30, start=0.0, step=1.0):
    return [start + i * step for i in range(n)]


def test_rain_and_traffic_same_zone_produce_hedged_relationship():
    ms = normal_zone()
    ms["rain_mm_h"] = metric("rain_mm_h", 26, 0, None, True, "high")
    ms["congestion_pct"] = metric("congestion_pct", 64, 36, 78, True, "high")
    onsets = {"rain_mm_h": NOW - timedelta(minutes=4), "congestion_pct": NOW - timedelta(minutes=2)}
    binned = {"rain_mm_h": rising(), "congestion_pct": rising(start=36)}
    rels, insufficient, cannot = evaluate_zone(ZoneSignals("Z3", "Zone 3 — East", ms, onsets, binned), S)
    rel = next(r for r in rels if r.rule_id == "rain_traffic")
    assert rel.strength == "strong"
    assert "may be related" in rel.statement
    assert "not a confirmed cause" in rel.caveat
    assert rel.co_movement_r == pytest.approx(1.0)
    assert any("Same zone" in e for e in rel.evidence)
    assert "became unusual first" in rel.lead_lag
    text = " ".join([rel.statement, rel.caveat, *rel.evidence]).lower()
    assert not any(word in text for word in CAUSAL)


def test_rain_alone_gives_insufficient_evidence_not_a_relationship():
    ms = normal_zone()
    ms["rain_mm_h"] = metric("rain_mm_h", 26, 0, None, True, "high")
    rels, insufficient, _ = evaluate_zone(ZoneSignals("Z2", "Zone 2 — North", ms, {}), S)
    assert rels == []
    assert "no disruption link detected" in insufficient[0]


def test_traffic_alone_is_not_blamed_on_anything():
    ms = normal_zone()
    ms["congestion_pct"] = metric("congestion_pct", 60, 36, 66, True, "high")
    rels, insufficient, _ = evaluate_zone(ZoneSignals("Z1", "Zone 1 — Central", ms, {}), S)
    assert rels == []
    assert "insufficient evidence" in insufficient[0]


def test_unavailable_weather_is_reported_as_cannot_assess():
    ms = normal_zone()
    ms["rain_mm_h"] = metric("rain_mm_h", None, 0, None, False, available=False)
    ms["congestion_pct"] = metric("congestion_pct", 60, 36, 66, True, "high")
    rels, _, cannot = evaluate_zone(ZoneSignals("Z3", "Zone 3 — East", ms, {}), S)
    assert rels == []
    assert "Weather data is unavailable" in cannot[0]


def test_response_before_driver_weakens_relationship():
    ms = normal_zone()
    ms["rain_mm_h"] = metric("rain_mm_h", 9, 0, None, True, "moderate")
    ms["congestion_pct"] = metric("congestion_pct", 50, 36, 39, True, "low")
    onsets = {"rain_mm_h": NOW - timedelta(minutes=1), "congestion_pct": NOW - timedelta(minutes=8)}
    rels, _, _ = evaluate_zone(ZoneSignals("Z3", "Zone 3 — East", ms, onsets), S)
    rel = rels[0]
    assert rel.strength == "weak"
    assert "does not fit" in rel.lead_lag
    assert "insufficient" in rel.statement


# ---------------------------------------------------------------------- risk

def anomaly(key: str, severity: str) -> Anomaly:
    return Anomaly(id=key, zone_id="Z3", metric=key, label=METRICS[key].label, severity=severity, current=1,
                   baseline=1, deviation_pct=1, unit="", since=NOW, description=f"{key} unusual")


def test_potential_disruption_needs_relationship_and_two_serious_anomalies():
    ms = normal_zone()
    ms["rain_mm_h"] = metric("rain_mm_h", 26, 0, None, True, "high")
    ms["congestion_pct"] = metric("congestion_pct", 64, 36, 78, True, "high")
    onsets = {"rain_mm_h": NOW - timedelta(minutes=4), "congestion_pct": NOW - timedelta(minutes=3)}
    rels, _, _ = evaluate_zone(ZoneSignals("Z3", "Zone 3 — East", ms, onsets), S)
    anomalies = [anomaly("rain_mm_h", "high"), anomaly("congestion_pct", "high")]
    risks = assess_risks("Z3", "Zone 3 — East", ms, anomalies, rels, S)
    assert risks[0].kind == "potential_disruption"
    assert risks[0].headline == "Elevated traffic disruption risk in Zone 3 — East"
    assert zone_status(anomalies, rels, risks) == ZoneStatus.RED


def test_early_warning_before_traffic_crosses_threshold():
    ms = normal_zone()
    ms["rain_mm_h"] = metric("rain_mm_h", 20, 0, None, True, "high")
    ms["congestion_pct"] = metric("congestion_pct", 43, 36, 19, False, trend="rising")
    anomalies = [anomaly("rain_mm_h", "high")]
    risks = assess_risks("Z3", "Zone 3 — East", ms, anomalies, [], S)
    assert [r.kind for r in risks] == ["early_warning"]
    assert zone_status(anomalies, [], risks) == ZoneStatus.YELLOW


def test_normal_zone_is_green():
    assert zone_status([], [], []) == ZoneStatus.GREEN


def test_small_report_baselines_are_described_without_huge_percentages():
    from app.analysis.metrics import usual_reports
    assert usual_reports(0.2, 2500) == "normally fewer than 1"
    assert usual_reports(2.2, 355.0) == "normally about 2.2, +355%"


def test_live_aqi_uses_only_the_health_threshold_not_a_synthetic_baseline():
    live = [Point(NOW - timedelta(seconds=30), 169, "live", None)]
    m = assess_continuous(METRICS["aqi"], live, live, Baseline(84, 5, 50, "history"), S)
    assert m.is_anomaly and m.baseline is None and m.deviation_pct is None
    from app.analysis.engine import describe_anomaly
    assert "unhealthy threshold" in describe_anomaly(m)
