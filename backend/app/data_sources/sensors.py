"""Simulated IoT street water-level sensors (MQTT-style messages).

Each message has a topic that encodes the sensor ID, an epoch-seconds timestamp and a
JSON-encoded payload string with the level in millimetres — yet another format to normalize.
"""

import json
from datetime import datetime

from app.data_sources.city_model import CityModel
from app.geo.zones import ZONES


def synthetic_messages(model: CityModel, now: datetime, malformed: bool = False) -> list[dict]:
    messages = []
    for zone in ZONES:
        for sensor_id, kind, _, _ in zone.sensors:
            if kind != "water_level":
                continue
            level_cm = model.value(zone.id, "water_level_cm", now, key=sensor_id)
            payload = {"lvl_mm": round(level_cm * 10), "bat": 87}
            raw_payload = json.dumps(payload)
            if malformed and model.rng("wl-bad", sensor_id, int(now.timestamp())).random() < 0.4:
                raw_payload = "{lvl_mm: oops"
            messages.append({
                "topic": f"city/sensors/{sensor_id}/level",
                "ts": int(now.timestamp()),
                "payload": raw_payload,
            })
    return messages
