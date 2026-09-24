"""Demo simulation: trigger known civic events and run the scripted full scenario.

Events don't write fake analysis results — they change the synthetic *city* (the ground truth
the feeds report on). Everything downstream (normalization, anomalies, correlation, risk,
alerts, summaries) then has to discover the event on its own, exactly as it would in real life.

Scenario progress is tracked from the *actual* analysis output, not from a timer, so the
stage list shows what the system genuinely detected and when.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.data_sources.city_model import EFFECT_KINDS, CityModel, Effect
from app.geo.zones import ZONE_IDS, ZONES_BY_ID
from app.schemas import ZoneState, ZoneStatus

EVENT_LABELS = {
    "heavy_rain": "Heavy rain",
    "traffic_spike": "Traffic spike",
    "incident_cluster": "Power / signal outage cluster",
    "poor_air": "Poor air-quality episode",
}


class SimulationError(ValueError):
    pass


@dataclass
class Stage:
    key: str
    label: str
    check: Callable[[ZoneState], bool]
    reached_at: datetime | None = None


@dataclass
class ScenarioStep:
    offset_s: float
    event: str | None
    zone_id: str | None
    narration: str
    intensity: float = 1.0
    done: bool = False


@dataclass
class Scenario:
    name: str
    focus_zone: str
    started_at: datetime
    steps: list[ScenarioStep]
    stages: list[Stage] = field(default_factory=list)


def _metric(z: ZoneState, key: str):
    return z.metrics.get(key)


def storm_stages() -> list[Stage]:
    """Stages of a rain-driven disruption, checked against real analysis output (live and replay)."""
    return [
        Stage("normal", "Normal conditions", lambda z: True),
        Stage("rain", "Rain begins", lambda z: (_metric(z, "rain_mm_h").current or 0) >= 2.5),
        Stage("traffic", "Traffic increases",
              lambda z: (_metric(z, "congestion_pct").deviation_pct or 0) >= 10),
        Stage("reports", "Waterlogging reports increase",
              lambda z: (_metric(z, "waterlogging_reports").current or 0) >= 2),
        Stage("anomaly", "Anomalies detected", lambda z: len(z.anomalies) >= 2),
        Stage("link", "Possible relationship found",
              lambda z: any(r.strength != "weak" for r in z.relationships)),
        Stage("disruption", "Potential disruption flagged", lambda z: z.status == ZoneStatus.RED),
    ]


def advance_stages(stages: list[Stage], zone: ZoneState, now: datetime) -> list[Stage]:
    """Mark newly reached stages. Stages after "rain" only count once rain has been detected,
    so random noise in traffic before the storm can't tick "Traffic increases" early."""
    rain_seen = any(s.key == "rain" and s.reached_at for s in stages)
    reached = []
    for stage in stages:
        if stage.reached_at is not None:
            continue
        if stage.key not in ("normal", "rain") and not rain_seen:
            continue
        if stage.check(zone):
            stage.reached_at = now
            reached.append(stage)
            rain_seen = rain_seen or stage.key == "rain"
    return reached


class SimulationController:
    def __init__(self, model: CityModel) -> None:
        self.model = model
        self.scenario: Scenario | None = None
        self.log: list[dict] = []

    # ----------------------------------------------------------------- events
    def trigger(self, event: str, zone_id: str, now: datetime, intensity: float = 1.0,
                duration_s: float = 600.0) -> Effect:
        if event not in EFFECT_KINDS:
            raise SimulationError(f"Unknown event {event!r}. Choose one of: {', '.join(EFFECT_KINDS)}.")
        if zone_id not in ZONE_IDS:
            raise SimulationError(f"Unknown zone {zone_id!r}. Choose one of: {', '.join(ZONE_IDS)}.")
        if not 0.2 <= intensity <= 1.5:
            raise SimulationError("Intensity must be between 0.2 and 1.5.")
        if not 60 <= duration_s <= 3600:
            raise SimulationError("Duration must be between 60 and 3600 seconds.")
        effect = Effect(kind=event, zone_id=zone_id, start=now, hold_s=duration_s, intensity=intensity,
                        label=f"{EVENT_LABELS[event]} in {ZONES_BY_ID[zone_id].name}")
        self.model.effects.append(effect)
        self.log.append({"at": now, "event": event, "zone_id": zone_id, "intensity": intensity})
        return effect

    def clear(self) -> None:
        self.model.effects.clear()
        self.scenario = None

    # --------------------------------------------------------------- scenario
    def start_full_scenario(self, now: datetime) -> Scenario:
        self.clear()
        self.scenario = Scenario(
            name="Monsoon evening in Zone 3", focus_zone="Z3", started_at=now,
            steps=[
                ScenarioStep(0, None, None, "Scenario started: the city is in its normal state."),
                ScenarioStep(6, "heavy_rain", "Z3", "Scenario: heavy rain begins over Zone 3 — East."),
                ScenarioStep(70, "traffic_spike", "Z1",
                             "Scenario: an unrelated traffic build-up starts in Zone 1 — Central.", 0.55),
            ],
            stages=storm_stages(),
        )
        return self.scenario

    def advance(self, now: datetime) -> list[str]:
        """Execute scenario steps that are due. Returns narration lines for the ticker."""
        if not self.scenario:
            return []
        lines = []
        for step in self.scenario.steps:
            if step.done or now < self.scenario.started_at + timedelta(seconds=step.offset_s):
                continue
            step.done = True
            if step.event:
                self.trigger(step.event, step.zone_id, now, intensity=step.intensity)
            lines.append(step.narration)
        return lines

    def observe(self, zones: list[ZoneState], now: datetime) -> list[str]:
        """Mark scenario stages the analysis has genuinely reached. Returns newly reached labels."""
        if not self.scenario:
            return []
        focus = next(z for z in zones if z.id == self.scenario.focus_zone)
        return [s.label for s in advance_stages(self.scenario.stages, focus, now)]

    # ------------------------------------------------------------------ status
    def status(self, now: datetime) -> dict:
        effects = [
            {"event": e.kind, "label": e.label or EVENT_LABELS[e.kind], "zone_id": e.zone_id,
             "started_at": e.start, "ends_at": e.end, "level": round(e.envelope(now), 2)}
            for e in self.model.effects if e.end >= now
        ]
        scenario = None
        if self.scenario:
            scenario = {
                "name": self.scenario.name, "focus_zone": self.scenario.focus_zone,
                "started_at": self.scenario.started_at,
                "elapsed_s": round((now - self.scenario.started_at).total_seconds()),
                "stages": [{"key": s.key, "label": s.label, "reached_at": s.reached_at}
                           for s in self.scenario.stages],
            }
        return {"active_events": effects, "scenario": scenario,
                "available_events": [{"id": k, "label": v} for k, v in EVENT_LABELS.items()]}
