"""Deterministic synthetic city.

This is the "ground truth" behind every simulated feed. For any zone and time it returns
what the city *actually* looks like:

    value = daily pattern (rush hours, air-quality peaks)  × zone character
            + active simulation effects (rain, traffic spike, incident cluster)
            + small deterministic noise

The feeds then report this ground truth in their own messy vendor formats, which is what
the normalization layer has to untangle. Because noise is seeded from (seed, zone, metric,
time), the same inputs always produce the same outputs, so demos and tests are repeatable.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar
from zoneinfo import ZoneInfo

from app.geo.zones import ZONES_BY_ID, zone_for_point


# How each zone differs from the city average.
ZONE_CHARACTER: dict[str, dict[str, float]] = {
    "Z1": {"traffic": 1.25, "air": 1.10, "incidents": 1.2},
    "Z2": {"traffic": 0.95, "air": 1.00, "incidents": 1.0},
    "Z3": {"traffic": 1.05, "air": 1.05, "incidents": 1.0},
    "Z4": {"traffic": 1.00, "air": 0.95, "incidents": 0.9},
    "Z5": {"traffic": 0.90, "air": 1.15, "incidents": 0.8},
}

FREE_FLOW_KMH = 45.0

# Normal (background) incident rate per zone, reports per minute, by category.
BASE_INCIDENT_RATES: dict[str, float] = {
    "pothole": 0.05,
    "streetlight": 0.04,
    "garbage": 0.06,
    "noise": 0.04,
    "tree_fall": 0.005,
    "power_outage": 0.006,
    "traffic_signal": 0.006,
    "road_accident": 0.01,
    "waterlogging": 0.006,
}


@dataclass(frozen=True)
class Impact:
    """How an effect changes one metric: add ``amount`` or multiply by (1 + amount)."""

    metric: str
    op: str  # "add" | "mul"
    amount: float
    lag_s: float = 0.0


# What each simulated civic event physically does to the city. Downstream signals
# react after a lag, which is what the correlation engine later has to discover.
EFFECT_IMPACTS: dict[str, tuple[Impact, ...]] = {
    "heavy_rain": (
        Impact("rain_mm_h", "add", 26.0),
        Impact("congestion_pct", "mul", 0.80, lag_s=20),
        Impact("transit_delay_min", "mul", 1.6, lag_s=30),
        Impact("water_level_cm", "add", 38.0, lag_s=25),
        Impact("pm25_ugm3", "mul", -0.30, lag_s=30),  # rain washes particles out
        Impact("temperature_c", "add", -4.0),
        Impact("wind_kmh", "add", 12.0),
    ),
    "traffic_spike": (
        Impact("congestion_pct", "mul", 0.90),
        Impact("transit_delay_min", "mul", 1.3, lag_s=20),
        Impact("pm25_ugm3", "mul", 0.60, lag_s=40),
    ),
    "incident_cluster": (
        Impact("congestion_pct", "mul", 0.5, lag_s=30),
        Impact("transit_delay_min", "mul", 0.8, lag_s=60),
    ),
    "poor_air": (
        Impact("pm25_ugm3", "mul", 2.2),
    ),
    # Localised flooding: drains overwhelmed, streets under water, traffic crawls.
    "flooding": (
        Impact("water_level_cm", "add", 45.0, lag_s=10),
        Impact("congestion_pct", "mul", 0.55, lag_s=30),
        Impact("transit_delay_min", "mul", 1.0, lag_s=40),
    ),
    # A serious crash: reports first, then a queue builds behind it.
    "road_accident": (
        Impact("congestion_pct", "mul", 0.75, lag_s=20),
        Impact("transit_delay_min", "mul", 0.9, lag_s=40),
        Impact("pm25_ugm3", "mul", 0.15, lag_s=60),
    ),
}

# Extra incident reports per minute (at full effect intensity) and their lag.
EFFECT_INCIDENTS: dict[str, dict[str, tuple[float, float]]] = {
    "heavy_rain": {"waterlogging": (3.5, 25), "tree_fall": (0.25, 40), "road_accident": (0.15, 50)},
    "traffic_spike": {"road_accident": (0.25, 30)},
    "incident_cluster": {"power_outage": (2.4, 0), "traffic_signal": (1.8, 10)},
    "poor_air": {},
    "flooding": {"waterlogging": (5.0, 15), "road_accident": (0.1, 40)},
    "road_accident": {"road_accident": (3.0, 0), "traffic_signal": (0.2, 30)},
}

EFFECT_KINDS = tuple(EFFECT_IMPACTS)


class SimClock:
    """Scenario time, which can be paused or sped up independently of the wall clock.

    Effects (rain, spikes…) are scheduled and evaluated in *scenario* time, so pausing freezes
    them where they are and 2×/4× makes them unfold faster. Everything else — time of day,
    noise, feed polling, the analysis windows — keeps running on the real clock. With no
    pause/speed change the scenario time simply equals real time.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._anchor_real: datetime | None = None
        self._anchor_sim: datetime | None = None
        self.speed = 1.0
        self.paused = False

    def now(self, t: datetime) -> datetime:
        if self._anchor_real is None:
            return t
        if self.paused:
            return self._anchor_sim
        return self._anchor_sim + (t - self._anchor_real) * self.speed

    @property
    def rate(self) -> float:
        """Scenario seconds per real second (0 while paused)."""
        return 0.0 if self.paused else self.speed

    def set(self, t: datetime, *, speed: float | None = None, paused: bool | None = None) -> None:
        current = self.now(t)
        self._anchor_real, self._anchor_sim = t, current
        if speed is not None:
            self.speed = speed
        if paused is not None:
            self.paused = paused


