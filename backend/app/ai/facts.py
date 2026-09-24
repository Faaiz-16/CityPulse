"""Build the compact, structured fact sheet that both the templates and the LLM read.

The LLM never sees raw feeds — only these facts, which the analysis engine has already
computed and checked. That is the main defence against invented events or numbers.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.schemas import HEALTHY_FEED_STATUSES, FeedHealth, ZoneState, ZoneStatus

_SEV_RANK = {"none": 0, "low": 1, "moderate": 2, "high": 3}
_STATUS_RANK = {ZoneStatus.RED: 0, ZoneStatus.YELLOW: 1, ZoneStatus.GREEN: 2}


def build_facts(zones: list[ZoneState], feeds: list[FeedHealth], now: datetime, tz: ZoneInfo,
                window_minutes: int) -> dict:
    ordered = sorted(zones, key=lambda z: (_STATUS_RANK[z.status], z.number))
    return {
        "as_of_local_time": now.astimezone(tz).strftime("%H:%M"),
        "rolling_window_minutes": window_minutes,
        "city_status": ordered[0].status.value if ordered else "GREEN",
        "zones": [
            {
                "zone_id": z.id,
                "zone_name": z.name,
                "status": z.status.value,
                "status_label": z.status_label,
                "headline": z.headline,
                "anomalies": [
                    {"signal": a.label, "current": a.current, "unit": a.unit, "normal": a.baseline,
                     "deviation_pct": a.deviation_pct, "severity": a.severity}
                    for a in sorted(z.anomalies, key=lambda a: -_SEV_RANK[a.severity])
                ],
                "possible_relationships": [
                    {"title": r.title, "strength": r.strength, "statement": r.statement}
                    for r in z.relationships
                ],
                "risk_insights": [{"headline": r.headline, "advice": r.resident_advice} for r in z.risks],
                "insufficient_evidence": z.insufficient_evidence,
                "cannot_assess": z.cannot_assess,
            }
            for z in ordered
        ],
        "degraded_feeds": [
            {"feed": f.label, "status": f.status.value, "note": f.message}
            for f in feeds if f.status not in HEALTHY_FEED_STATUSES
        ],
    }


def fingerprint(facts: dict) -> str:
    """Changes only when the *situation* changes (not on every small number wobble)."""
    parts = [facts["city_status"]]
    for z in facts["zones"]:
        parts.append(z["zone_id"] + z["status"])
        parts += [a["signal"] + a["severity"] for a in z["anomalies"]]
        parts += [r["title"] + r["strength"] for r in z["possible_relationships"]]
        parts += [r["headline"] for r in z["risk_insights"]]
    parts += [f["feed"] + f["status"] for f in facts["degraded_feeds"]]
    return "|".join(parts)
