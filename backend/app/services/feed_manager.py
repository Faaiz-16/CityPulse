"""Polls every feed, applies the fallback chain, and tracks feed health.

Fallback chain for a feed with a live public API (weather, air quality):

    live API ──ok──▶ LIVE readings
       │ timeout / HTTP error / rate limit / malformed
       ▼
    synthetic estimate, clearly labelled FALLBACK  (never presented as live)

Feeds whose upstream is the synthetic city model (traffic, incidents, sensors) have no
second source, so when they fail CityPulse shows the last known values as FALLBACK for a
short while, then marks the feed UNAVAILABLE. Analysis never invents data for a missing
feed — it reports what it cannot assess instead.

Demo fault modes (set from the demo panel) simulate upstream problems:
  outage    — every request fails
  delay     — the upstream silently stops sending new data
  malformed — some records arrive broken and must be rejected individually
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

from app.config import Settings
from app.data_sources import air_quality, incidents, sensors, traffic, weather
from app.data_sources.city_model import CityModel
from app.normalization import normalizers as norm
from app.schemas import DataStatus, FeedHealth, FeedStatus, SourceType

log = logging.getLogger("citypulse.feeds")

FAULT_MODES = ("none", "outage", "delay", "malformed")
SYNTHETIC_PROVIDER = "synthetic city model"
LIVE_PROVIDER = "Open-Meteo (public API)"


class FeedError(Exception):
    pass


@dataclass
class FeedSpec:
    id: str
    label: str
    source_type: SourceType
    interval_s: float
    synthetic: Callable[[CityModel, datetime, datetime, bool, norm.Context], norm.NormalizationResult]
    live: Callable[[httpx.Client, float, norm.Context], norm.NormalizationResult] | None = None


@dataclass
class FeedState:
    fault_mode: str = "none"
    last_poll_at: datetime | None = None
    last_success_at: datetime | None = None
    last_attempt_failed: bool = False
    last_error: str | None = None
    using_fallback: bool = False
    live_retry_after: datetime | None = None
    accepted: int = 0
    rejected: int = 0
    last_rejections: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ feed adapters

def _weather_synthetic(model, since, now, bad, ctx):
    return norm.normalize_cpmet_weather(weather.synthetic_payload(model, now, bad), ctx)


def _weather_live(client, timeout, ctx):
    return norm.normalize_open_meteo_weather(weather.fetch_open_meteo(client, timeout), ctx)


def _traffic_synthetic(model, since, now, bad, ctx):
    out = norm.normalize_tsn_traffic(traffic.synthetic_road_payload(model, now, bad), ctx)
    out.extend(norm.normalize_transit_csv(traffic.synthetic_transit_csv(model, now, bad), ctx))
    return out


def _incidents_synthetic(model, since, now, bad, ctx):
    return norm.normalize_open311(incidents.synthetic_payload(model, since, now, bad), ctx)


def _aq_synthetic(model, since, now, bad, ctx):
    return norm.normalize_openaq(air_quality.synthetic_payload(model, now, bad), ctx)


def _aq_live(client, timeout, ctx):
    return norm.normalize_open_meteo_aq(air_quality.fetch_open_meteo(client, timeout), ctx)


def _sensors_synthetic(model, since, now, bad, ctx):
    return norm.normalize_mqtt_water(sensors.synthetic_messages(model, now, bad), ctx)


FEEDS: tuple[FeedSpec, ...] = (
    FeedSpec("weather", "Weather", SourceType.WEATHER, 10, _weather_synthetic, _weather_live),
    FeedSpec("traffic", "Traffic & transit", SourceType.TRAFFIC, 5, _traffic_synthetic),
    FeedSpec("incidents", "Civic reports (311)", SourceType.INCIDENTS, 5, _incidents_synthetic),
    FeedSpec("air_quality", "Air quality", SourceType.AIR_QUALITY, 20, _aq_synthetic, _aq_live),
    FeedSpec("iot_sensors", "Water-level sensors", SourceType.IOT_SENSORS, 10, _sensors_synthetic),
)
FEEDS_BY_ID = {f.id: f for f in FEEDS}


class FeedManager:
    def __init__(self, settings: Settings, model: CityModel,
                 http_client: httpx.Client | None = None) -> None:
        self.s = settings
        self.model = model
        self.http = http_client or httpx.Client(headers={"User-Agent": "CityPulse/1.0"})
        self.state: dict[str, FeedState] = {f.id: FeedState() for f in FEEDS}
        self.live_paused = False  # set while a simulation scenario is driving the city

    # ------------------------------------------------------------------ config
    def uses_live(self, spec: FeedSpec) -> bool:
        return bool(self.s.live_apis and spec.live and not self.live_paused)

    def interval(self, spec: FeedSpec) -> float:
        return float(self.s.live_refresh_seconds) if self.uses_live(spec) else spec.interval_s

    def intervals(self) -> dict[str, float]:
        return {f.id: self.interval(f) for f in FEEDS}

    def set_fault(self, feed_id: str, mode: str) -> None:
        if feed_id not in self.state:
            raise ValueError(f"unknown feed {feed_id!r}")
        if mode not in FAULT_MODES:
            raise ValueError(f"unknown fault mode {mode!r}")
        self.state[feed_id].fault_mode = mode

    def clear_faults(self) -> None:
        for st in self.state.values():
            st.fault_mode = "none"

    # -------------------------------------------------------------------- poll
    def poll(self, now: datetime, force: bool = False) -> tuple[norm.NormalizationResult, dict[str, int]]:
        """Poll every feed that is due. Returns merged results and per-feed rejected counts."""
        merged = norm.NormalizationResult()
        rejected: dict[str, int] = {}
        for spec in FEEDS:
            st = self.state[spec.id]
            if not force and st.last_poll_at and (now - st.last_poll_at).total_seconds() < self.interval(spec) - 0.5:
                continue
            since = st.last_success_at or (now - timedelta(seconds=spec.interval_s))
            st.last_poll_at = now
            result = self._poll_one(spec, st, since, now)
            if result is not None:
                merged.extend(result)
                rejected[spec.id] = len(result.rejected)
        return merged, rejected

    def _poll_one(self, spec: FeedSpec, st: FeedState, since: datetime,
                  now: datetime) -> norm.NormalizationResult | None:
        if st.fault_mode == "delay":
            return None  # upstream silently not sending; freshness checks will notice

        try:
            if st.fault_mode == "outage":
                raise FeedError("upstream not responding (simulated outage)")
            result = self._fetch(spec, st, since, now)
        except Exception as exc:  # one broken feed must never stop the others
            st.last_attempt_failed = True
            st.last_error = _friendly_error(exc)
            log.warning("feed %s failed: %s", spec.id, exc)
            if spec.live and self.uses_live(spec) and st.fault_mode != "outage":
                return self._synthetic_fallback(spec, st, since, now)
            st.using_fallback = False
            return None

        st.last_attempt_failed = False
        st.last_error = None
        st.last_success_at = now
        st.accepted += len(result.readings) + len(result.incidents)
        st.rejected += len(result.rejected)
        st.last_rejections = result.rejected[-5:]
        return result

    def _fetch(self, spec: FeedSpec, st: FeedState, since: datetime, now: datetime) -> norm.NormalizationResult:
        bad = st.fault_mode == "malformed"
        if self.uses_live(spec):
            if st.live_retry_after and now < st.live_retry_after:
                return self._synthetic_fallback(spec, st, since, now, count_success=False)
            ctx = norm.Context(self.s.tz, now, DataStatus.LIVE, LIVE_PROVIDER)
            try:
                result = spec.live(self.http, self.s.api_timeout_seconds, ctx)
            except Exception:
                st.live_retry_after = now + timedelta(seconds=60)  # back off before retrying
                raise
            if not result.readings:
                raise FeedError("live API returned no usable records")
            st.using_fallback = False
            return result
        ctx = norm.Context(self.s.tz, now, DataStatus.SIMULATED, SYNTHETIC_PROVIDER)
        st.using_fallback = False
        return spec.synthetic(self.model, since, now, bad, ctx)

    def _synthetic_fallback(self, spec: FeedSpec, st: FeedState, since: datetime, now: datetime,
                            count_success: bool = True) -> norm.NormalizationResult:
        ctx = norm.Context(self.s.tz, now, DataStatus.FALLBACK, SYNTHETIC_PROVIDER + " (fallback)")
        result = spec.synthetic(self.model, since, now, False, ctx)
        st.using_fallback = True
        if count_success:
            st.last_success_at = now
        return result

    # ------------------------------------------------------------------ health
    def health(self, now: datetime) -> list[FeedHealth]:
        return [self._health_one(spec, now) for spec in FEEDS]

    def available(self, feed_id: str, now: datetime) -> bool:
        return self._health_one(FEEDS_BY_ID[feed_id], now).status not in (
            FeedStatus.UNAVAILABLE, FeedStatus.STALE)

    def _health_one(self, spec: FeedSpec, now: datetime) -> FeedHealth:
        st = self.state[spec.id]
        interval = self.interval(spec)
        age = (now - st.last_success_at).total_seconds() if st.last_success_at else None
        provider = LIVE_PROVIDER if self.uses_live(spec) else SYNTHETIC_PROVIDER
        cache_ttl = max(90.0, self.s.stale_after_intervals * interval)

        if st.using_fallback and not st.last_attempt_failed and st.fault_mode != "outage":
            status, msg = FeedStatus.FALLBACK, "Live API unavailable — showing simulated estimates, not live data."
        elif st.last_attempt_failed:
            if st.using_fallback:
                status, msg = FeedStatus.FALLBACK, (f"{st.last_error}. Showing simulated estimates, "
                                                    "not live data.")
            elif age is not None and age <= cache_ttl:
                status, msg = FeedStatus.FALLBACK, (f"{st.last_error}. Showing last known values "
                                                    f"from {_ago(age)}.")
            else:
                status, msg = FeedStatus.UNAVAILABLE, f"{st.last_error}. No recent data."
        elif age is None:
            status, msg = FeedStatus.UNAVAILABLE, "No data received yet."
        elif age > self.s.unavailable_after_minutes * 60:
            status, msg = FeedStatus.UNAVAILABLE, f"No data for {_ago(age)}."
        elif age > self.s.stale_after_intervals * interval:
            status, msg = FeedStatus.STALE, f"Last update {_ago(age)} — data is stale."
        elif age > self.s.delayed_after_intervals * interval:
            status, msg = FeedStatus.DELAYED, f"Last update {_ago(age)} — updates are late."
        elif self.uses_live(spec):
            status, msg = FeedStatus.LIVE, "Receiving live data."
        else:
            status, msg = FeedStatus.SIMULATED, "Receiving simulated data (demo city)."

        if st.fault_mode == "malformed" and st.last_rejections and status in (
                FeedStatus.LIVE, FeedStatus.SIMULATED):
            msg += f" Some records were malformed and rejected ({len(st.last_rejections)} recently)."

        return FeedHealth(
            id=spec.id, label=spec.label, source_type=spec.source_type, status=status, provider=provider,
            last_success_at=st.last_success_at, age_seconds=round(age, 1) if age is not None else None,
            expected_interval_seconds=interval, message=msg, fault_mode=st.fault_mode,
            records_accepted=st.accepted, records_rejected=st.rejected,
        )


def _ago(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)} s ago"
    return f"{int(seconds // 60)} min ago"


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "Upstream API timed out"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return "Upstream API rate limit reached" if code == 429 else f"Upstream API returned HTTP {code}"
    if isinstance(exc, httpx.HTTPError):
        return "Upstream API unreachable"
    if isinstance(exc, FeedError):
        return str(exc).capitalize()
    return "Upstream returned an unexpected response"
