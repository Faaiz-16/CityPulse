"""Synthetic multi-day history.

Used for two things:
  * learning baselines ("what does Zone 3 traffic normally look like at 6 p.m.?")
  * historical replay of a recorded storm (yesterday evening, Zones 3 and 4)

History is sampled every 5 minutes from the same deterministic city model.
"""

from datetime import datetime, timedelta

from app.data_sources.city_model import CityModel, Effect
from app.data_sources.incidents import request_id
from app.analysis.metrics import INCIDENT_CATEGORIES
from app.geo.zones import ZONE_IDS
from app.normalization.units import pm25_to_us_aqi

HISTORY_STEP = timedelta(minutes=5)
_UNITS = {"rain_mm_h": "mm/h", "temperature_c": "°C", "wind_kmh": "km/h", "congestion_pct": "%",
          "avg_speed_kmh": "km/h", "transit_delay_min": "min", "pm25_ugm3": "µg/m³", "aqi": "AQI",
          "water_level_cm": "cm"}
_SOURCES = {"rain_mm_h": "weather", "temperature_c": "weather", "wind_kmh": "weather",
            "congestion_pct": "traffic", "avg_speed_kmh": "traffic", "transit_delay_min": "traffic",
            "pm25_ugm3": "air_quality", "aqi": "air_quality", "water_level_cm": "iot_sensors"}


def recorded_storm_window(now: datetime, model: CityModel) -> tuple[datetime, datetime]:
    """Yesterday 18:00–19:45 local time: the recorded storm available for replay."""
    local = now.astimezone(model.tz)
    start = (local - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    return start, start + timedelta(minutes=105)


def storm_effects(now: datetime, model: CityModel) -> list[Effect]:
    start, _ = recorded_storm_window(now, model)
    return [
        Effect("heavy_rain", "Z3", start + timedelta(minutes=15), ramp_s=600, hold_s=2400, fade_s=900,
               label="Recorded storm (Zone 3)"),
        Effect("heavy_rain", "Z4", start + timedelta(minutes=30), ramp_s=600, hold_s=1500, fade_s=900,
               intensity=0.7, label="Recorded storm (Zone 4)"),
    ]


def generate_history(model: CityModel, now: datetime, days: int) -> tuple[list[dict], list[dict]]:
    """Return (reading rows, incident rows) ready for bulk insert."""
    history_model = CityModel(seed=model.seed, tz=model.tz, effects=storm_effects(now, model))
    end = now - timedelta(minutes=15)
    t = (end - timedelta(days=days)).replace(second=0, microsecond=0)
    readings, incidents = [], []
    while t < end:
        for zone in ZONE_IDS:
            values = {m: history_model.value(zone, m, t, key="hist") for m in
                      ("rain_mm_h", "temperature_c", "wind_kmh", "congestion_pct", "transit_delay_min",
                       "pm25_ugm3", "water_level_cm")}
            values["avg_speed_kmh"] = round(45.0 * (1 - values["congestion_pct"] / 100), 2)
            values["aqi"] = pm25_to_us_aqi(values["pm25_ugm3"])
            for metric, value in values.items():
                readings.append({
                    "source": _SOURCES[metric], "source_type": _SOURCES[metric], "provider": "synthetic history",
                    "zone_id": zone, "ts": t, "ingested_at": t, "metric": metric, "value": value,
                    "unit": _UNITS[metric], "confidence": 1.0, "data_status": "simulated", "sensor_id": None,
                    "is_history": True, "meta": {},
                })
            for rec in history_model.incidents_between(zone, t, t + HISTORY_STEP):
                incidents.append({
                    "id": request_id("hist-" + rec["key"]), "source": "incidents", "zone_id": zone,
                    "ts": rec["ts"], "ingested_at": rec["ts"], "category": rec["category"],
                    "severity": INCIDENT_CATEGORIES[rec["category"]]["severity"], "lat": rec["lat"],
                    "lon": rec["lon"], "data_status": "simulated", "is_history": True, "meta": {},
                })
        t += HISTORY_STEP
    return readings, incidents
