"""Catalogue of every metric CityPulse understands and how each one is judged.

``mode`` decides how "unusual" is measured:
  * ``relative``  — % deviation from the learned baseline (traffic, transit, incidents)
  * ``absolute``  — fixed physical threshold, because the normal value is ~0
                    and a % change is meaningless (rain, standing water)
  * ``hybrid``    — anomaly if EITHER the absolute limit OR the relative limit is crossed (AQI)
  * ``info``      — displayed for context, never flagged on its own
"""

from dataclasses import dataclass
from typing import Literal

from app.schemas import SourceType


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    unit: str
    source: SourceType
    mode: Literal["relative", "absolute", "hybrid", "info"]
    icon: str
    higher_is_worse: bool = True


METRICS: dict[str, MetricDef] = {
    m.key: m
    for m in (
        MetricDef("rain_mm_h", "Rainfall", "mm/h", SourceType.WEATHER, "absolute", "rain"),
        MetricDef("temperature_c", "Temperature", "°C", SourceType.WEATHER, "info", "temp"),
        MetricDef("wind_kmh", "Wind", "km/h", SourceType.WEATHER, "info", "wind"),
        MetricDef("congestion_pct", "Traffic congestion", "%", SourceType.TRAFFIC, "relative", "traffic"),
        MetricDef("avg_speed_kmh", "Average road speed", "km/h", SourceType.TRAFFIC, "info", "traffic", False),
        MetricDef("transit_delay_min", "Bus delays", "min", SourceType.TRAFFIC, "relative", "transit"),
        MetricDef("aqi", "Air quality (US AQI)", "AQI", SourceType.AIR_QUALITY, "hybrid", "air"),
        MetricDef("pm25_ugm3", "PM2.5", "µg/m³", SourceType.AIR_QUALITY, "info", "air"),
        MetricDef("water_level_cm", "Street water level", "cm", SourceType.IOT_SENSORS, "absolute", "water"),
        # Derived from incident reports inside the rolling window:
        MetricDef("incident_reports", "Civic reports (all)", "reports", SourceType.INCIDENTS, "relative", "incident"),
        MetricDef("waterlogging_reports", "Waterlogging reports", "reports", SourceType.INCIDENTS, "relative", "water"),
        MetricDef("outage_signal_reports", "Power / signal outage reports", "reports", SourceType.INCIDENTS, "relative", "incident"),
    )
}


def verb_for(label: str) -> str:
    """'is' or 'are' for a metric label ("Bus delays are…", "Civic reports (all) are…")."""
    return "are" if label.split(" (")[0].endswith("s") else "is"


CONTINUOUS_METRICS = tuple(k for k, m in METRICS.items() if m.source != SourceType.INCIDENTS)

INCIDENT_CATEGORIES: dict[str, dict[str, str]] = {
    "waterlogging": {"label": "Waterlogging", "severity": "moderate"},
    "pothole": {"label": "Pothole", "severity": "low"},
    "streetlight": {"label": "Streetlight out", "severity": "low"},
    "garbage": {"label": "Garbage not collected", "severity": "low"},
    "noise": {"label": "Noise complaint", "severity": "low"},
    "tree_fall": {"label": "Fallen tree", "severity": "moderate"},
    "power_outage": {"label": "Power outage", "severity": "high"},
    "traffic_signal": {"label": "Traffic signal down", "severity": "moderate"},
    "road_accident": {"label": "Road accident", "severity": "high"},
}

# Which incident categories feed which derived metric.
DERIVED_INCIDENT_METRICS: dict[str, tuple[str, ...] | None] = {
    "incident_reports": None,  # None = every category
    "waterlogging_reports": ("waterlogging",),
    "outage_signal_reports": ("power_outage", "traffic_signal"),
}
