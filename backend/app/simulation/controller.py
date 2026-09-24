"""Demo simulation: trigger civic events, run scenario presets, control playback.

Events don't write fake analysis results — they change the synthetic *city* (the ground truth
the feeds report on). Everything downstream (normalization, anomalies, correlation, risk,
alerts, summaries, the map) then has to discover the event on its own, as it would in real life.

Scenario progress is tracked from the *actual* analysis output, not from a timer, so a storyline
beat is ticked only when the system genuinely detected it. Effects run on the model's scenario
clock, so a scenario can be paused or played at 2×/4×.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.data_sources.city_model import EFFECT_KINDS, CityModel, Effect
from app.geo.zones import ZONE_IDS, ZONES_BY_ID
from app.schemas import ZoneState, ZoneStatus
from app.simulation.scenarios import ALIASES, CUSTOM_CONTROLS, PRESETS, PRESETS_BY_ID, Preset

EVENT_LABELS = {
    "heavy_rain": "Heavy rain",
    "traffic_spike": "Traffic spike",
    "incident_cluster": "Power / signal outage cluster",
    "poor_air": "Poor air-quality episode",
    "flooding": "Flash flooding",
    "road_accident": "Road accident",
}
SPEEDS = (1.0, 2.0, 4.0)
CUSTOM_PREFIX = "Custom: "


class SimulationError(ValueError):
    pass


@dataclass
class Stage:
    key: str
    label: str
    check: Callable[[ZoneState], bool]
    reached_at: datetime | None = None
    t_plus_s: int | None = None  # scenario seconds after the start when it was detected
    expected_at_s: int | None = None


@dataclass
class ScenarioStep:
    offset_s: float
    event: str | None
    zone_id: str | None
    narration: str
    intensity: float = 1.0
    duration_s: float = 600.0
    done: bool = False


@dataclass
class Scenario:
    id: str
    name: str
    focus_zone: str
    started_at: datetime  # scenario-clock time
    steps: list[ScenarioStep]
    stages: list[Stage] = field(default_factory=list)
    expected: str = ""
    lag_scale: float = 1.0


def _metric(z: ZoneState, key: str):
    return z.metrics.get(key)


def storm_stages() -> list[Stage]:
    """Stages of a rain-driven disruption (used by historical replay)."""
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


def advance_stages(stages: list[Stage], zone: ZoneState, now: datetime,
                   started_at: datetime | None = None, sim_now: datetime | None = None) -> list[Stage]:
    """Mark newly reached stages. Later stages only count once the story's first beat has
    happened, so random noise before the event can't tick them early."""
    first = next((s for s in stages if s.key != "normal"), None)
    reached = []
    for stage in stages:
        if stage.reached_at is not None:
            continue
        if first is not None and stage is not first and stage.key != "normal" and first.reached_at is None:
            continue
        if stage.check(zone):
            stage.reached_at = now
            if started_at is not None and sim_now is not None:
                stage.t_plus_s = max(0, round((sim_now - started_at).total_seconds()))
            reached.append(stage)
    return reached


