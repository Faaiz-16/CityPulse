"""Deterministic plain-language summaries.

Always generated first, instantly, from the structured facts. This is what the user sees
whenever the AI layer is disabled, slow, failing or produces something the validator rejects.
"""

from app.analysis.metrics import usual_reports, verb_for
from app.geo.zones import cell_distance
from app.schemas import SummarySection, ZoneState, ZoneStatus

_STATUS_RANK = {ZoneStatus.RED: 0, ZoneStatus.YELLOW: 1, ZoneStatus.GREEN: 2}
_SEV = {"none": 0, "low": 1, "moderate": 2, "high": 3}


def importance(z: ZoneState) -> tuple:
    """Sort key: worst status first, then the area with the most (and most severe) signals."""
    return (_STATUS_RANK[z.status], -(10 * len(z.risks) + sum(_SEV[a.severity] for a in z.anomalies)), z.number)


def _fmt_num(v: float | None) -> str:
    return "—" if v is None else f"{v:g}"


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def anomaly_phrase(metric: str, current: float | None, deviation: float | None, label: str,
                   baseline: float | None = None) -> str:
    label = _lower_first(label)
    if metric == "rain_mm_h":
        return f"rainfall is heavy at {_fmt_num(current)} mm/h"
    if metric == "aqi" and deviation is None:
        return f"air quality is unhealthy (AQI {_fmt_num(current)})"
    if metric == "water_level_cm":
        return f"street water-level sensors read {_fmt_num(current)} cm"
    if metric in ("waterlogging_reports", "outage_signal_reports", "incident_reports", "accident_reports"):
        return f"{label} are up ({_fmt_num(current)} in the last window, {usual_reports(baseline, deviation)})"
    verb = verb_for(label)
    if deviation is not None:
        return f"{label} {verb} {deviation:.0f}% above normal"
    return f"{label} {verb} unusual"


def zone_explanation(z: ZoneState) -> SummarySection:
    """Three-part explanation for one zone (used in the zone dashboard)."""
    if not z.anomalies and not z.risks:
        happening = f"Conditions in {z.name} are within their normal range for this time of day."
        return SummarySection(
            whats_happening=happening,
            why_it_matters="No unusual civic signals — no action needed.",
            possible_connection=(z.cannot_assess[0] if z.cannot_assess
                                 else "No relationships detected because nothing is unusual."),
        )

    phrases = [anomaly_phrase(a.metric, a.current, a.deviation_pct, a.label, a.baseline) for a in z.anomalies[:4]]
    happening = f"In {z.name}, " + _join(phrases) + "."

    if z.risks:
        why = " ".join(dict.fromkeys(r.resident_advice for r in z.risks))
        why = ("Residents may notice the effects on the ground. " + why) if z.status == ZoneStatus.RED else why
    else:
        why = "Worth keeping an eye on; there is no sign yet that it is affecting other services."

    strong = [r for r in z.relationships if r.strength != "weak"]
    if strong:
        signals = list(dict.fromkeys(label for r in strong for label in _signal_names(r.signals)))
        connection = (f"{_join(signals).capitalize()} are occurring in the same area and time window, "
                      f"so these signals may be related. This is a possible link, not a confirmed cause.")
    elif z.insufficient_evidence:
        connection = z.insufficient_evidence[0]
    elif z.relationships:
        connection = z.relationships[0].statement
    else:
        connection = "Insufficient evidence to identify a relationship between signals."
    if z.cannot_assess:
        connection += " " + z.cannot_assess[0]
    return SummarySection(whats_happening=happening, why_it_matters=why, possible_connection=connection)


def city_summary(zones: list[ZoneState], degraded_feeds: list[str]) -> tuple[str, SummarySection]:
    """Headline + three-part explanation for the whole city."""
    ordered = sorted(zones, key=importance)
    unusual = [z for z in ordered if z.status != ZoneStatus.GREEN]

    if not unusual:
        headline = "All areas look normal right now."
        sections = SummarySection(
            whats_happening="Weather, traffic, civic reports, air quality and street sensors are all "
                            "within their usual range across the city.",
            why_it_matters="No disruptions detected — a good time for normal plans.",
            possible_connection="Nothing unusual, so no relationships between signals to report.",
        )
    else:
        top = unusual[0]
        headline = f"{top.name}: {top.status_label.lower()} — {top.headline.lower()}."
        if len(unusual) > 1:
            others = len(unusual) - 1
            headline += f" {others} more area{'s are' if others > 1 else ' is'} affected."
        # One explanation per hotspot (its most affected area); touching areas are summarised.
        leads: list[ZoneState] = []
        for z in unusual:
            if not any(cell_distance(z.id, lead.id) < 1.5 for lead in leads):
                leads.append(z)
        parts = [zone_explanation(z) for z in leads[:2]]
        happening = " ".join(p.whats_happening for p in parts)
        nearby = len(unusual) - len(leads)
        if nearby:
            happening += f" {nearby} neighbouring area{'s show' if nearby > 1 else ' shows'} similar signals."
        if len(leads) > 2:
            happening += f" {len(leads) - 2} other area{'s' if len(leads) > 3 else ''} elsewhere also show unusual signals."
        happening += " The rest of the city is normal."
        sections = SummarySection(
            whats_happening=happening,
            why_it_matters=" ".join(dict.fromkeys(p.why_it_matters for p in parts)),
            possible_connection=" ".join(dict.fromkeys(p.possible_connection for p in parts[:2])),
        )

    if degraded_feeds:
        sections.possible_connection += (
            f" Note: {_join(degraded_feeds)} data {'is' if len(degraded_feeds) == 1 else 'are'} not fully "
            f"available, so some links cannot be checked.")
    return headline, sections


_SIGNAL_NAMES = {
    "rain_mm_h": "heavy rain",
    "congestion_pct": "heavier traffic",
    "transit_delay_min": "longer bus delays",
    "waterlogging_reports": "waterlogging reports",
    "water_level_cm": "standing water",
    "outage_signal_reports": "power and signal outage reports",
    "accident_reports": "road-accident reports",
    "aqi": "worse air quality",
}


def _signal_names(metrics: list[str]) -> list[str]:
    return [_SIGNAL_NAMES[m] for m in metrics if m in _SIGNAL_NAMES]


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]
