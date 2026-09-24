"""One normalizer per raw format → the common civic data model.

Each normalizer:
  1. reads the vendor's field names,
  2. parses the vendor's timestamp convention into UTC,
  3. converts units to CityPulse canonical units,
  4. maps the vendor's location/identifier to a CityPulse zone,
  5. validates values, and
  6. rejects bad records individually (with a reason) so good records still flow.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app.analysis.metrics import INCIDENT_CATEGORIES
from app.data_sources.incidents import SERVICE_NAMES
from app.data_sources.traffic import TRANSIT_AREA_CODES
from app.geo.zones import SENSOR_REGISTRY, ZONES, zone_for_point
from app.normalization.timestamps import TimestampError, parse_timestamp
from app.normalization.units import (
    fahrenheit_to_celsius,
    mm_to_cm,
    ms_to_kmh,
    per_interval_to_per_hour,
    pm25_to_us_aqi,
    validate_value,
)
from app.schemas import CivicIncident, CivicReading, DataStatus, SourceType


@dataclass
class NormalizationResult:
    readings: list[CivicReading] = field(default_factory=list)
    incidents: list[CivicIncident] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)  # human-readable reasons

    def extend(self, other: "NormalizationResult") -> None:
        self.readings += other.readings
        self.incidents += other.incidents
        self.rejected += other.rejected


@dataclass(frozen=True)
class Context:
    """Shared information every normalizer needs."""

    tz: ZoneInfo
    now: datetime
    data_status: DataStatus
    provider: str


def _reading(ctx: Context, source: str, source_type: SourceType, zone_id: str, ts: datetime,
             metric: str, value: float, unit: str, **extra) -> CivicReading:
    return CivicReading(
        source=source, source_type=source_type, provider=ctx.provider, zone_id=zone_id,
        timestamp=ts, ingested_at=ctx.now, metric=metric, value=round(value, 2), unit=unit,
        data_status=ctx.data_status, **extra,
    )


# ---------------------------------------------------------------------------- weather

def normalize_cpmet_weather(raw: dict, ctx: Context) -> NormalizationResult:
    out = NormalizationResult()
    for st in raw.get("stations", []):
        sid = st.get("station", "?")
        try:
            reg = SENSOR_REGISTRY.get(sid)
            zone_id = reg[0] if reg else zone_for_point(float(st["lat"]), float(st["lon"]))
            if zone_id is None:
                raise ValueError("station outside the city")
            ts = parse_timestamp(st.get("obs_time"), ctx.tz, now=ctx.now)
            rain = per_interval_to_per_hour(validate_value("rain_mm_h", st.get("precip_mm_15min")), 15)
            temp = validate_value("temperature_c", fahrenheit_to_celsius(float(st["temp_f"])))
            wind = validate_value("wind_kmh", ms_to_kmh(float(st["wind_ms"])))
        except (ValueError, KeyError, TypeError, TimestampError) as exc:
            out.rejected.append(f"weather station {sid}: {exc}")
            continue
        common = dict(sensor_id=sid, lat=st.get("lat"), lon=st.get("lon"))
        out.readings += [
            _reading(ctx, "weather", SourceType.WEATHER, zone_id, ts, "rain_mm_h", rain, "mm/h", **common),
            _reading(ctx, "weather", SourceType.WEATHER, zone_id, ts, "temperature_c", temp, "°C", **common),
            _reading(ctx, "weather", SourceType.WEATHER, zone_id, ts, "wind_kmh", wind, "km/h", **common),
        ]
    return out


def normalize_open_meteo_weather(raw: list[dict], ctx: Context) -> NormalizationResult:
    """Open-Meteo returns one object per requested location, in request order (= ZONES order)."""
    out = NormalizationResult()
    for zone, item in zip(ZONES, raw):
        try:
            cur = item["current"]
            ts = parse_timestamp(cur["time"], ZoneInfo("UTC"), now=ctx.now)
            interval_min = float(cur.get("interval", 900)) / 60
            rain = per_interval_to_per_hour(validate_value("rain_mm_h", cur.get("precipitation")), interval_min)
            temp = validate_value("temperature_c", cur.get("temperature_2m"))
            wind = validate_value("wind_kmh", cur.get("wind_speed_10m"))
        except (ValueError, KeyError, TypeError, TimestampError) as exc:
            out.rejected.append(f"open-meteo {zone.id}: {exc}")
            continue
        out.readings += [
            _reading(ctx, "weather", SourceType.WEATHER, zone.id, ts, "rain_mm_h", rain, "mm/h"),
            _reading(ctx, "weather", SourceType.WEATHER, zone.id, ts, "temperature_c", temp, "°C"),
            _reading(ctx, "weather", SourceType.WEATHER, zone.id, ts, "wind_kmh", wind, "km/h"),
        ]
    return out


# ---------------------------------------------------------------------------- traffic

def normalize_tsn_traffic(raw: dict, ctx: Context) -> NormalizationResult:
    out = NormalizationResult()
    for row in raw.get("readings", []):
        sid = row.get("sensorId", "?")
        try:
            reg = SENSOR_REGISTRY.get(sid)
            if reg is None:
                raise ValueError("unknown sensor")
            zone_id, _, lat, lon = reg
            ts = parse_timestamp(row.get("epochMs"), ctx.tz, now=ctx.now)
            speed = validate_value("avg_speed_kmh", row.get("speedKph"))
            free_flow = float(row.get("freeFlowKph") or 0)
            if free_flow <= 0:
                raise ValueError("missing free-flow speed")
            congestion = validate_value("congestion_pct", max(0.0, (1 - speed / free_flow) * 100))
        except (ValueError, TypeError, TimestampError) as exc:
            out.rejected.append(f"traffic sensor {sid}: {exc}")
            continue
        common = dict(sensor_id=sid, lat=lat, lon=lon)
        out.readings += [
            _reading(ctx, "traffic", SourceType.TRAFFIC, zone_id, ts, "congestion_pct", congestion, "%", **common),
            _reading(ctx, "traffic", SourceType.TRAFFIC, zone_id, ts, "avg_speed_kmh", speed, "km/h", **common),
        ]
    return out


def normalize_transit_csv(raw: str, ctx: Context) -> NormalizationResult:
    out = NormalizationResult()
    lines = [ln for ln in raw.strip().splitlines() if ln.strip()]
    if not lines:
        return out
    header = [h.strip() for h in lines[0].split(",")]
    for line in lines[1:]:
        cells = [c.strip() for c in line.split(",")]
        if len(cells) != len(header):
            out.rejected.append(f"transit row {line!r}: wrong column count")
            continue
        row = dict(zip(header, cells))
        try:
            zone_id = TRANSIT_AREA_CODES.get(row["stop_area"])
            if zone_id is None:
                raise ValueError(f"unknown area code {row['stop_area']!r}")
            ts = parse_timestamp(row["reported_at"], ctx.tz, now=ctx.now)
            delay = validate_value("transit_delay_min", float(row["delay_seconds"]) / 60)
        except (ValueError, KeyError, TimestampError) as exc:
            out.rejected.append(f"transit {row.get('route_id', '?')}: {exc}")
            continue
        out.readings.append(_reading(
            ctx, "traffic", SourceType.TRAFFIC, zone_id, ts, "transit_delay_min", delay, "min",
            metadata={"route_id": row["route_id"]},
        ))
    return out


# -------------------------------------------------------------------------- incidents

_SERVICE_TO_CATEGORY = {v.lower(): k for k, v in SERVICE_NAMES.items()}
_ALLOWED_INCIDENT_FIELDS = {"service_request_id", "service_name", "requested_datetime", "lat", "long", "status"}


def normalize_open311(raw: list[dict], ctx: Context) -> NormalizationResult:
    """Only whitelisted, non-personal fields survive; everything else is discarded."""
    out = NormalizationResult()
    for item in raw:
        rid = item.get("service_request_id", "?")
        try:
            category = _SERVICE_TO_CATEGORY.get(str(item.get("service_name", "")).strip().lower())
            if category is None:
                raise ValueError(f"unknown service {item.get('service_name')!r}")
            lat, lon = float(item["lat"]), float(item["long"])
            zone_id = zone_for_point(lat, lon)
            if zone_id is None:
                raise ValueError("location outside the city")
            ts = parse_timestamp(item.get("requested_datetime"), ctx.tz, now=ctx.now)
        except (ValueError, KeyError, TypeError, TimestampError) as exc:
            out.rejected.append(f"report {rid}: {exc}")
            continue
        dropped = sorted(set(item) - _ALLOWED_INCIDENT_FIELDS)
        out.incidents.append(CivicIncident(
            id=str(rid), source="incidents", zone_id=zone_id, timestamp=ts, ingested_at=ctx.now,
            category=category, severity=INCIDENT_CATEGORIES[category]["severity"],
            lat=round(lat, 4), lon=round(lon, 4),  # ~10 m precision is enough for a civic map
            data_status=ctx.data_status,
            metadata={"personal_fields_dropped": len(dropped)} if dropped else {},
        ))
    return out


# ------------------------------------------------------------------------ air quality

def normalize_openaq(raw: dict, ctx: Context) -> NormalizationResult:
    out = NormalizationResult()
    for row in raw.get("results", []):
        sid = row.get("location", "?")
        try:
            if row.get("parameter") != "pm25":
                raise ValueError(f"unsupported parameter {row.get('parameter')!r}")
            reg = SENSOR_REGISTRY.get(sid)
            if reg:
                zone_id = reg[0]
            else:
                coords = row["coordinates"]
                zone_id = zone_for_point(float(coords["latitude"]), float(coords["longitude"]))
            if zone_id is None:
                raise ValueError("monitor outside the city")
            ts = parse_timestamp((row.get("date") or {}).get("utc"), ctx.tz, now=ctx.now)
            pm25 = validate_value("pm25_ugm3", row.get("value"))
        except (ValueError, KeyError, TypeError, TimestampError) as exc:
            out.rejected.append(f"air monitor {sid}: {exc}")
            continue
        common = dict(sensor_id=sid, lat=(row.get("coordinates") or {}).get("latitude"),
                      lon=(row.get("coordinates") or {}).get("longitude"))
        out.readings += [
            _reading(ctx, "air_quality", SourceType.AIR_QUALITY, zone_id, ts, "pm25_ugm3", pm25, "µg/m³", **common),
            _reading(ctx, "air_quality", SourceType.AIR_QUALITY, zone_id, ts, "aqi", pm25_to_us_aqi(pm25), "AQI",
                     metadata={"derived_from": "pm25 (US EPA breakpoints)"}, **common),
        ]
    return out


def normalize_open_meteo_aq(raw: list[dict], ctx: Context) -> NormalizationResult:
    out = NormalizationResult()
    for zone, item in zip(ZONES, raw):
        try:
            cur = item["current"]
            ts = parse_timestamp(cur["time"], ZoneInfo("UTC"), now=ctx.now)
            pm25 = validate_value("pm25_ugm3", cur.get("pm2_5"))
            aqi = validate_value("aqi", cur.get("us_aqi"))
        except (ValueError, KeyError, TypeError, TimestampError) as exc:
            out.rejected.append(f"open-meteo air {zone.id}: {exc}")
            continue
        out.readings += [
            _reading(ctx, "air_quality", SourceType.AIR_QUALITY, zone.id, ts, "pm25_ugm3", pm25, "µg/m³"),
            _reading(ctx, "air_quality", SourceType.AIR_QUALITY, zone.id, ts, "aqi", aqi, "AQI"),
        ]
    return out


# ------------------------------------------------------------------------ IoT sensors

def normalize_mqtt_water(raw: list[dict], ctx: Context) -> NormalizationResult:
    out = NormalizationResult()
    for msg in raw:
        topic = str(msg.get("topic", ""))
        parts = topic.split("/")
        sid = parts[2] if len(parts) >= 4 else "?"
        try:
            reg = SENSOR_REGISTRY.get(sid)
            if reg is None:
                raise ValueError(f"unknown topic {topic!r}")
            zone_id, _, lat, lon = reg
            ts = parse_timestamp(msg.get("ts"), ctx.tz, now=ctx.now)
            payload = json.loads(msg.get("payload") or "")
            level = validate_value("water_level_cm", mm_to_cm(float(payload["lvl_mm"])))
        except (ValueError, KeyError, TypeError, TimestampError) as exc:
            out.rejected.append(f"sensor {sid}: {exc}")
            continue
        out.readings.append(_reading(
            ctx, "iot_sensors", SourceType.IOT_SENSORS, zone_id, ts, "water_level_cm", level, "cm",
            sensor_id=sid, lat=lat, lon=lon,
        ))
    return out

