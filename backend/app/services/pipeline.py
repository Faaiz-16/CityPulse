"""The CityPulse pipeline: one ``tick`` runs the whole flow.

    simulation step → poll feeds (with fallback) → normalize → store → persist
      → analyse (anomalies, relationships, risk, status) → monitoring agent
      → plain-language summary → ticker / timeline → CityState

The API only reads the latest ``CityState``, so requests are fast and never trigger work.
"""

import logging
import threading
from collections import deque
from datetime import UTC, datetime, timedelta

import httpx

from app.agent.monitor import MonitoringAgent
from app.ai.summarizer import Summarizer
from app.analysis.baseline import BaselineModel
from app.analysis.engine import AnalysisEngine
from app.analysis.metrics import INCIDENT_CATEGORIES, METRICS
from app.config import Settings, get_settings
from app.data_sources.city_model import CityModel
from app.geo.zones import SENSOR_REGISTRY, ZONES_BY_ID
from app.normalization.normalizers import Context
from app.schemas import (
    CityState,
    DataStatus,
    FeedStatus,
    SummarySection,
    TickerEvent,
    ZoneState,
)
from app.services.feed_manager import FEEDS, SYNTHETIC_PROVIDER, FeedManager
from app.services.persistence import Persistence
from app.services.store import ReadingStore
from app.simulation.controller import SimulationController

log = logging.getLogger("citypulse.pipeline")

SNAPSHOT_EVERY = timedelta(seconds=15)
TIMELINE_LENGTH = timedelta(minutes=30)
WARM_UP = timedelta(minutes=10)


