"""Traffic / transit feed — two sub-feeds in two unrelated formats.

* Road sensors ("TSN v2" JSON): camelCase fields, epoch-millisecond timestamps, raw speed
  (congestion must be derived from speed vs free-flow speed).
* Bus operator delays (CSV text): route-level rows, delay in seconds, day-first local
  timestamps, and the operator's own area codes (CEN/NTH/...) instead of our zone IDs.
"""

from datetime import datetime

from app.data_sources.city_model import FREE_FLOW_KMH, CityModel
from app.geo.zones import ZONES

# The bus operator's area codes -> CityPulse zone IDs (an identifier mismatch to reconcile).
TRANSIT_AREA_CODES = {"CEN": "Z1", "NTH": "Z2", "EST": "Z3", "STH": "Z4", "WST": "Z5"}
_ZONE_TO_AREA = {v: k for k, v in TRANSIT_AREA_CODES.items()}
_ROUTES = {"Z1": ("R-101", "R-104"), "Z2": ("R-210",), "Z3": ("R-312", "R-315"),
           "Z4": ("R-420",), "Z5": ("R-507",)}


def synthetic_road_payload(model: CityModel, now: datetime, malformed: bool = False) -> dict:
    readings = []
    for zone in ZONES:
        for sensor_id, kind, _, _ in zone.sensors:
            if kind != "traffic":
                continue
            speed = model.speed_kmh(zone.id, now, key=sensor_id)
            row = {
                "sensorId": sensor_id,
                "epochMs": int(now.timestamp() * 1000),
                "speedKph": speed,
                "freeFlowKph": FREE_FLOW_KMH,
                "laneCount": 3,
            }
            if malformed and model.rng("tr-bad", sensor_id, int(now.timestamp())).random() < 0.35:
                row["speedKph"] = -12.0  # impossible value
            readings.append(row)
    return {"feed": "tsn/v2", "count": len(readings), "readings": readings}


def synthetic_transit_csv(model: CityModel, now: datetime, malformed: bool = False) -> str:
    local = now.astimezone(model.tz).strftime("%d/%m/%Y %H:%M:%S")
    lines = ["route_id,stop_area,delay_seconds,reported_at"]
    for zone in ZONES:
        for route in _ROUTES[zone.id]:
            delay_min = model.value(zone.id, "transit_delay_min", now, key=route)
            area = _ZONE_TO_AREA[zone.id]
            if malformed and model.rng("tx-bad", route, int(now.timestamp())).random() < 0.35:
                area = "???"
            lines.append(f"{route},{area},{round(delay_min * 60)},{local}")
    return "\n".join(lines)