class SimulationController:
    def __init__(self, model: CityModel) -> None:
        self.model = model
        self.scenario: Scenario | None = None
        self.custom: dict | None = None
        self.log: list[dict] = []

    @property
    def clock(self):
        return self.model.clock

    # ----------------------------------------------------------------- events
    def trigger(self, event: str, zone_id: str, now: datetime, intensity: float = 1.0,
                duration_s: float = 600.0, lag_scale: float = 1.0, label: str | None = None) -> Effect:
        if event not in EFFECT_KINDS:
            raise SimulationError(f"Unknown event {event!r}. Choose one of: {', '.join(EFFECT_KINDS)}.")
        if zone_id not in ZONE_IDS:
            raise SimulationError(f"Unknown zone {zone_id!r}. Choose one of: {', '.join(ZONE_IDS)}.")
        if not 0.2 <= intensity <= 1.5:
            raise SimulationError("Intensity must be between 0.2 and 1.5.")
        if not 60 <= duration_s <= 3600:
            raise SimulationError("Duration must be between 60 and 3600 seconds.")
        effect = Effect(kind=event, zone_id=zone_id, start=self.clock.now(now), hold_s=duration_s,
                        intensity=intensity, lag_scale=lag_scale,
                        label=label or f"{EVENT_LABELS[event]} in {ZONES_BY_ID[zone_id].name}")
        self.model.effects.append(effect)
        self.log.append({"at": now, "event": event, "zone_id": zone_id, "intensity": intensity})
        return effect

    def clear(self) -> None:
        self.model.effects.clear()
        self.model._carry.clear()
        self.scenario = None
        self.custom = None
        self.clock.reset()

    # -------------------------------------------------------------- scenarios
    @staticmethod
    def preset(preset_id: str) -> Preset:
        preset = PRESETS_BY_ID.get(ALIASES.get(preset_id, preset_id))
        if preset is None:
            raise SimulationError(f"Unknown scenario {preset_id!r}. Choose one of: "
                                  f"{', '.join(p.id for p in PRESETS)}.")
        return preset

    def start_scenario(self, preset_id: str, now: datetime) -> Scenario:
        preset = self.preset(preset_id)
        self.clear()
        self.scenario = Scenario(
            id=preset.id, name=preset.name, focus_zone=preset.zone, started_at=self.clock.now(now),
            steps=[ScenarioStep(st.at_s, st.event, st.zone or preset.zone, st.narration, st.intensity,
                                st.duration_s) for st in preset.steps],
            stages=[Stage(b.key, b.label, b.check, expected_at_s=b.expected_at_s) for b in preset.beats],
            expected=preset.expected, lag_scale=preset.lag_scale,
        )
        return self.scenario

    def start_full_scenario(self, now: datetime) -> Scenario:
        return self.start_scenario("multi_event", now)

    def advance(self, now: datetime) -> list[str]:
        """Start scenario steps that are due (on scenario time). Returns narration for the ticker."""
        if not self.scenario:
            return []
        sim_now = self.clock.now(now)
        lines = []
        for step in self.scenario.steps:
            if step.done or sim_now < self.scenario.started_at + timedelta(seconds=step.offset_s):
                continue
            step.done = True
            if step.event:
                self.trigger(step.event, step.zone_id, now, intensity=step.intensity,
                             duration_s=step.duration_s, lag_scale=self.scenario.lag_scale)
            lines.append(f"Scenario: {step.narration}")
        return lines

    def observe(self, zones: list[ZoneState], now: datetime) -> list[str]:
        """Tick storyline beats the analysis has genuinely reached. Returns newly reached labels."""
        if not self.scenario:
            return []
        focus = next(z for z in zones if z.id == self.scenario.focus_zone)
        reached = advance_stages(self.scenario.stages, focus, now, self.scenario.started_at, self.clock.now(now))
        return [s.label for s in reached]

    # --------------------------------------------------------------- playback
    def pause(self, now: datetime) -> None:
        self.clock.set(now, paused=True)

    def resume(self, now: datetime) -> None:
        self.clock.set(now, paused=False)

    def set_speed(self, speed: float, now: datetime) -> None:
        if speed not in SPEEDS:
            raise SimulationError(f"Speed must be one of {', '.join(f'{s:g}' for s in SPEEDS)}.")
        self.clock.set(now, speed=speed)

    # ------------------------------------------------------------------ custom
    def set_custom(self, zone_id: str, values: dict[str, float], duration_s: float, now: datetime) -> list[str]:
        """Replace the custom scenario with one effect per non-zero slider (0–1.5)."""
        if zone_id not in ZONE_IDS:
            raise SimulationError(f"Unknown zone {zone_id!r}. Choose one of: {', '.join(ZONE_IDS)}.")
        unknown = set(values) - set(CUSTOM_CONTROLS)
        if unknown:
            raise SimulationError(f"Unknown control(s): {', '.join(sorted(unknown))}.")
        self.model.effects[:] = [e for e in self.model.effects if not e.label.startswith(CUSTOM_PREFIX)]
        started = []
        for control, level in values.items():
            if level <= 0:
                continue
            event = CUSTOM_CONTROLS[control]
            self.trigger(event, zone_id, now, intensity=min(1.5, max(0.2, level)), duration_s=duration_s,
                         label=f"{CUSTOM_PREFIX}{EVENT_LABELS[event]} in {ZONES_BY_ID[zone_id].name}")
            started.append(EVENT_LABELS[event])
        self.custom = {"zone_id": zone_id, "values": values, "duration_s": duration_s}
        return started

    # ------------------------------------------------------------------ status
    def status(self, now: datetime) -> dict:
        sim_now = self.clock.now(now)
        effects = [
            {"event": e.kind, "label": e.label or EVENT_LABELS[e.kind], "zone_id": e.zone_id,
             "started_at": e.start, "ends_at": e.end, "level": round(e.envelope(sim_now), 2)}
            for e in self.model.effects if e.end >= sim_now
        ]
        scenario = None
        if self.scenario:
            stages = self.scenario.stages
            scenario = {
                "id": self.scenario.id, "name": self.scenario.name, "focus_zone": self.scenario.focus_zone,
                "expected": self.scenario.expected, "started_at": self.scenario.started_at,
                "elapsed_s": max(0, round((sim_now - self.scenario.started_at).total_seconds())),
                "complete": all(s.reached_at for s in stages),
                "stages": [{"key": s.key, "label": s.label, "reached_at": s.reached_at, "t_plus_s": s.t_plus_s,
                            "expected_at_s": s.expected_at_s} for s in stages],
            }
        return {
            "active_events": effects,
            "scenario": scenario,
            "clock": {"paused": self.clock.paused, "speed": self.clock.speed},
            "custom": self.custom,
            "presets": [p.summary() for p in PRESETS],
            "custom_controls": list(CUSTOM_CONTROLS),
            "available_events": [{"id": k, "label": v} for k, v in EVENT_LABELS.items()],
        }
