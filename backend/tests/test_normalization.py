from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.data_sources import incidents, sensors, traffic, weather
from app.data_sources.city_model import CityModel
from app.geo.zones import ZONE_IDS
from app.normalization import normalizers as norm
from app.normalization.timestamps import TimestampError, parse_timestamp
from app.normalization.units import fahrenheit_to_celsius, pm25_to_us_aqi, validate_value
from app.schemas import DataStatus

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 9, 24, 9, 30, tzinfo=UTC)
CTX = norm.Context(IST, NOW, DataStatus.SIMULATED, "test")


# ------------------------------------------------------------------ timestamps

@pytest.mark.parametrize("raw", [
    "2026-09-24T15:00:00+05:30",       # ISO with offset
    "2026-09-24T09:30:00Z",            # ISO UTC
    "2026-09-24T15:00",                # ISO without zone → city local time
    1790242200,                        # epoch seconds
    1790242200000,                     # epoch milliseconds
    "24/09/2026 15:00",                # day-first local text
    "2026-09-24 15:00:00 IST",         # zone abbreviation
])
def test_every_timestamp_format_maps_to_same_utc_instant(raw):
    assert parse_timestamp(raw, IST) == NOW


def test_future_timestamps_are_rejected():
    with pytest.raises(TimestampError):
        parse_timestamp((NOW + timedelta(hours=1)).isoformat(), IST, now=NOW)


@pytest.mark.parametrize("raw", [None, "", "yesterday-ish", "31/31/2026 10:00", True])
def test_bad_timestamps_raise(raw):
    with pytest.raises(TimestampError):
        parse_timestamp(raw, IST)


# ----------------------------------------------------------------------- units

def test_unit_conversions():
    assert fahrenheit_to_celsius(212) == pytest.approx(100)
    assert pm25_to_us_aqi(9.0) == 50
    assert pm25_to_us_aqi(35.4) == 100
    assert pm25_to_us_aqi(55.5) == 151


@pytest.mark.parametrize("metric,value", [("congestion_pct", 140), ("rain_mm_h", -1), ("aqi", "N/A"),
                                          ("aqi", None), ("aqi", float("nan"))])
def test_invalid_values_rejected(metric, value):
    with pytest.raises(ValueError):
        validate_value(metric, value)


# -------------------------------------------------------------------- per-feed

def test_weather_units_normalized():
    model = CityModel(seed=1, tz=IST)
    raw = weather.synthetic_payload(model, NOW)
    raw["stations"][0]["precip_mm_15min"] = 2.0  # 2 mm per 15 min = 8 mm/h
    raw["stations"][0]["temp_f"] = 86.0
    out = norm.normalize_cpmet_weather(raw, CTX)
    first = {r.metric: r for r in out.readings if r.sensor_id == raw["stations"][0]["station"]}
    assert first["rain_mm_h"].value == 8.0 and first["rain_mm_h"].unit == "mm/h"
    assert first["temperature_c"].value == pytest.approx(30.0)
    assert all(r.timestamp == NOW for r in out.readings)
    assert not out.rejected


def test_traffic_congestion_derived_from_speed_and_zone_from_sensor():
    raw = {"readings": [{"sensorId": "TS-C2-9-1", "epochMs": int(NOW.timestamp() * 1000),
                         "speedKph": 22.5, "freeFlowKph": 45}]}
    out = norm.normalize_tsn_traffic(raw, CTX)
    congestion = next(r for r in out.readings if r.metric == "congestion_pct")
    assert congestion.value == 50.0 and congestion.zone_id == "C2-9"


def test_transit_area_codes_mapped_and_unknown_codes_rejected():
    csv = "route_id,stop_area,delay_seconds,reported_at\nR-1,R6C9,300,24/09/2026 15:00\nR-2,???,60,24/09/2026 15:00"
    out = norm.normalize_transit_csv(csv, CTX)
    assert len(out.readings) == 1
    assert out.readings[0].zone_id == "C2-9" and out.readings[0].value == 5.0
    assert out.readings[0].timestamp == NOW
    assert "unknown area code" in out.rejected[0]


def test_incident_personal_fields_are_dropped():
    model = CityModel(seed=3, tz=IST)
    raw = []
    t = NOW - timedelta(minutes=30)
    while not raw:  # find a window with at least one report
        raw = incidents.synthetic_payload(model, t, t + timedelta(minutes=10))
        t += timedelta(minutes=10)
    out = norm.normalize_open311(raw, CTX)
    assert out.incidents
    dumped = out.incidents[0].model_dump_json()
    assert "acct-" not in dumped and "contact_phone" not in dumped and "XXXX" not in dumped
    assert out.incidents[0].metadata["personal_fields_dropped"] == 2


def test_malformed_incidents_rejected_individually_valid_ones_kept():
    model = CityModel(seed=3, tz=IST)
    raw = incidents.synthetic_payload(model, NOW - timedelta(minutes=30), NOW, malformed=True)
    out = norm.normalize_open311(raw, CTX)
    assert len(out.rejected) == 4  # bad timestamp, missing lat, unknown service, outside city
    assert len(out.incidents) == len(raw) - 4


def test_mqtt_sensor_payload_decoded_and_bad_json_rejected():
    model = CityModel(seed=1, tz=IST)
    msgs = sensors.synthetic_messages(model, NOW)
    msgs[0]["payload"] = "{broken"
    out = norm.normalize_mqtt_water(msgs, CTX)
    assert len(out.readings) == len(msgs) - 1
    assert all(r.unit == "cm" for r in out.readings)
    assert len(out.rejected) == 1


def test_transit_and_road_formats_both_feed_the_same_model():
    model = CityModel(seed=1, tz=IST)
    road = norm.normalize_tsn_traffic(traffic.synthetic_road_payload(model, NOW), CTX)
    transit = norm.normalize_transit_csv(traffic.synthetic_transit_csv(model, NOW), CTX)
    zones = {r.zone_id for r in road.readings} & {r.zone_id for r in transit.readings}
    assert zones == set(ZONE_IDS)  # every area has road sensors and a bus route
