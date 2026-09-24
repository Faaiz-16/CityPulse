"""Possible-impact / risk insights and the zone traffic-light status.

Two kinds of insight, both built only from structured evidence:

* **Potential disruption** (high) — a relationship of at least moderate strength exists AND
  at least two signals in the zone are anomalous at moderate severity or worse.
  Example: heavy rain + traffic +80% + waterlogging reports rising, same zone, same window.

* **Early warning** (elevated) — the "driver" is already anomalous and a related signal is
  clearly moving the same way but has not crossed its threshold yet.
  Example: heavy rain and congestion already +15% and rising → traffic may slow soon.
  This addresses the PDF pain point "alerts are reactive, not predictive".
"""

from app.config import Settings
from app.schemas import Anomaly, MetricAssessment, Relationship, RiskInsight, ZoneStatus

_SEV_RANK = {"none": 0, "low": 1, "moderate": 2, "high": 3}

_DISRUPTION_HEADLINES = {
    "rain_traffic": "Elevated traffic disruption risk",
    "rain_flooding": "Possible waterlogging disruption",
    "outage_traffic": "Possible disruption from outages",
    "traffic_air": "Traffic and air quality both worsening",
}

_ADVICE = {
    "rain_traffic": "Allow extra travel time and expect slower roads and buses.",
    "rain_flooding": "Avoid low-lying roads and underpasses where water may collect.",
    "outage_traffic": "Treat junctions with signals down as all-way stops; expect delays.",
    "traffic_air": "People sensitive to air pollution may want to limit time near busy roads.",
}


def assess_risks(zone_id: str, zone_name: str, metrics: dict[str, MetricAssessment],
                 anomalies: list[Anomaly], relationships: list[Relationship],
                 s: Settings) -> list[RiskInsight]:
    risks: list[RiskInsight] = []

    strong_links = [r for r in relationships if r.strength in ("moderate", "strong")]
    serious = [a for a in anomalies if _SEV_RANK[a.severity] >= 2]
    if strong_links and len(serious) >= 2:
        lead = max(strong_links, key=lambda r: r.score)
        evidence = [a.description for a in serious]
        evidence.append(f"Possible relationship: {lead.title.lower()} ({lead.strength}, score {lead.score:.2f})")
        risks.append(RiskInsight(
            id=f"{zone_id}:disruption", zone_id=zone_id, kind="potential_disruption", level="high",
            headline=f"{_DISRUPTION_HEADLINES[lead.rule_id]} in {zone_name}",
            evidence=evidence, resident_advice=_ADVICE[lead.rule_id],
        ))

    # Early warning: rain is heavy and traffic is climbing but not yet anomalous.
    rain = metrics.get("rain_mm_h")
    traffic = metrics.get("congestion_pct")
    if (rain and rain.is_anomaly and traffic and traffic.available and not traffic.is_anomaly
            and traffic.deviation_pct is not None and traffic.deviation_pct >= 10
            and traffic.trend == "rising"):
        risks.append(RiskInsight(
            id=f"{zone_id}:early_traffic", zone_id=zone_id, kind="early_warning", level="elevated",
            headline=f"Traffic may slow in {zone_name}",
            evidence=[f"Rainfall: {rain.current:g} mm/h (heavy)",
                      f"Traffic congestion already {traffic.deviation_pct:+.0f}% above normal and rising",
                      f"Anomaly threshold for traffic is {s.traffic_threshold_pct:g}% — not crossed yet"],
            resident_advice="If you are about to travel through this area, consider leaving earlier.",
        ))

    water = metrics.get("water_level_cm")
    if (rain and rain.is_anomaly and water and water.available and not water.is_anomaly
            and water.current is not None and water.current >= s.water_level_threshold_cm / 2
            and water.trend == "rising"):
        risks.append(RiskInsight(
            id=f"{zone_id}:early_water", zone_id=zone_id, kind="early_warning", level="elevated",
            headline=f"Water may collect on streets in {zone_name}",
            evidence=[f"Rainfall: {rain.current:g} mm/h (heavy)",
                      f"Street water level {water.current:g} cm and rising "
                      f"(flag level {s.water_level_threshold_cm:g} cm)"],
            resident_advice="Watch for standing water on low-lying roads.",
        ))
    return risks


def zone_status(anomalies: list[Anomaly], relationships: list[Relationship],
                risks: list[RiskInsight]) -> ZoneStatus:
    """GREEN = normal · YELLOW = attention · RED = possible disruption."""
    if any(r.kind == "potential_disruption" for r in risks):
        return ZoneStatus.RED
    if sum(1 for a in anomalies if a.severity == "high") >= 2:
        return ZoneStatus.RED
    if anomalies or risks or relationships:
        return ZoneStatus.YELLOW
    return ZoneStatus.GREEN


STATUS_LABELS = {
    ZoneStatus.GREEN: "Normal",
    ZoneStatus.YELLOW: "Attention",
    ZoneStatus.RED: "Possible disruption",
}
