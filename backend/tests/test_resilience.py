"""Feed failures, fallbacks, stale data and database outages (feed-failure scenarios 1–5)."""

from datetime import timedelta

import httpx
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.data_sources.city_model import CityModel
from app.schemas import DataStatus, FeedStatus
from app.services.feed_manager import FeedManager
from app.services.persistence import Persistence
from app.services.pipeline import CityPulse
from tests.conftest import T0


def status(p: CityPulse, feed_id: str) -> FeedStatus:
    return next(f for f in p.state.feeds if f.id == feed_id).status


def run(p: CityPulse, seconds: int, step: int = 3):
    for i in range(1, seconds // step + 1):
        p.tick(T0 + timedelta(seconds=i * step))


# Scenario 1 — weather unavailable
def test_weather_outage_keeps_everything_else_running(pipeline):
    pipeline.set_feed_fault("weather", "outage", now=T0)
    run(pipeline, 12)  # weather polls every 10 s
    assert status(pipeline, "weather") == FeedStatus.FALLBACK  # last known values, clearly labelled
    assert status(pipeline, "traffic") == FeedStatus.SIMULATED
    assert status(pipeline, "incidents") == FeedStatus.SIMULATED
    run(pipeline, 150)
    assert status(pipeline, "weather") == FeedStatus.UNAVAILABLE
    z3 = next(z for z in pipeline.state.zones if z.id == "Z3")
    assert z3.metrics["rain_mm_h"].available is False
    assert z3.metrics["congestion_pct"].available is True
    assert any(a.kind == "data_quality" for a in pipeline.state.alerts)
    assert "weather" in pipeline.state.summary.sections.possible_connection.lower()


# Scenario 1b — weather outage while traffic spikes: say what can't be checked
def test_weather_outage_during_traffic_spike_reports_cannot_assess(pipeline):
    pipeline.set_feed_fault("weather", "outage", now=T0)
    pipeline.trigger_event("traffic_spike", "Z3", now=T0)
    for i in range(1, 70):
        pipeline.tick(T0 + timedelta(seconds=3 * i))
    z3 = next(z for z in pipeline.state.zones if z.id == "Z3")
    assert z3.metrics["congestion_pct"].is_anomaly
    assert any("Weather data is unavailable" in n for n in z3.cannot_assess)


# Scenario 2 — traffic unavailable
def test_traffic_outage_does_not_break_dashboard(pipeline):
    pipeline.set_feed_fault("traffic", "outage", now=T0)
    run(pipeline, 150)
    assert status(pipeline, "traffic") == FeedStatus.UNAVAILABLE
    assert status(pipeline, "weather") == FeedStatus.SIMULATED
    assert len(pipeline.state.zones) == 5


def test_delayed_feed_becomes_delayed_then_stale(pipeline):
    pipeline.set_feed_fault("air_quality", "delay", now=T0)
    run(pipeline, 66)
    assert status(pipeline, "air_quality") == FeedStatus.DELAYED
    run(pipeline, 180)
    assert status(pipeline, "air_quality") == FeedStatus.STALE


def test_feed_recovers_after_fault_cleared(pipeline):
    pipeline.set_feed_fault("incidents", "outage", now=T0)
    run(pipeline, 30)
    pipeline.set_feed_fault("incidents", "none", now=T0 + timedelta(seconds=30))
    for i in range(11, 15):
        pipeline.tick(T0 + timedelta(seconds=3 * i))
    assert status(pipeline, "incidents") == FeedStatus.SIMULATED


# Scenario 4 — malformed payloads
def test_malformed_records_rejected_valid_records_continue(pipeline):
    pipeline.set_feed_fault("incidents", "malformed", now=T0)
    pipeline.set_feed_fault("traffic", "malformed", now=T0)
    run(pipeline, 30)
    feeds = {f.id: f for f in pipeline.state.feeds}
    assert feeds["incidents"].records_rejected >= 4
    assert feeds["traffic"].records_rejected > 0
    assert feeds["traffic"].status == FeedStatus.SIMULATED  # still delivering valid data
    assert all(z.metrics["congestion_pct"].available for z in pipeline.state.zones)


# Live-API fallback chain (timeouts, HTTP errors, rate limits, garbage)
def _manager(handler) -> FeedManager:
    s = Settings(run_background_loop=False, live_apis=True)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return FeedManager(s, CityModel(seed=1, tz=s.tz), client)


def test_live_api_timeout_falls_back_to_labelled_synthetic():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)
    fm = _manager(handler)
    result, _ = fm.poll(T0)
    weather = [r for r in result.readings if r.source == "weather"]
    assert weather and all(r.data_status == DataStatus.FALLBACK for r in weather)
    health = {h.id: h for h in fm.health(T0)}
    assert health["weather"].status == FeedStatus.FALLBACK
    assert "timed out" in health["weather"].message
    assert "not live data" in health["weather"].message


def test_live_api_rate_limit_and_malformed_json_fall_back():
    fm = _manager(lambda req: httpx.Response(429, json={"error": "slow down"}))
    fm.poll(T0)
    assert "rate limit" in {h.id: h for h in fm.health(T0)}["weather"].message

    fm = _manager(lambda req: httpx.Response(200, text="<html>not json</html>"))
    result, _ = fm.poll(T0)
    assert {h.id: h for h in fm.health(T0)}["air_quality"].status == FeedStatus.FALLBACK
    assert all(r.data_status != DataStatus.LIVE for r in result.readings)


def test_live_api_success_is_labelled_live():
    def handler(request):
        cur = ({"time": "2026-09-24T09:30", "interval": 900, "temperature_2m": 31.2, "precipitation": 0.5,
                "wind_speed_10m": 8.0} if "forecast" in str(request.url)
               else {"time": "2026-09-24T09:30", "us_aqi": 92, "pm2_5": 31.0})
        return httpx.Response(200, json=[{"current": cur}] * 5)
    fm = _manager(handler)
    result, _ = fm.poll(T0)
    rain = [r for r in result.readings if r.metric == "rain_mm_h"]
    assert rain[0].data_status == DataStatus.LIVE and rain[0].value == 2.0  # 0.5 mm / 15 min
    assert {h.id: h for h in fm.health(T0)}["weather"].status == FeedStatus.LIVE


# Scenario 5 — database unavailable
class BrokenDB(Persistence):
    def _boom(self, *a, **k):
        self._fail("database call", OperationalError("stmt", {}, Exception("disk I/O error")))

    def init(self):
        self._boom()
        return False

    def ensure_history(self, *a, **k):
        self._boom()
        return [], []

    def save_live(self, *a, **k):
        self._boom()

    def save_snapshot(self, *a, **k):
        self._boom()

    def save_simulation_event(self, *a, **k):
        self._boom()

    def clear_live(self, *a, **k):
        self._boom()

    def save_alert(self, *a, **k):
        self._boom()
        raise OperationalError("stmt", {}, Exception("disk I/O error"))


def test_database_outage_keeps_live_pulse_running(settings):
    p = CityPulse(settings, persistence=BrokenDB())
    p.startup(T0)  # must not raise
    p.trigger_event("heavy_rain", "Z3", now=T0)
    for i in range(1, 40):
        p.tick(T0 + timedelta(seconds=3 * i))
    assert p.db.ok is False
    assert p.state is not None and len(p.state.zones) == 5
    assert p.state.config["baseline_history_days"] == 0  # fell back to default baselines
    assert next(z for z in p.state.zones if z.id == "Z3").metrics["rain_mm_h"].is_anomaly
