"""Traffic / transit feed — two sub-feeds in two unrelated formats.

* Road sensors ("TSN v2" JSON): camelCase fields, epoch-millisecond timestamps, raw speed
  (congestion must be derived from speed vs free-flow speed).
* Bus operator delays (CSV text): route-level rows, delay in seconds, day-first local
  timestamps, and the operator's own depot codes (e.g. "R4C6") instead of our area IDs ("F4").
"""

from datetime import datetime

from app.data_sources.city_model import FREE_FLOW_KMH, CityModel
from app.data_sources.city_model import ZONE_CHARACTER
from app.geo.zones import ZONES

# The bus operator's depot codes (row/column, 1-based) -> CityPulse area IDs: an identifier
# mismatch the normalizer has to reconcile.
TRANSIT_AREA_CODES = {f"R{z.row + 1}C{z.col + 1}": z.id for z in ZONES}
_ZONE_TO_AREA = {v: k for k, v in TRANSIT_AREA_CODES.items()}
# Busier areas are served by two routes, quieter ones by one.
_ROUTES = {z.id: tuple(f"R-{z.number:02d}{s}" for s in ("A", "B")[: 2 if ZONE_CHARACTER[z.id]["traffic"] > 1.0 else 1])
           for z in ZONES}


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
