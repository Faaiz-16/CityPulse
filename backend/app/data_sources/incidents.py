"""311-style civic reports in the Open311 GeoReport v2 shape.

Realistic quirks the normalizer has to handle:
  * ``service_name`` is free text ("Water Logging", "Streetlight out"), not our category key
  * timestamps are ISO-8601 in UTC ("Z")
  * longitude is called ``long``
  * upstream systems sometimes attach personal fields (account id, phone). CityPulse drops
    them during normalization and never stores them.
"""

import hashlib
from datetime import UTC, datetime

from app.data_sources.city_model import CityModel
from app.geo.zones import ZONE_IDS

# Upstream service names -> CityPulse category keys.
SERVICE_NAMES = {
    "waterlogging": "Water Logging",
    "pothole": "Pothole Repair",
    "streetlight": "Streetlight Out",
    "garbage": "Missed Garbage Pickup",
    "noise": "Noise Complaint",
    "tree_fall": "Fallen Tree",
    "power_outage": "Power Outage",
    "traffic_signal": "Traffic Signal Malfunction",
    "road_accident": "Road Accident",
}


def request_id(key: str) -> str:
    return "SR-" + hashlib.sha1(key.encode()).hexdigest()[:10].upper()


def synthetic_payload(
    model: CityModel, since: datetime, now: datetime, malformed: bool = False
) -> list[dict]:
    out: list[dict] = []
    for zone_id in ZONE_IDS:
        for rec in model.incidents_between(zone_id, since, now):
            item = {
                "service_request_id": request_id(rec["key"]),
                "service_name": SERVICE_NAMES[rec["category"]],
                "status": "open",
                "requested_datetime": rec["ts"].astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "lat": rec["lat"],
                "long": rec["lon"],
                # Personal data an upstream portal might leak; must be discarded.
                "account_id": "acct-" + rec["key"][-6:],
                "contact_phone": "+91-XXXXXXXXXX",
            }
            out.append(item)

    if malformed:
        rng = model.rng("inc-bad", int(now.timestamp()))
        stamp = now.astimezone(UTC).isoformat()
        out.extend([
            {"service_request_id": "SR-BAD-1", "service_name": "Water Logging",
             "requested_datetime": "yesterday-ish", "lat": 26.92, "long": 75.82},
            {"service_request_id": "SR-BAD-2", "service_name": "Pothole Repair",
             "requested_datetime": stamp, "lat": None, "long": 75.8},
            {"service_request_id": "SR-BAD-3", "service_name": "Alien Landing",
             "requested_datetime": stamp, "lat": 26.92, "long": 75.8},
            {"service_request_id": f"SR-BAD-4-{rng.randint(0, 999)}", "service_name": "Pothole Repair",
             "requested_datetime": stamp, "lat": 19.07, "long": 72.87},  # outside the city
        ])
    return out
