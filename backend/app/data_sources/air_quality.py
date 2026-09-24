"""Air-quality feed.

1. Synthetic monitors in an OpenAQ-like shape (default): PM2.5 concentration only, nested
   ``date.utc`` timestamp, nested coordinates. CityPulse computes the US AQI itself.
2. Open-Meteo air-quality API (optional), which already provides ``us_aqi`` and ``pm2_5``.
"""

from datetime import UTC, datetime

import httpx

from app.data_sources.city_model import CityModel
from app.geo.zones import ZONES


def synthetic_payload(model: CityModel, now: datetime, malformed: bool = False) -> dict:
    results = []
    for zone in ZONES:
        sensor_id, _, lat, lon = next(s for s in zone.sensors if s[1] == "air_quality")
        value = model.value(zone.id, "pm25_ugm3", now, key=sensor_id)
        row = {
            "location": sensor_id,
            "parameter": "pm25",
            "value": value,
            "unit": "µg/m³",
            "date": {"utc": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")},
            "coordinates": {"latitude": lat, "longitude": lon},
        }
        if malformed and model.rng("aq-bad", zone.id, int(now.timestamp())).random() < 0.4:
            row.pop("value")
        results.append(row)
    return {"meta": {"found": len(results)}, "results": results}


OPEN_METEO_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def fetch_open_meteo(client: httpx.Client, timeout: float) -> list[dict]:
    lats = ",".join(f"{z.centroid[0]:.4f}" for z in ZONES)
    lons = ",".join(f"{z.centroid[1]:.4f}" for z in ZONES)
    resp = client.get(
        OPEN_METEO_AQ_URL,
        params={"latitude": lats, "longitude": lons, "current": "us_aqi,pm2_5", "timezone": "GMT"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]
