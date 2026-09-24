"""Historical replay: run a recorded civic event through the *same* pipeline stages.

    stored history ─► rolling store ─► AnalysisEngine ─► MonitoringAgent ─► templates ─► frames

Nothing here is scripted. The replay *finds* the recorded event in the archive (the stretch
where rainfall was heavy), loads the 1-minute archive around it, then steps a virtual clock one
minute at a time and records what CityPulse would have shown at each moment. Judges can scrub
back and forth and watch detection happen on past data.

Frames are computed once and cached, so scrubbing is instant and every viewer sees the same
thing (deterministic). With 81 areas a frame is large, so frames are kept compressed and
decoded when requested.
"""

import logging
import threading
import zlib
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import datetime, timedelta

from app.agent.monitor import MonitoringAgent
from app.ai import templates
from app.analysis.baseline import BaselineModel
from app.analysis.engine import AnalysisEngine
from app.analysis.metrics import INCIDENT_CATEGORIES
from app.config import Settings
from app.schemas import (
    CityState,
    CivicIncident,
    CivicReading,
    DataStatus,
    FeedHealth,
    FeedStatus,
    SourceType,
    Summary,
)
from app.services import views
from app.services.feed_manager import FEEDS
from app.services.persistence import Persistence
from app.services.store import ReadingStore
from app.services.ticker import Ticker
from app.simulation.controller import advance_stages, storm_stages
from app.simulation.history import ARCHIVE_STEP

log = logging.getLogger("citypulse.replay")

LEAD_IN = timedelta(minutes=20)  # show some calm before the event
TAIL = timedelta(minutes=25)  # and the recovery after it
WARM_UP = timedelta(minutes=15)  # history loaded before the first frame so windows are full
_SOURCE_TYPES = {"rain_mm_h": SourceType.WEATHER, "temperature_c": SourceType.WEATHER,
                 "wind_kmh": SourceType.WEATHER, "congestion_pct": SourceType.TRAFFIC,
                 "avg_speed_kmh": SourceType.TRAFFIC, "transit_delay_min": SourceType.TRAFFIC,
                 "pm25_ugm3": SourceType.AIR_QUALITY, "aqi": SourceType.AIR_QUALITY,
                 "water_level_cm": SourceType.IOT_SENSORS}
_UNITS = {"rain_mm_h": "mm/h", "temperature_c": "°C", "wind_kmh": "km/h", "congestion_pct": "%",
          "avg_speed_kmh": "km/h", "transit_delay_min": "min", "pm25_ugm3": "µg/m³", "aqi": "AQI",
          "water_level_cm": "cm"}


class ReplayUnavailable(Exception):
    pass


@dataclass
class Frame:
    blob: bytes  # zlib-compressed CityState JSON
    summary: dict  # {i, t, city_status, statuses} for the replay timeline
    agent_trace: list[str]

    @property
    def state(self) -> CityState:
        return _decode(self.blob)


@lru_cache(maxsize=12)
def _decode(blob: bytes) -> CityState:
    return CityState.model_validate_json(zlib.decompress(blob))


@dataclass
class ReplaySession:
    name: str
    start: datetime
    end: datetime
    focus_zone: str
    store: ReadingStore
    frames: list[Frame] = field(default_factory=list)
    key_moments: list[dict] = field(default_factory=list)