@dataclass
class Effect:
    kind: str
    zone_id: str
    start: datetime
    ramp_s: float = 40.0
    hold_s: float = 600.0
    fade_s: float = 60.0
    intensity: float = 1.0
    label: str = ""
    # Downstream lags are tuned in seconds for a snappy live demo; a recorded real-world
    # event unfolds over minutes, so history effects stretch the lags by this factor.
    lag_scale: float = 1.0

    @property
    def end(self) -> datetime:
        return self.start + timedelta(seconds=self.ramp_s + self.hold_s + self.fade_s)

    def envelope(self, t: datetime, lag_s: float = 0.0) -> float:
        """0 → 1 ramp, hold at 1, fade back to 0. Lag shifts the whole curve later."""
        s = (t - self.start).total_seconds() - lag_s * self.lag_scale
        if s <= 0:
            return 0.0
        if s < self.ramp_s:
            level = s / self.ramp_s
        elif s < self.ramp_s + self.hold_s:
            level = 1.0
        elif s < self.ramp_s + self.hold_s + self.fade_s:
            level = 1.0 - (s - self.ramp_s - self.hold_s) / self.fade_s
        else:
            level = 0.0
        return level * self.intensity


def _peak(hour: float, centre: float, width: float) -> float:
    return math.exp(-((hour - centre) ** 2) / (2 * width**2))


