"""Predictive impact: what may happen next, here and in neighbouring blocks.

Once the analysis knows what is unusual *now*, well-known knock-on effects tell us what is worth
watching *next*: heavy rain is often followed by waterlogging, power cuts and slower traffic, a
crash by queues on the surrounding roads, an outage by dark traffic signals, and so on. Each rule
turns an observed driver (with its strength) into a possible impact in the same block and — more
weakly — in the eight neighbouring blocks.

These are **possibilities**, not certainties, and not claims about causes: every prediction says
how likely it is (low / medium / high), roughly when, and which observed conditions it is based
on. An impact that is already being measured in a block is not predicted there (it is happening,
and the rest of the analysis reports it).
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.config import Settings
from app.geo.zones import ZONES_BY_ID, cell_distance
from app.schemas import MetricAssessment, Prediction, ZoneState

# Impact kinds: wording, rough time horizon, and the metrics that mean it is already happening.
IMPACTS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "flooding": ("Flash flooding possible", "next 30–60 min", ("water_level_cm", "waterlogging_reports")),
    "power_cut": ("Power cuts possible", "next 1–2 hours", ("outage_signal_reports",)),
    "traffic": ("Traffic may slow down", "next 15–30 min", ("congestion_pct",)),
    "bus_delays": ("Buses may run late", "next 15–30 min", ("transit_delay_min",)),
    "air_quality": ("Air quality may worsen", "next 1–2 hours", ("aqi",)),
}
MIN_SCORE = 0.3  # weaker than this is not worth showing
MAX_PER_BLOCK = 4


@dataclass(frozen=True)
class Rule:
    driver: str  # short name of the observed condition, used in the reason
    strength: Callable[[ZoneState, Settings], float]  # 0 = not present … 1 = very strong
    here: dict[str, float]  # impact kind → weight in the same block
    nearby: dict[str, float]  # impact kind → weight in the 8 neighbouring blocks
    because: Callable[[ZoneState], str]  # the observed condition, in plain words


def _m(z: ZoneState, key: str) -> MetricAssessment | None:
    m = z.metrics.get(key)
    return m if m is not None and m.available and m.current is not None else None


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _rain(z: ZoneState, s: Settings) -> float:
    m = _m(z, "rain_mm_h")
    if not m or m.current < s.moderate_rain_mm_h:
        return 0.0
    return _clamp(0.25 + 0.75 * (m.current - s.moderate_rain_mm_h) / 25)


def _water(z: ZoneState, s: Settings) -> float:
    m = _m(z, "water_level_cm")
    rising = m is not None and m.trend == "rising"
    if not m or (m.current < s.water_level_threshold_cm / 2 and not m.is_anomaly):
        return 0.0
    return _clamp(0.35 + m.current / (3 * s.water_level_threshold_cm) + (0.15 if rising else 0))


def _flag(key: str, base: float = 0.6) -> Callable[[ZoneState, Settings], float]:
    """Strength of an anomalous report/traffic signal, from its severity."""
    def strength(z: ZoneState, _s: Settings) -> float:
        m = z.metrics.get(key)
        if m is None or not m.is_anomaly:
            return 0.0
        return {"low": base, "moderate": base + 0.2, "high": base + 0.4}.get(m.severity, base)
    return strength


def _say(key: str, text: Callable[[MetricAssessment], str]) -> Callable[[ZoneState], str]:
    def because(z: ZoneState) -> str:
        m = z.metrics.get(key)
        return text(m) if m is not None else key
    return because


RULES: tuple[Rule, ...] = (
    Rule("heavy rain", _rain,
         here={"flooding": 0.85, "power_cut": 0.6, "traffic": 0.8, "bus_delays": 0.65},
         nearby={"flooding": 0.55, "power_cut": 0.35, "traffic": 0.45},
         because=_say("rain_mm_h", lambda m: f"rain at {m.current:g} mm/h")),
    Rule("rising water", _water,
         here={"flooding": 0.95, "traffic": 0.75, "power_cut": 0.45, "bus_delays": 0.55},
         nearby={"flooding": 0.6, "traffic": 0.4},
         because=_say("water_level_cm", lambda m: f"street water at {m.current:g} cm")),
    Rule("waterlogging reports", _flag("waterlogging_reports"),
         here={"traffic": 0.75, "bus_delays": 0.6, "power_cut": 0.4},
         nearby={"flooding": 0.5, "traffic": 0.4},
         because=_say("waterlogging_reports", lambda m: f"{m.current:g} waterlogging reports")),
    Rule("heavy traffic", _flag("congestion_pct", 0.55),
         here={"bus_delays": 0.8, "air_quality": 0.55},
         nearby={"traffic": 0.5},
         because=_say("congestion_pct", lambda m: f"traffic {m.deviation_pct:+.0f}% vs normal")),
    Rule("road accident", _flag("accident_reports", 0.65),
         here={"traffic": 0.9, "bus_delays": 0.7},
         nearby={"traffic": 0.55},
         because=_say("accident_reports", lambda m: f"{m.current:g} accident reports")),
    Rule("power / signal outages", _flag("outage_signal_reports", 0.65),
         here={"traffic": 0.85, "bus_delays": 0.55},
         nearby={"power_cut": 0.5, "traffic": 0.4},
         because=_say("outage_signal_reports", lambda m: f"{m.current:g} outage reports")),
    Rule("poor air", _flag("aqi", 0.6),
         here={},
         nearby={"air_quality": 0.55},
         because=_say("aqi", lambda m: f"air quality index {m.current:g}")),
)


def _likelihood(score: float) -> str:
    return "high" if score >= 0.65 else "medium" if score >= 0.45 else "low"


def _happening(z: ZoneState, kind: str) -> bool:
    return any((m := z.metrics.get(k)) is not None and m.is_anomaly for k in IMPACTS[kind][2])


def _unlikely(z: ZoneState, kind: str, s: Settings) -> bool:
    """Conditions that make an impact implausible: rain washes particles out of the air."""
    return kind == "air_quality" and _rain(z, s) > 0


def predict(zones: list[ZoneState], s: Settings) -> dict[str, list[Prediction]]:
    """Possible next impacts for every block, from the conditions observed in it and around it."""
    by_id = {z.id: z for z in zones}
    best: dict[tuple[str, str], Prediction] = {}
    for source in zones:
        for rule in RULES:
            strength = rule.strength(source, s)
            if strength <= 0:
                continue
            here_name = ZONES_BY_ID[source.id].short_name
            targets = [(source, rule.here, False)]
            if rule.nearby:
                targets += [(by_id[n], rule.nearby, True) for n in _neighbours(source.id) if n in by_id]
            for target, weights, nearby in targets:
                for kind, weight in weights.items():
                    score = round(strength * weight, 2)
                    if score < MIN_SCORE or _happening(target, kind) or _unlikely(target, kind, s):
                        continue
                    key = (target.id, kind)
                    if key in best and best[key].score >= score:
                        continue
                    label, horizon, _ = IMPACTS[kind]
                    where = f"in a neighbouring block ({here_name})" if nearby else "here"
                    best[key] = Prediction(
                        kind=kind, label=label, likelihood=_likelihood(score), score=score, horizon=horizon,
                        reason=f"Based on {rule.because(source)} {where}.", source_zone=source.id, nearby=nearby,
                    )
    out: dict[str, list[Prediction]] = {}
    for (zone_id, _), pred in best.items():
        out.setdefault(zone_id, []).append(pred)
    return {z: sorted(p, key=lambda x: -x.score)[:MAX_PER_BLOCK] for z, p in out.items()}


_NEIGHBOURS: dict[str, list[str]] = {}


def _neighbours(zone_id: str) -> list[str]:
    if not _NEIGHBOURS:
        for a in ZONES_BY_ID:
            _NEIGHBOURS[a] = [b for b in ZONES_BY_ID if b != a and cell_distance(a, b) < 1.5]
    return _NEIGHBOURS[zone_id]
