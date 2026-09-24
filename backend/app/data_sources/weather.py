"""Weather feed — two possible upstreams with different formats.

1. Synthetic "CPMET" rain-gauge network (default). Vendor quirks we must normalize:
   precipitation in mm per 15 minutes, temperature in °F, wind in m/s,
   local time with a +05:30 offset.
2. Open-Meteo current-conditions API (optional, free, no key), queried at each zone centroid.
"""

from datetime import datetime

import httpx

from app.data_sources.city_model import CityModel
from app.geo.zones import ZONES


def synthetic_payload(model: CityModel, now: datetime, malformed: bool = False) -> dict:
    stations = []
    for zone in ZONES:
        sensor_id, _, lat, lon = next(s for s in zone.sensors if s[1] == "rain_gauge")
        rain = model.value(zone.id, "rain_mm_h", now)
        temp_c = model.value(zone.id, "temperature_c", now)
        wind = model.value(zone.id, "wind_kmh", now)
        station = {
            "station": sensor_id,
            "lat": lat,
            "lon": lon,
            "obs_time": now.astimezone(model.tz).isoformat(timespec="seconds"),
            "precip_mm_15min": round(rain / 4, 3),
            "temp_f": round(temp_c * 9 / 5 + 32, 1),
            "wind_ms": round(wind / 3.6, 2),
        }
        if malformed and model.rng("wx-bad", zone.id, int(now.timestamp())).random() < 0.4:
            station["precip_mm_15min"] = "N/A"
        stations.append(station)
    return {
        "network": "CPMET",
        "generated": now.astimezone(model.tz).strftime("%Y-%m-%d %H:%M:%S IST"),
        "stations": stations,
    }


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_open_meteo(client: httpx.Client, timeout: float) -> list[dict]:
    """One request for all zone centroids. Returns one result object per zone (same order)."""
    lats = ",".join(f"{z.centroid[0]:.4f}" for z in ZONES)
    lons = ",".join(f"{z.centroid[1]:.4f}" for z in ZONES)
    resp = client.get(
        OPEN_METEO_URL,
        params={
            "latitude": lats,
            "longitude": lons,
            "current": "temperature_2m,precipitation,wind_speed_10m",
            "timezone": "GMT",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]