@dataclass
class CityModel:
    seed: int
    tz: ZoneInfo
    effects: list[Effect] = field(default_factory=list)
    clock: SimClock = field(default_factory=SimClock)
    _carry: dict[tuple[str, str], float] = field(default_factory=dict, repr=False)  # event reports owed

    # ------------------------------------------------------------------ utils
    def rng(self, *keys: object) -> random.Random:
        return random.Random(f"{self.seed}|" + "|".join(str(k) for k in keys))

    def active_effects(self, zone_id: str, t: datetime) -> list[Effect]:
        return [e for e in self.effects if e.zone_id == zone_id and e.start <= t <= e.end]

    # ----------------------------------------------------------- base pattern
    def base_value(self, zone_id: str, metric: str, t: datetime) -> float:
        char = ZONE_CHARACTER[zone_id]
        local = t.astimezone(self.tz)
        h = local.hour + local.minute / 60 + local.second / 3600
        if metric == "congestion_pct":
            daily = 22 + 26 * _peak(h, 9.0, 1.4) + 30 * _peak(h, 18.5, 1.7) + 10 * _peak(h, 13.5, 3.0)
            return min(daily * char["traffic"], 85.0)
        if metric == "transit_delay_min":
            return 1.5 + 0.07 * self.base_value(zone_id, "congestion_pct", t)
        if metric == "rain_mm_h":
            return 0.0
        if metric == "temperature_c":
            return 29.0 + 4.0 * math.sin((h - 9.0) / 24 * 2 * math.pi)
        if metric == "wind_kmh":
            return 9.0 + 4.0 * _peak(h, 15.0, 3.0)
        if metric == "pm25_ugm3":
            daily = 22 + 10 * _peak(h, 8.5, 1.8) + 14 * _peak(h, 21.5, 2.2)
            return daily * char["air"]
        if metric == "water_level_cm":
            return 1.5
        raise KeyError(metric)

    NOISE_SD: ClassVar[dict[str, float]] = {
        "congestion_pct": 0.035,  # relative
        "transit_delay_min": 0.05,
        "pm25_ugm3": 0.05,
        "temperature_c": 0.2,  # absolute
        "wind_kmh": 0.8,
        "rain_mm_h": 0.0,
        "water_level_cm": 0.4,
    }

    # ------------------------------------------------------------ ground truth
    def value(self, zone_id: str, metric: str, t: datetime, key: object = "") -> float:
        """Ground-truth value of a metric in a zone at time ``t``."""
        v = self.base_value(zone_id, metric, t)
        st = self.clock.now(t)  # effects run on scenario time
        for eff in self.active_effects(zone_id, st):
            for imp in EFFECT_IMPACTS[eff.kind]:
                if imp.metric != metric:
                    continue
                level = eff.envelope(st, imp.lag_s)
                v = v + imp.amount * level if imp.op == "add" else v * (1 + imp.amount * level)

        sd = self.NOISE_SD.get(metric, 0.0)
        if sd:
            r = self.rng(zone_id, metric, int(t.timestamp()), key).gauss(0, 1)
            relative = metric in ("congestion_pct", "transit_delay_min", "pm25_ugm3")
            v = v * (1 + sd * r) if relative else v + sd * r
        if metric == "rain_mm_h" and v > 0:
            v *= 1 + 0.08 * self.rng(zone_id, metric, int(t.timestamp()), key).gauss(0, 1)
        if metric == "congestion_pct":
            v = min(v, 97.0)
        return round(max(v, 0.0), 2)

    def speed_kmh(self, zone_id: str, t: datetime, key: object = "") -> float:
        congestion = self.value(zone_id, "congestion_pct", t, key)
        return round(FREE_FLOW_KMH * (1 - congestion / 100), 2)

    # --------------------------------------------------------------- incidents
    def incident_rate(self, zone_id: str, category: str, t: datetime) -> tuple[float, float]:
        """(normal background rate, extra rate caused by active effects), reports per minute."""
        base = BASE_INCIDENT_RATES.get(category, 0.0) * ZONE_CHARACTER[zone_id]["incidents"]
        extra = 0.0
        st = self.clock.now(t)
        for eff in self.active_effects(zone_id, st):
            spec = EFFECT_INCIDENTS.get(eff.kind, {}).get(category)
            if spec:
                per_min, lag = spec
                extra += per_min * eff.envelope(st, lag)
        return base, extra

    def incidents_between(self, zone_id: str, t0: datetime, t1: datetime) -> list[dict]:
        """Deterministic Poisson draw of reports in [t0, t1) for one zone."""
        dt_min = (t1 - t0).total_seconds() / 60
        if dt_min <= 0:
            return []
        mid = t0 + (t1 - t0) / 2
        out: list[dict] = []
        for category in BASE_INCIDENT_RATES:
            base, extra = self.incident_rate(zone_id, category, mid)
            rng = self.rng(zone_id, "inc", category, int(t0.timestamp()), int(t1.timestamp()))
            # Background reports arrive randomly (Poisson). Reports caused by an event are
            # emitted from an accumulator so they track the event's rate reliably — a scripted
            # demo shouldn't stall on an unlucky streak. They follow scenario time: none while
            # paused, faster at 2×/4×.
            key = (zone_id, category)
            self._carry[key] = self._carry.get(key, 0.0) + extra * self.clock.rate * dt_min
            from_event = int(self._carry[key])
            self._carry[key] -= from_event
            for i in range(_poisson(base * dt_min, rng) + from_event):
                ts = t0 + (t1 - t0) * rng.random()
                lat, lon = self.random_point(zone_id, rng)
                out.append({"category": category, "ts": ts, "lat": lat, "lon": lon,
                            "key": f"{zone_id}-{category}-{int(t0.timestamp())}-{i}"})
        return sorted(out, key=lambda r: r["ts"])

    def random_point(self, zone_id: str, rng: random.Random) -> tuple[float, float]:
        zone = ZONES_BY_ID[zone_id]
        clat, clon = zone.sensors[4][2], zone.sensors[4][3]  # cluster near the zone's low point
        for _ in range(12):
            lat = clat + rng.gauss(0, 0.012)
            lon = clon + rng.gauss(0, 0.015)
            if zone_for_point(lat, lon) == zone_id:
                return round(lat, 5), round(lon, 5)
        return round(clat, 5), round(clon, 5)


def _poisson(lam: float, rng: random.Random) -> int:
    """Knuth's algorithm — fine for the small rates used here."""
    if lam <= 0:
        return 0
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1
