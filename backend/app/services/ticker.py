"""The live civic signal stream: turns tick-to-tick *changes* into short narrative events.

Shared by the live pipeline and historical replay so both tell the story the same way.
"""

from collections import deque
from datetime import datetime

from app.analysis.metrics import INCIDENT_CATEGORIES, METRICS
from app.geo.zones import ZONES_BY_ID
from app.schemas import (
    HEALTHY_FEED_STATUSES,
    Alert,
    CivicIncident,
    FeedHealth,
    FeedStatus,
    TickerEvent,
    ZoneState,
)

_ALERT_PREFIX = {"opened": "Agent alert", "escalated": "Agent escalated", "resolved": "Agent resolved"}


class Ticker:
    def __init__(self, maxlen: int = 80) -> None:
        self.events: deque[TickerEvent] = deque(maxlen=maxlen)
        self._prev_zones: dict[str, ZoneState] = {}
        self._prev_feed_status: dict[str, FeedStatus] = {}

    def add(self, at: datetime, zone_id: str | None, kind: str, text: str, severity: str = "none") -> None:
        self.events.append(TickerEvent(at=at, zone_id=zone_id, kind=kind, text=text, severity=severity))

    def clear(self) -> None:
        self.events.clear()
        self._prev_zones.clear()
        self._prev_feed_status.clear()

    def latest(self, n: int = 40) -> list[TickerEvent]:
        return list(self.events)[::-1][:n]

    def update(self, now: datetime, zones: list[ZoneState], feeds: list[FeedHealth],
               new_incidents: list[CivicIncident], alert_events: list[tuple[str, Alert]]) -> None:
        for inc in new_incidents[-6:]:
            zone = ZONES_BY_ID[inc.zone_id]
            self.add(inc.timestamp, inc.zone_id, "incident",
                     f"{zone.short_name}: {INCIDENT_CATEGORIES[inc.category]['label']} reported",
                     "low" if inc.severity == "low" else "moderate")

        for z in zones:
            prev = self._prev_zones.get(z.id)
            prev_anoms = {a.metric for a in prev.anomalies} if prev else set()
            for a in z.anomalies:
                if a.metric not in prev_anoms:
                    self.add(now, z.id, "anomaly", f"{z.short_name}: {a.description}", a.severity)
            for metric in prev_anoms - {a.metric for a in z.anomalies}:
                self.add(now, z.id, "anomaly", f"{z.short_name}: {METRICS[metric].label} back within normal range")
            prev_links = {r.id for r in prev.relationships if r.strength != "weak"} if prev else set()
            for r in z.relationships:
                if r.strength != "weak" and r.id not in prev_links:
                    self.add(now, z.id, "relationship",
                             f"{z.short_name}: possible link — {r.title.lower()} ({r.strength})", "moderate")
            if prev and prev.status != z.status:
                self.add(now, z.id, "status", f"{z.name} is now {z.status.value} — {z.status_label}",
                         "high" if z.status.value == "RED" else "low")
            self._prev_zones[z.id] = z

        for event, alert in alert_events:
            self.add(now, alert.zone_id, "alert", f"{_ALERT_PREFIX[event]}: {alert.title}",
                     "high" if alert.level == "critical" and event != "resolved" else "low")

        for f in feeds:
            prev = self._prev_feed_status.get(f.id)
            if prev is not None and prev != f.status:
                self.add(now, None, "feed", f"{f.label} feed is now {f.status.value}",
                         "none" if f.status in HEALTHY_FEED_STATUSES else "moderate")
            self._prev_feed_status[f.id] = f.status
