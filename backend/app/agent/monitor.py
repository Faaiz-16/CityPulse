"""CityPulse monitoring agent.

Runs after every analysis tick and decides whether anything deserves an alert:

    CHECK FEEDS → CHECK DATA QUALITY → CHECK ANOMALIES → CHECK RELATED SIGNALS
      → CHECK ROLLING WINDOW → DECIDE → OPEN / UPDATE / RESOLVE ALERTS → EXPLAIN

It follows the same epistemic rules as the rest of the system: every alert separates
  OBSERVED CONDITIONS  (measured facts)
  POSSIBLE RELATIONSHIP (hedged, from the correlation engine)
  CAUSATION NOTE       (always: not confirmed)
and it can only raise alerts about things present in the structured civic state.

Alerts use hysteresis: an alert is resolved only after its condition has been absent for
``resolve_after_runs`` consecutive checks, so a single noisy reading doesn't flicker it.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.schemas import Alert, FeedHealth, FeedStatus, ZoneState, ZoneStatus

log = logging.getLogger("citypulse.agent")

CAUSATION_NOTE = ("Not a confirmed cause: CityPulse found signals that overlap in place and time. "
                  "Official sources should confirm causes.")
_LEVEL_RANK = {"info": 0, "warning": 1, "critical": 2}


@dataclass
class Candidate:
    key: str
    zone_id: str | None
    level: str
    kind: str
    title: str
    observed: list[str]
    possible_relationship: str | None


class MonitoringAgent:
    def __init__(self, persist: Callable[[Alert, str], None] | None = None,
                 resolve_after_runs: int = 3) -> None:
        self.persist = persist  # callback(alert, key) to store in the database (best effort)
        self.resolve_after_runs = resolve_after_runs
        self._open: dict[str, Alert] = {}
        self._missing_runs: dict[str, int] = {}
        self._resolved: list[Alert] = []
        self._next_id = 1
        self.trace: list[str] = []
        self.runs = 0

    # ------------------------------------------------------------------- public
    def run(self, zones: list[ZoneState], feeds: list[FeedHealth], now: datetime) -> list[tuple[str, Alert]]:
        """One monitoring pass. Returns [(event, alert)] for alerts opened/escalated/resolved."""
        self.runs += 1
        trace: list[str] = []
        candidates: list[Candidate] = []

        # 1–2. Feeds and data quality
        degraded = [f for f in feeds if f.status not in (FeedStatus.LIVE, FeedStatus.SIMULATED)]
        trace.append(f"Checked {len(feeds)} feeds: " + (
            ", ".join(f"{f.label} {f.status.value}" for f in degraded) if degraded else "all healthy"))
        for f in degraded:
            if f.status in (FeedStatus.UNAVAILABLE, FeedStatus.STALE, FeedStatus.FALLBACK):
                candidates.append(Candidate(
                    key=f"feed:{f.id}", zone_id=None,
                    level="warning" if f.status != FeedStatus.FALLBACK else "info",
                    kind="data_quality", title=f"{f.label} feed {f.status.value.lower()}",
                    observed=[f.message], possible_relationship=None))
        rejected = sum(f.records_rejected for f in feeds)
        trace.append(f"Data quality: {rejected} malformed record(s) rejected so far")

        # 3–5. Anomalies, related signals, rolling window → decisions per zone
        n_anom = sum(len(z.anomalies) for z in zones)
        trace.append(f"Checked anomalies: {n_anom} active across {len(zones)} zones")
        for z in zones:
            links = [r for r in z.relationships if r.strength != "weak"]
            if z.anomalies:
                trace.append(f"{z.name}: {len(z.anomalies)} anomal{'y' if len(z.anomalies) == 1 else 'ies'}, "
                             f"{len(links)} possible link(s) in the rolling window → {z.status.value}")
            for risk in z.risks:
                if risk.kind == "potential_disruption":
                    lead = max(links, key=lambda r: r.score) if links else None
                    candidates.append(Candidate(
                        key=f"{z.id}:disruption", zone_id=z.id, level="critical", kind="potential_disruption",
                        title=f"Potential civic disruption detected in {z.name}",
                        observed=[a.description for a in z.anomalies],
                        possible_relationship=lead.statement if lead else None))
                else:
                    candidates.append(Candidate(
                        key=risk.id, zone_id=z.id, level="warning", kind="early_warning",
                        title=f"Early warning: {risk.headline}", observed=risk.evidence,
                        possible_relationship=None))
            if z.status != ZoneStatus.RED:
                for rel in links:
                    candidates.append(Candidate(
                        key=rel.id, zone_id=z.id, level="warning", kind="possible_relationship",
                        title=f"Possible link in {z.name}: {rel.title.lower()}",
                        observed=rel.evidence[:3], possible_relationship=rel.statement))
            high = [a for a in z.anomalies if a.severity == "high"]
            if high and not links and not z.risks:
                a = high[0]
                candidates.append(Candidate(
                    key=f"{z.id}:anomaly:{a.metric}", zone_id=z.id, level="warning", kind="anomaly",
                    title=f"{a.label} highly unusual in {z.name}", observed=[a.description],
                    possible_relationship=None))

        # 6–7. Open / update / resolve
        events = self._reconcile(candidates, now)
        opened = sum(1 for e, _ in events if e == "opened")
        resolved = sum(1 for e, _ in events if e == "resolved")
        trace.append(f"Decision: {len(self._open)} active alert(s); {opened} opened, {resolved} resolved this run")
        self.trace = trace
        return events

    def active(self) -> list[Alert]:
        return sorted(self._open.values(), key=lambda a: (-_LEVEL_RANK[a.level], a.opened_at))

    def recent_resolved(self, n: int = 10) -> list[Alert]:
        return self._resolved[-n:][::-1]

    def reset(self) -> None:
        self._open.clear()
        self._missing_runs.clear()
        self._resolved.clear()

    # ------------------------------------------------------------------ helpers
    def _reconcile(self, candidates: list[Candidate], now: datetime) -> list[tuple[str, Alert]]:
        events: list[tuple[str, Alert]] = []
        seen = set()
        for c in candidates:
            seen.add(c.key)
            self._missing_runs.pop(c.key, None)
            existing = self._open.get(c.key)
            if existing is None:
                alert = Alert(id=self._next_id, zone_id=c.zone_id, level=c.level, kind=c.kind, title=c.title,
                              observed=c.observed, possible_relationship=c.possible_relationship,
                              causation_note=CAUSATION_NOTE, opened_at=now, updated_at=now,
                              resolved_at=None, active=True)
                self._next_id += 1
                self._open[c.key] = alert
                events.append(("opened", alert))
                self._save(alert, c.key)
            else:
                escalated = _LEVEL_RANK[c.level] > _LEVEL_RANK[existing.level]
                existing.observed, existing.updated_at = c.observed, now
                existing.possible_relationship = c.possible_relationship or existing.possible_relationship
                if escalated:
                    existing.level, existing.title = c.level, c.title
                    events.append(("escalated", existing))
                    self._save(existing, c.key)

        critical_zones = {a.zone_id for a in self._open.values() if a.level == "critical"}
        for key in list(self._open):
            if key in seen:
                continue
            alert = self._open[key]
            if alert.level != "critical" and alert.zone_id in critical_zones:
                # Superseded: folded into the zone's disruption alert, not "resolved".
                self._open.pop(key)
                self._missing_runs.pop(key, None)
                continue
            self._missing_runs[key] = self._missing_runs.get(key, 0) + 1
            if self._missing_runs[key] >= self.resolve_after_runs:
                alert = self._open.pop(key)
                self._missing_runs.pop(key, None)
                alert.active, alert.resolved_at, alert.updated_at = False, now, now
                self._resolved.append(alert)
                self._resolved = self._resolved[-50:]
                events.append(("resolved", alert))
                self._save(alert, key)
        return events

    def _save(self, alert: Alert, key: str) -> None:
        if self.persist is None:
            return
        try:
            self.persist(alert, key)
        except Exception:
            log.warning("could not persist alert %s (database issue); continuing", alert.id)
