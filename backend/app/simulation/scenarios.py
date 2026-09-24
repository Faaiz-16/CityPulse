"""Scenario presets for the demo: realistic civic incidents that unfold over time.

A preset only changes the *simulated city* (it schedules effects such as rain or a crash).
Everything the user then sees — anomalies, relationships, risk, alerts, the map — is produced by
the normal pipeline. Each preset also carries a **storyline**: the beats we expect CityPulse to
detect, each with a check that is evaluated against the real analysis output. A beat is ticked
only when the analysis actually shows it.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.geo.zones import ZONES_BY_ID
from app.schemas import ZoneState, ZoneStatus

Check = Callable[[ZoneState], bool]


# ---------------------------------------------------------------- beat checks

def _m(z: ZoneState, key: str):
    return z.metrics.get(key)


def value_at_least(key: str, v: float) -> Check:
    return lambda z: (_m(z, key) is not None and (_m(z, key).current or 0) >= v)


def deviation_at_least(key: str, pct: float) -> Check:
    return lambda z: (_m(z, key) is not None and (_m(z, key).deviation_pct or 0) >= pct)


def anomalous(key: str) -> Check:
    return lambda z: (_m(z, key) is not None and _m(z, key).is_anomaly)


def any_link(rule_prefix: str = "") -> Check:
    return lambda z: any(r.strength != "weak" and r.rule_id.startswith(rule_prefix) for r in z.relationships)


def status_is(status: ZoneStatus) -> Check:
    return lambda z: z.status == status


def no_explanation_for(key: str) -> Check:
    """The metric is unusual but CityPulse (honestly) found nothing related."""
    return lambda z: anomalous(key)(z) and not any(key in r.signals for r in z.relationships if r.strength != "weak") \
        and bool(z.insufficient_evidence)


# ------------------------------------------------------------------ data model

@dataclass(frozen=True)
class Step:
    """At ``at_s`` scenario seconds, start ``event`` in ``zone`` (None = the preset's zone)."""

    at_s: float
    event: str
    intensity: float = 1.0
    zone: str | None = None
    duration_s: float = 600.0
    narration: str = ""


@dataclass(frozen=True)
class Beat:
    key: str
    label: str
    expected_at_s: int  # measured time at 1× speed (shown as the storyline's expected timing)
    check: Check


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    tagline: str
    zone: str
    severity: str  # "high" | "moderate" | "low"
    duration_s: int
    feeds: tuple[str, ...]
    expected: str
    steps: tuple[Step, ...]
    beats: tuple[Beat, ...]
    lag_scale: float = 2.0  # stretch downstream reactions so the story is watchable
    icon: str = "rain"
    extra_zones: tuple[str, ...] = field(default=())

    @property
    def ready_s(self) -> int:
        """How far into the scenario everything has usually been detected (instant start)."""
        return max(b.expected_at_s for b in self.beats) + 30

    def summary(self) -> dict:
        return {
            "id": self.id, "name": self.name, "tagline": self.tagline, "zone_id": self.zone,
            "place": ZONES_BY_ID[self.zone].short_name,
            "severity": self.severity, "duration_s": self.duration_s, "feeds": list(self.feeds),
            "expected": self.expected, "icon": self.icon, "ready_s": self.ready_s,
            "storyline": [{"key": b.key, "label": b.label, "expected_at_s": b.expected_at_s} for b in self.beats],
        }


RED = ZoneStatus.RED

PRESETS: tuple[Preset, ...] = (
    Preset(
        id="heavy_rain", name="Heavy rainfall", icon="rain",
        tagline="Monsoon downpour over the Walled City",
        zone="F4", severity="high", duration_s=600,
        feeds=("weather", "traffic", "transit", "civic reports", "water sensors"),
        expected="Possible traffic disruption in and around the Walled City",
        steps=(Step(0, "heavy_rain", narration="Rain begins over the Walled City (F4)."),),
        beats=(
            Beat("rain", "Rain begins", 25, value_at_least("rain_mm_h", 2.5)),
            Beat("rain_heavy", "Rain becomes heavy", 35, anomalous("rain_mm_h")),
            Beat("traffic", "Traffic starts building", 70, deviation_at_least("congestion_pct", 10)),
            Beat("water", "Street water levels rise", 85, value_at_least("water_level_cm", 8)),
            Beat("reports", "Waterlogging reports come in", 105, value_at_least("waterlogging_reports", 2)),
            Beat("buses", "Bus delays grow", 95, deviation_at_least("transit_delay_min", 30)),
            Beat("link", "Possible relationship found", 90, any_link("rain")),
            Beat("disruption", "Possible disruption detected", 95, status_is(RED)),
        ),
    ),
    Preset(
        id="flash_flood", name="Flash flood", icon="water",
        tagline="Cloudburst — the Dravyavati overflows in Mansarovar",
        zone="C7", severity="high", duration_s=600,
        feeds=("weather", "water sensors", "civic reports", "traffic"),
        expected="Possible waterlogging disruption in Mansarovar",
        steps=(Step(0, "heavy_rain", 1.3, narration="A cloudburst starts over Mansarovar (C7)."),
               Step(20, "flooding", 1.0, narration="Drains in Mansarovar begin to overflow.")),
        beats=(
            Beat("rain", "Intense rain begins", 35, anomalous("rain_mm_h")),
            Beat("water", "Water rises on the streets", 70, anomalous("water_level_cm")),
            Beat("reports", "Waterlogging reports surge", 95, anomalous("waterlogging_reports")),
            Beat("traffic", "Traffic slows", 70, deviation_at_least("congestion_pct", 15)),
            Beat("link", "Possible relationship found", 70, any_link("rain")),
            Beat("disruption", "Possible disruption detected", 75, status_is(RED)),
        ),
    ),
    Preset(
        id="traffic", name="Major congestion", icon="traffic",
        tagline="Gridlock around C-Scheme and MI Road — no weather involved",
        zone="E4", severity="moderate", duration_s=600,
        feeds=("traffic", "transit", "air quality"),
        expected="Traffic and air quality worsening in C-Scheme — no weather link",
        steps=(Step(0, "traffic_spike", narration="Traffic builds rapidly around C-Scheme (E4)."),),
        beats=(
            Beat("traffic", "Traffic starts building", 30, deviation_at_least("congestion_pct", 10)),
            Beat("traffic_high", "Congestion becomes unusual", 50, anomalous("congestion_pct")),
            Beat("buses", "Bus delays grow", 70, deviation_at_least("transit_delay_min", 20)),
            Beat("air", "Air quality worsens", 125, deviation_at_least("aqi", 15)),
            Beat("link", "Possible traffic–air link found", 145, any_link("traffic_air")),
        ),
    ),
    Preset(
        id="accident", name="Road accident", icon="accident",
        tagline="A serious crash on Ajmer Road near Heerapura",
        zone="B6", severity="high", duration_s=480,
        feeds=("civic reports", "traffic", "transit"),
        expected="Possible traffic disruption after an accident near Heerapura",
        steps=(Step(0, "road_accident", narration="Accident reports start coming in from Ajmer Road (B6)."),),
        beats=(
            Beat("reports", "Accident reports come in", 65, value_at_least("accident_reports", 2)),
            Beat("reports_high", "Report cluster confirmed", 85, anomalous("accident_reports")),
            Beat("traffic", "A queue builds behind the crash", 70, deviation_at_least("congestion_pct", 10)),
            Beat("link", "Possible relationship found", 95, any_link("accident")),
            Beat("disruption", "Possible disruption detected", 145, status_is(RED)),
        ),
    ),
    Preset(
        id="power_outage", name="Power outage", icon="outage",
        tagline="Substation failure knocks out power and signals in Malviya Nagar",
        zone="F7", severity="high", duration_s=600,
        feeds=("civic reports", "traffic", "transit"),
        expected="Possible disruption from outages in Malviya Nagar",
        steps=(Step(0, "incident_cluster", narration="Power-outage reports start in Malviya Nagar (F7)."),),
        beats=(
            Beat("reports", "Outage reports come in", 80, value_at_least("outage_signal_reports", 2)),
            Beat("reports_high", "Outage cluster confirmed", 80, anomalous("outage_signal_reports")),
            Beat("traffic", "Traffic slows at dark junctions", 100, deviation_at_least("congestion_pct", 10)),
            Beat("link", "Possible relationship found", 130, any_link("outage")),
            Beat("disruption", "Possible disruption detected", 130, status_is(RED)),
        ),
    ),
    Preset(
        id="poor_air", name="Poor air quality", icon="air",
        tagline="Smog settles over the VKI industrial area — cause unknown",
        zone="D1", severity="moderate", duration_s=600,
        feeds=("air quality",),
        expected="Air-quality alert in VKI Industrial Area — CityPulse does not guess a cause",
        steps=(Step(0, "poor_air", narration="Air quality starts deteriorating around VKI Industrial Area (D1)."),),
        beats=(
            Beat("air", "Air quality worsens", 20, deviation_at_least("aqi", 15)),
            Beat("air_high", "Air quality becomes unusual", 20, anomalous("aqi")),
            Beat("honest", "No related signal — no cause claimed", 25, no_explanation_for("aqi")),
        ),
    ),
    Preset(
        id="storm", name="Severe storm", icon="storm",
        tagline="Torrential rain, flooding and power cuts in Jagatpura",
        zone="G8", severity="high", duration_s=720,
        feeds=("weather", "water sensors", "civic reports", "traffic", "transit"),
        expected="Possible disruption in Jagatpura from several linked signals",
        steps=(Step(0, "heavy_rain", 1.5, narration="A severe storm reaches Jagatpura (G8)."),
               Step(30, "flooding", 0.8, narration="Low-lying streets in Jagatpura start flooding."),
               Step(45, "incident_cluster", 0.7, narration="Storm damage causes power cuts in Jagatpura.")),
        beats=(
            Beat("rain", "Torrential rain", 35, anomalous("rain_mm_h")),
            Beat("water", "Streets flood", 85, anomalous("water_level_cm")),
            Beat("outage", "Power cuts reported", 140, value_at_least("outage_signal_reports", 2)),
            Beat("traffic", "Traffic grinds down", 80, anomalous("congestion_pct")),
            Beat("link", "Possible relationships found", 80, any_link()),
            Beat("disruption", "Possible disruption detected", 85, status_is(RED)),
        ),
    ),
    Preset(
        id="multi_event", name="Multi-event evening", icon="multi",
        tagline="Rain over the Walled City, plus an unrelated jam in Vaishali Nagar",
        zone="F4", severity="high", duration_s=600, lag_scale=1.0,
        feeds=("all feeds",),
        expected="Disruption in the Walled City; Vaishali Nagar traffic flagged but NOT blamed on the rain",
        extra_zones=("C4",),
        steps=(Step(6, "heavy_rain", narration="Heavy rain begins over the Walled City (F4)."),
               Step(30, "traffic_spike", 0.55, zone="C4",
                    narration="An unrelated traffic build-up starts in Vaishali Nagar (C4).")),
        beats=(
            Beat("rain", "Rain begins", 25, value_at_least("rain_mm_h", 2.5)),
            Beat("traffic", "Traffic increases", 55, deviation_at_least("congestion_pct", 10)),
            Beat("reports", "Waterlogging reports increase", 90, value_at_least("waterlogging_reports", 2)),
            Beat("anomaly", "Anomalies detected", 70, lambda z: len(z.anomalies) >= 2),
            Beat("link", "Possible relationship found", 70, any_link()),
            Beat("disruption", "Possible disruption flagged", 70, status_is(RED)),
        ),
    ),
)

PRESETS_BY_ID = {p.id: p for p in PRESETS}
ALIASES = {"full": "multi_event"}  # the original "Run full scenario"

# Custom-scenario sliders → the effect each one drives.
CUSTOM_CONTROLS: dict[str, str] = {
    "rain": "heavy_rain",
    "flooding": "flooding",
    "traffic": "traffic_spike",
    "accident": "road_accident",
    "outage": "incident_cluster",
    "air": "poor_air",
}
