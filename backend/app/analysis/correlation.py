"""Rolling-window correlation: finding *possible* relationships between signals.

We never link two signals just because both happen to be unusual. A candidate relationship
needs all of the following:

  1. a **logical rule** saying the two signals can plausibly be connected
     (rain → traffic is on the list; rain → noise complaints is not),
  2. both signals **anomalous** (meaningfully off their baseline),
  3. the **same zone**,
  4. the **same rolling time window** (default 10 minutes),
  5. timing that fits (the "driver" did not start clearly after the "response").

The strength score also rewards signal size, a supporting signal, and how closely the two
series moved together (Pearson correlation, "co-movement r"). Output wording is always
"may be related" — never "caused".
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.analysis.metrics import METRICS, usual_reports, verb_for
from app.config import Settings
from app.schemas import MetricAssessment, Relationship, Strength

CAVEAT = ("This is a possible link based on location and timing, not a confirmed cause. "
          "Other factors may be involved.")


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    driver: str
    responses: tuple[str, ...]
    supporting: tuple[str, ...] = ()
    driver_phrase: str = ""
    response_phrase: str = ""


RULES: tuple[Rule, ...] = (
    Rule("rain_traffic", "Rain and traffic congestion", "rain_mm_h", ("congestion_pct",),
         ("transit_delay_min",), "heavy rainfall", "higher-than-usual traffic congestion"),
    Rule("rain_flooding", "Rain and waterlogging", "rain_mm_h",
         ("waterlogging_reports", "water_level_cm"), (),
         "heavy rainfall", "rising waterlogging reports and street water levels"),
    Rule("outage_traffic", "Power/signal outages and traffic", "outage_signal_reports",
         ("congestion_pct",), ("transit_delay_min",),
         "a cluster of power-outage and traffic-signal reports", "higher-than-usual traffic congestion"),
    Rule("traffic_air", "Traffic and air quality", "congestion_pct", ("aqi",), (),
         "unusually heavy traffic", "worsening air quality"),
)

# Which feed a metric depends on (used to explain what can't be assessed).
FEED_LABEL = {"weather": "Weather", "traffic": "Traffic", "incidents": "Incident-report",
              "air_quality": "Air-quality", "iot_sensors": "Water-level sensor"}

_SEV_WEIGHT = {"none": 0.0, "low": 0.33, "moderate": 0.66, "high": 1.0}


@dataclass
class ZoneSignals:
    """Everything the correlation step needs to know about one zone."""

    zone_id: str
    zone_name: str
    metrics: dict[str, MetricAssessment]
    onsets: dict[str, datetime]
    binned: dict[str, list[float | None]] = field(default_factory=dict)


def co_movement(a: list[float | None], b: list[float | None]) -> float | None:
    """Pearson correlation of two equally-binned series, ignoring bins missing in either."""
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 6:
        return None
    xs, ys = zip(*pairs)
    try:
        return statistics.correlation(xs, ys)
    except statistics.StatisticsError:  # a flat series has no correlation
        return None


def describe(m: MetricAssessment) -> str:
    """One evidence bullet for a metric, e.g. 'Traffic congestion: 54% (normal 30%, +80%)'."""
    unit = "%" if m.unit == "%" else f" {m.unit}"
    cur = f"{m.current:g}{unit}"
    if METRICS[m.metric].mode == "absolute":  # % change from ~0 is meaningless; show the rule
        return f"{m.label}: {cur} (anomaly rule: {m.threshold})"
    if m.source == "incidents":
        return f"{m.label}: {m.current:g} in the window ({usual_reports(m.baseline, m.deviation_pct)})"
    if m.deviation_pct is None:
        return f"{m.label}: {cur}"
    return f"{m.label}: {cur} (normal {m.baseline:g}{unit}, {m.deviation_pct:+.0f}%)"


def _fmt(t: datetime, tz: ZoneInfo) -> str:
    return t.astimezone(tz).strftime("%H:%M:%S")


def evaluate_zone(z: ZoneSignals, s: Settings) -> tuple[list[Relationship], list[str], list[str]]:
    """Return (relationships, insufficient-evidence notes, cannot-assess notes) for one zone."""
    tz = s.tz
    relationships: list[Relationship] = []
    cannot_assess: list[str] = []
    explained: set[str] = set()

    for rule in RULES:
        driver = z.metrics.get(rule.driver)
        responses = [z.metrics[r] for r in rule.responses if r in z.metrics]
        if driver is None:
            continue

        # Missing data: say what we cannot check instead of guessing.
        if not driver.available and any(r.is_anomaly for r in responses):
            cannot_assess.append(
                f"{FEED_LABEL[driver.source]} data is unavailable, so CityPulse cannot check whether "
                f"{rule.driver_phrase} is linked to the unusual {responses[0].label.lower()}.")
            continue
        if not driver.is_anomaly:
            continue
        anomalous = [r for r in responses if r.is_anomaly]
        missing = [r for r in responses if not r.available]
        if not anomalous:
            if missing:
                cannot_assess.append(
                    f"{FEED_LABEL[missing[0].source]} data is unavailable, so CityPulse cannot check "
                    f"whether {rule.driver_phrase} is affecting {missing[0].label.lower()}.")
            continue

        # --- timing: did the driver start before (or together with) the response? ---
        t_driver = z.onsets.get(rule.driver)
        t_resp = min((z.onsets[r.metric] for r in anomalous if r.metric in z.onsets), default=None)
        timing_fits, lead_lag = True, None
        if t_driver and t_resp:
            gap = (t_resp - t_driver).total_seconds()
            if gap < -60:
                timing_fits = False
                lead_lag = (f"{anomalous[0].label} was already unusual at {_fmt(t_resp, tz)}, before "
                            f"{METRICS[rule.driver].label.lower()} became unusual at {_fmt(t_driver, tz)} "
                            f"— timing does not fit a simple link.")
            elif gap <= 60:
                lead_lag = f"Both became unusual at about the same time (~{_fmt(t_driver, tz)})."
            else:
                lead_lag = (f"{METRICS[rule.driver].label} became unusual first ({_fmt(t_driver, tz)}); "
                            f"{anomalous[0].label.lower()} followed about {max(1, round(gap / 60))} min later.")

        # --- co-movement over the rolling window ---
        r_values = [co_movement(z.binned.get(rule.driver, []), z.binned.get(r.metric, []))
                    for r in anomalous]
        r_values = [r for r in r_values if r is not None]
        r_best = max(r_values) if r_values else None

        supporting = [z.metrics[m] for m in rule.supporting if m in z.metrics and z.metrics[m].is_anomaly]

        score = 0.40
        score += 0.15 * _SEV_WEIGHT[driver.severity]
        score += 0.15 * max(_SEV_WEIGHT[r.severity] for r in anomalous)
        score += 0.15 if timing_fits else -0.10
        score += 0.10 * max(0.0, r_best) if r_best is not None else 0.0
        score += min(0.10, 0.05 * (len(anomalous) - 1 + len(supporting)))
        score = round(min(score, 1.0), 2)
        strength: Strength = "strong" if score >= 0.8 else "moderate" if score >= 0.6 else "weak"

        evidence = [describe(driver)] + [describe(r) for r in anomalous] + [describe(r) for r in supporting]
        evidence.append(f"Same zone: {z.zone_name}")
        evidence.append(f"Overlapping {s.rolling_window_minutes}-minute window")
        if lead_lag:
            evidence.append(lead_lag)
        if r_best is not None and r_best >= 0.5:
            evidence.append(f"The signals rose and fell together over the window (co-movement r = {r_best:.2f})")
        elif r_best is not None:
            evidence.append(f"Little shared movement inside the window (r = {r_best:.2f}) — both are holding "
                            f"at unusual levels, so this adds no extra evidence")

        if strength == "weak":
            statement = (f"{rule.driver_phrase.capitalize()} and {rule.response_phrase} are both present in "
                         f"{z.zone_name}, but the evidence is insufficient to suggest a strong relationship.")
        else:
            statement = (f"{rule.driver_phrase.capitalize()} and {rule.response_phrase} are occurring in the same "
                         f"zone and time window. These signals may be related.")

        relationships.append(Relationship(
            id=f"{z.zone_id}:{rule.id}", zone_id=z.zone_id, rule_id=rule.id, title=rule.title,
            signals=[rule.driver] + [r.metric for r in anomalous] + [r.metric for r in supporting],
            strength=strength, score=score, co_movement_r=round(r_best, 2) if r_best is not None else None,
            lead_lag=lead_lag, window_minutes=s.rolling_window_minutes, evidence=evidence,
            statement=statement, caveat=CAVEAT,
        ))
        if strength != "weak":
            explained.update([rule.driver, *(r.metric for r in anomalous), *(r.metric for r in supporting)])

    insufficient = _unexplained_notes(z, explained)
    return relationships, insufficient, cannot_assess


def _unexplained_notes(z: ZoneSignals, explained: set[str]) -> list[str]:
    notes = []
    for m in z.metrics.values():
        if not m.is_anomaly or m.metric in explained:
            continue
        if m.metric == "rain_mm_h":
            notes.append(f"Heavy rain in {z.zone_name}, but no related traffic or flooding signal is "
                         f"unusual so far — no disruption link detected.")
        elif m.metric == "incident_reports" and "waterlogging_reports" in explained:
            continue  # already covered by the waterlogging relationship
        else:
            notes.append(f"{m.label} {verb_for(m.label)} unusual in {z.zone_name}, but no related signal is unusual at the "
                         f"same time — insufficient evidence to suggest any explanation.")
    return notes


def window_bins(now: datetime, minutes: int, bin_seconds: int = 20) -> list[tuple[datetime, datetime]]:
    n = int(minutes * 60 / bin_seconds)
    start = now - timedelta(minutes=minutes)
    return [(start + timedelta(seconds=i * bin_seconds), start + timedelta(seconds=(i + 1) * bin_seconds))
            for i in range(n)]