class ReplayService:
    """Builds and serves the replay of the recorded storm (lazily, once)."""

    def __init__(self, settings: Settings, baselines: BaselineModel, db: Persistence) -> None:
        self.s = settings
        self.baselines = baselines
        self.db = db
        self._session: ReplaySession | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ public
    def session(self) -> ReplaySession:
        with self._lock:
            if self._session is None:
                self._session = self._build()
            return self._session

    def meta(self) -> dict:
        r = self.session()
        return {
            "available": True,
            "name": r.name,
            "description": ("Recorded data from the archive, replayed through the same analysis engine "
                            "and monitoring agent that run live. Nothing here is live."),
            "focus_zone": r.focus_zone,
            "start": r.start,
            "end": r.end,
            "step_seconds": int(ARCHIVE_STEP.total_seconds()),
            "frames": [f.summary for f in r.frames],
            "key_moments": r.key_moments,
        }

    def frame(self, index: int) -> Frame:
        r = self.session()
        if not 0 <= index < len(r.frames):
            raise IndexError(index)
        return r.frames[index]

    def zone_detail(self, index: int, zone_id: str) -> dict:
        r = self.session()
        f = self.frame(index)
        state = f.state
        zone = next(z for z in state.zones if z.id == zone_id)
        return views.zone_detail(
            r.store, self.baselines, zone, state.generated_at, explanation=templates.zone_explanation(zone),
            explanation_by="template", alerts=[a for a in f.state.alerts if a.active],
            agent_trace=f.agent_trace, sensors=[], bin_s=60,
        )

    # ------------------------------------------------------------------- build
    def _build(self) -> ReplaySession:
        event = self.db.find_recorded_event("rain_mm_h", self.s.heavy_rain_mm_h)
        if event is None:
            raise ReplayUnavailable("No recorded event found in the stored history.")
        first, last = event
        start, end = first - LEAD_IN, last + TAIL
        readings, incidents = self.db.load_history_between(start - WARM_UP, end)
        if not readings:
            raise ReplayUnavailable("The recorded event's data could not be loaded.")

        store = ReadingStore(retention=timedelta(days=1))
        store.add_readings([
            CivicReading(source=_SOURCE_TYPES[m].value, source_type=_SOURCE_TYPES[m], provider="recorded archive",
                         zone_id=z, timestamp=t, ingested_at=t, metric=m, value=v, unit=_UNITS[m],
                         data_status=DataStatus.SIMULATED)
            for z, m, t, v in readings if m in _SOURCE_TYPES
        ])
        store.add_incidents([
            CivicIncident(id=i, source="incidents", zone_id=z, timestamp=t, ingested_at=t, category=c,
                          severity=sev, lat=la, lon=lo, data_status=DataStatus.SIMULATED)
            for i, z, c, sev, t, la, lo in incidents if c in INCIDENT_CATEGORIES
        ])

        local = first.astimezone(self.s.tz)
        session = ReplaySession(
            name=f"Recorded storm — {local.strftime('%d %b, %H:%M')} (local time)",
            start=start, end=end, focus_zone=self._focus_zone(readings), store=store,
        )
        self._compute_frames(session, incidents)
        log.info("replay ready: %d frames from %s", len(session.frames), start.isoformat())
        return session

    @staticmethod
    def _focus_zone(readings) -> str:
        peak: dict[str, float] = {}
        for z, m, _, v in readings:
            if m == "rain_mm_h":
                peak[z] = max(peak.get(z, 0.0), v)
        return max(peak, key=peak.get) if peak else "E6"

    def _compute_frames(self, session: ReplaySession, incidents: list[tuple]) -> None:
        engine = AnalysisEngine(self.s, self.baselines)
        agent = MonitoringAgent(persist=None)
        ticker = Ticker(maxlen=400)
        intervals = {spec.id: ARCHIVE_STEP.total_seconds() for spec in FEEDS}
        stages = storm_stages()
        ticker.add(session.start, None, "simulation", f"Replay started: {session.name}.")
        by_time = sorted(incidents, key=lambda row: row[4])
        idx = 0
        t = session.start
        while t <= session.end:
            new_incidents = []
            while idx < len(by_time) and by_time[idx][4] <= t:
                i, z, c, sev, ts, la, lo = by_time[idx]
                if ts > t - ARCHIVE_STEP and c in INCIDENT_CATEGORIES:
                    new_incidents.append(CivicIncident(id=i, source="incidents", zone_id=z, timestamp=ts,
                                                       ingested_at=ts, category=c, severity=sev, lat=la, lon=lo,
                                                       data_status=DataStatus.SIMULATED))
                idx += 1

            zones, pulse = engine.analyze(session.store, t, intervals, incidents_available=True)
            feeds = self._archive_feeds(t)
            alert_events = agent.run(zones, feeds, t)
            headline, sections = templates.city_summary(zones, [])
            ticker.update(t, zones, feeds, new_incidents, alert_events)

            focus = next(z for z in zones if z.id == session.focus_zone)
            for stage in advance_stages(stages, focus, t):
                if stage.key != "normal":
                    session.key_moments.append({"i": len(session.frames), "t": t, "label": stage.label})
                    ticker.add(t, session.focus_zone, "simulation", f"Replay: {stage.label.lower()}")

            state = CityState(
                generated_at=t, city_name=self.s.city_name, mode="replay", replay_time=t, pulse=pulse,
                zones=zones, feeds=feeds, alerts=agent.active() + agent.recent_resolved(6),
                summary=Summary(headline=headline, sections=sections, generated_by="template", generated_at=t,
                                note="Replay of recorded data — rule-based summary."),
                ticker=ticker.latest(), simulation={"active_events": [], "scenario": None, "available_events": []},
                config={"rolling_window_minutes": self.s.rolling_window_minutes, "mode": "replay"},
            )
            summary = {"i": len(session.frames), "t": t, "city_status": pulse.city_status,
                       "statuses": {z.id: z.status for z in zones}}
            session.frames.append(Frame(zlib.compress(state.model_dump_json().encode(), 6), summary,
                                        list(agent.trace)))
            t += ARCHIVE_STEP

    def _archive_feeds(self, t: datetime) -> list[FeedHealth]:
        return [
            FeedHealth(id=spec.id, label=spec.label, source_type=spec.source_type, status=FeedStatus.ARCHIVE,
                       provider="recorded archive", last_success_at=t, age_seconds=0.0,
                       expected_interval_seconds=ARCHIVE_STEP.total_seconds(),
                       message="Recorded data being replayed — not live.", fault_mode="none",
                       records_accepted=0, records_rejected=0)
            for spec in FEEDS
        ]