class CityPulse:
    def __init__(self, settings: Settings | None = None, http_client: httpx.Client | None = None,
                 persistence: Persistence | None = None) -> None:
        self.s = settings or get_settings()
        self.model = CityModel(seed=self.s.random_seed, tz=self.s.tz)
        self.store = ReadingStore()
        self.feeds = FeedManager(self.s, self.model, http_client)
        self.baselines = BaselineModel(self.s.tz)
        self.engine = AnalysisEngine(self.s, self.baselines)
        self.summarizer = Summarizer(self.s)
        self.db = persistence or Persistence()
        self.agent = MonitoringAgent(persist=self.db.save_alert)
        self.sim = SimulationController(self.model)

        self.state: CityState | None = None
        self.zone_explanations: dict[str, SummarySection] = {}
        self.ticker: deque[TickerEvent] = deque(maxlen=80)
        self.timeline: deque[tuple[datetime, dict[str, str]]] = deque()
        self._lock = threading.RLock()
        self._prev_zones: dict[str, ZoneState] = {}
        self._prev_feed_status: dict[str, FeedStatus] = {}
        self._last_snapshot: datetime | None = None
        self._last_prune_db: datetime | None = None
        self.started_at: datetime | None = None
        self.tick_count = 0
        self.last_tick_error: str | None = None

    # ------------------------------------------------------------------ start-up
    def startup(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        self.started_at = now
        if self.db.init():
            self.db.clear_live()  # each run starts a fresh live session; history is kept
        readings, incidents = self.db.ensure_history(self.model, now, self.s.history_days)
        self.baselines.fit(readings, incidents)
        if not readings:
            log.warning("no history available — using default baselines")
        self.warm_up(now)
        self.tick(now)

    def warm_up(self, now: datetime) -> None:
        """Fill the rolling window with the last few minutes so analysis is meaningful at once."""
        for spec in FEEDS:
            if self.feeds.uses_live(spec):
                continue
            t = now - WARM_UP
            step = timedelta(seconds=spec.interval_s)
            while t < now - step:
                ctx = Context(self.s.tz, t, DataStatus.SIMULATED, SYNTHETIC_PROVIDER)
                result = spec.synthetic(self.model, t - step, t, False, ctx)
                self.store.add_readings(result.readings)
                self.store.add_incidents(result.incidents)
                t += step
            state = self.feeds.state[spec.id]
            state.last_success_at = t - step
            state.last_poll_at = None

    # ---------------------------------------------------------------------- tick
    def tick(self, now: datetime | None = None) -> CityState:
        with self._lock:
            now = now or datetime.now(UTC)
            try:
                return self._tick(now)
            except Exception as exc:  # keep serving the previous state rather than crashing
                self.last_tick_error = exc.__class__.__name__
                log.exception("pipeline tick failed")
                if self.state is None:
                    raise
                return self.state

    def _tick(self, now: datetime) -> CityState:
        for line in self.sim.advance(now):
            self._ticker(now, None, "simulation", line)
        self.feeds.live_paused = bool(self.model.effects)

        result, _ = self.feeds.poll(now)
        self.store.add_readings(result.readings)
        new_incidents = self.store.add_incidents(result.incidents)
        self.db.save_live(result.readings, new_incidents)
        self.store.prune(now)

        feed_health = self.feeds.health(now)
        zones, pulse = self.engine.analyze(self.store, now, self.feeds.intervals(),
                                           self.feeds.available("incidents", now))
        alert_events = self.agent.run(zones, feed_health, now)
        summary, zone_sections = self.summarizer.summarize(zones, feed_health, now)
        for label in self.sim.observe(zones, now):
            self._ticker(now, self.sim.scenario.focus_zone if self.sim.scenario else None,
                         "simulation", f"Scenario stage reached: {label}")

        self._update_ticker(now, zones, feed_health, new_incidents, alert_events)
        self._update_timeline(now, zones)

        self.state = CityState(
            generated_at=now, city_name=self.s.city_name, pulse=pulse, zones=zones, feeds=feed_health,
            alerts=self.agent.active() + self.agent.recent_resolved(6), summary=summary,
            ticker=list(self.ticker)[::-1][:40], simulation=self.sim.status(now),
            config=self.public_config(),
        )
        self.zone_explanations = zone_sections
        self.tick_count += 1
        self.last_tick_error = None

        if self._last_prune_db is None or now - self._last_prune_db > timedelta(minutes=10):
            self._last_prune_db = now
            self.db.clear_live(older_than=now - timedelta(hours=6))
        return self.state

    # --------------------------------------------------------------- simulation
    def trigger_event(self, event: str, zone_id: str, intensity: float = 1.0, duration_s: float = 600.0,
                      now: datetime | None = None) -> str:
        with self._lock:
            now = now or datetime.now(UTC)
            effect = self.sim.trigger(event, zone_id, now, intensity, duration_s)
            self.db.save_simulation_event(now, event, zone_id, {"intensity": intensity, "duration_s": duration_s})
            self._ticker(now, zone_id, "simulation", f"Simulation: {effect.label} started.")
            return effect.label

    def run_full_scenario(self, now: datetime | None = None) -> None:
        with self._lock:
            now = now or datetime.now(UTC)
            self.reset(now, announce=False)
            self.sim.start_full_scenario(now)
            self.db.save_simulation_event(now, "full_scenario", "Z3", {})

    def set_feed_fault(self, feed_id: str, mode: str, now: datetime | None = None) -> None:
        with self._lock:
            now = now or datetime.now(UTC)
            self.feeds.set_fault(feed_id, mode)
            self.db.save_simulation_event(now, "feed_fault", None, {"feed": feed_id, "mode": mode})
            text = "restored" if mode == "none" else f"fault injected: {mode}"
            self._ticker(now, None, "feed", f"Demo: {feed_id.replace('_', ' ')} feed {text}.")

    def reset(self, now: datetime | None = None, announce: bool = True) -> None:
        with self._lock:
            now = now or datetime.now(UTC)
            self.sim.clear()
            self.feeds.clear_faults()
            self.store.clear()
            self.agent.reset()
            self.ticker.clear()
            self.timeline.clear()
            self._prev_zones.clear()
            self._prev_feed_status.clear()
            self.db.clear_live()
            self.db.save_simulation_event(now, "reset", None, {})
            self.warm_up(now)
            if announce:
                self._ticker(now, None, "simulation", "Simulation reset: the city is back to normal.")
            self.tick(now)

    # ------------------------------------------------------------------- views
    def zone_detail(self, zone_id: str, now: datetime | None = None) -> dict:
        now = now or (self.state.generated_at if self.state else datetime.now(UTC))
        zone_state = next(z for z in self.state.zones if z.id == zone_id)
        start = now - timedelta(minutes=15)
        series = {}
        for key in ("rain_mm_h", "congestion_pct", "transit_delay_min", "aqi", "water_level_cm",
                    "temperature_c"):
            points = self.store.series(zone_id, key, start, now)
            series[key] = _downsample(points, start, now, 20)
        reports = self.store.incidents(start, now, zone_id)
        per_minute: dict[str, int] = {}
        for r in reports:
            minute = r.timestamp.replace(second=0, microsecond=0).isoformat()
            per_minute[minute] = per_minute.get(minute, 0) + 1
        explanation = self.zone_explanations.get(zone_id)
        return {
            "zone": zone_state,
            "explanation": explanation,
            "explanation_by": self.state.summary.generated_by if self.state else "template",
            "series": series,
            "baselines": {k: self.baselines.continuous(zone_id, k, now).median for k in series},
            "reports_per_minute": [{"minute": k, "count": v} for k, v in sorted(per_minute.items())],
            "sensors": [s for s in self.sensor_list() if s["zone_id"] == zone_id],
            "alerts": [a for a in self.agent.active() if a.zone_id == zone_id],
            "agent_trace": self.agent.trace,
        }

    def sensor_list(self) -> list[dict]:
        out = []
        for sid, (zone_id, kind, lat, lon) in SENSOR_REGISTRY.items():
            latest = self.store.sensors.get(sid, {}).get("values", {})
            out.append({"id": sid, "zone_id": zone_id, "kind": kind, "lat": lat, "lon": lon,
                        "values": latest})
        return out

    def timeline_view(self) -> list[dict]:
        return [{"at": t, "zones": statuses} for t, statuses in self.timeline]

    def public_config(self) -> dict:
        s = self.s
        return {
            "rolling_window_minutes": s.rolling_window_minutes,
            "current_window_seconds": s.current_window_seconds,
            "tick_seconds": s.tick_seconds,
            "live_apis": s.live_apis,
            "ai_enabled": s.ai_enabled,
            "ai_status": self.summarizer.status,
            "timezone": s.city_timezone,
            "thresholds": {
                "traffic_pct": s.traffic_threshold_pct, "transit_pct": s.transit_threshold_pct,
                "incident_pct": s.incident_threshold_pct, "incident_min_count": s.incident_min_count,
                "heavy_rain_mm_h": s.heavy_rain_mm_h, "aqi": s.aqi_threshold, "aqi_pct": s.aqi_threshold_pct,
                "water_level_cm": s.water_level_threshold_cm,
            },
            "baseline_history_days": self.baselines.history_days,
        }

    # ------------------------------------------------------------------ ticker
    def _ticker(self, at: datetime, zone_id: str | None, kind: str, text: str, severity: str = "none") -> None:
        self.ticker.append(TickerEvent(at=at, zone_id=zone_id, kind=kind, text=text, severity=severity))

    def _update_ticker(self, now, zones: list[ZoneState], feeds, new_incidents, alert_events) -> None:
        for inc in new_incidents[-6:]:
            zone = ZONES_BY_ID[inc.zone_id]
            self._ticker(inc.timestamp, inc.zone_id, "incident",
                         f"{zone.short_name}: {INCIDENT_CATEGORIES[inc.category]['label']} reported",
                         "low" if inc.severity == "low" else "moderate")

        for z in zones:
            prev = self._prev_zones.get(z.id)
            prev_anoms = {a.metric for a in prev.anomalies} if prev else set()
            for a in z.anomalies:
                if a.metric not in prev_anoms:
                    self._ticker(now, z.id, "anomaly", f"{z.short_name}: {a.description}", a.severity)
            for metric in prev_anoms - {a.metric for a in z.anomalies}:
                self._ticker(now, z.id, "anomaly", f"{z.short_name}: {METRICS[metric].label} back within normal range")
            prev_links = {r.id for r in prev.relationships if r.strength != "weak"} if prev else set()
            for r in z.relationships:
                if r.strength != "weak" and r.id not in prev_links:
                    self._ticker(now, z.id, "relationship",
                                 f"{z.short_name}: possible link — {r.title.lower()} ({r.strength})", "moderate")
            if prev and prev.status != z.status:
                self._ticker(now, z.id, "status", f"{z.name} is now {z.status.value} — {z.status_label}",
                             "high" if z.status.value == "RED" else "low")
            self._prev_zones[z.id] = z

        for event, alert in alert_events:
            prefix = {"opened": "Agent alert", "escalated": "Agent escalated", "resolved": "Agent resolved"}[event]
            self._ticker(now, alert.zone_id, "alert", f"{prefix}: {alert.title}",
                         "high" if alert.level == "critical" and event != "resolved" else "low")

        for f in feeds:
            prev = self._prev_feed_status.get(f.id)
            if prev is not None and prev != f.status:
                self._ticker(now, None, "feed", f"{f.label} feed is now {f.status.value}",
                             "moderate" if f.status not in (FeedStatus.LIVE, FeedStatus.SIMULATED) else "none")
            self._prev_feed_status[f.id] = f.status

    def _update_timeline(self, now: datetime, zones: list[ZoneState]) -> None:
        if self._last_snapshot and now - self._last_snapshot < SNAPSHOT_EVERY:
            return
        self._last_snapshot = now
        self.timeline.append((now, {z.id: z.status.value for z in zones}))
        while self.timeline and self.timeline[0][0] < now - TIMELINE_LENGTH:
            self.timeline.popleft()
        self.db.save_snapshot(now, zones)


def _downsample(points, start: datetime, end: datetime, bin_s: int) -> list[dict]:
    out, idx = [], 0
    t = start
    while t < end:
        t_next = t + timedelta(seconds=bin_s)
        bucket = []
        while idx < len(points) and points[idx].ts < t_next:
            if points[idx].ts >= t:
                bucket.append(points[idx].value)
            idx += 1
        out.append({"t": t_next, "v": round(sum(bucket) / len(bucket), 2) if bucket else None})
        t = t_next
    return out

