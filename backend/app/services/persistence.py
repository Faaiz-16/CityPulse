"""Best-effort database persistence.

Every method catches database errors, records them in ``self.ok`` / ``self.last_error`` and
returns normally. A database problem therefore degrades history and alert storage but never
stops the live pulse. ``/api/health`` reports the storage state.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import SQLAlchemyError

from app import database as db
from app.data_sources.city_model import CityModel
from app.geo.zones import ZONES
from app.schemas import Alert, CivicIncident, CivicReading, ZoneState
from app.simulation.history import generate_history

log = logging.getLogger("citypulse.db")


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # SQLite returns naive datetimes


class Persistence:
    def __init__(self) -> None:
        self.ok = True
        self.last_error: str | None = None

    def _fail(self, what: str, exc: Exception) -> None:
        self.ok = False
        self.last_error = f"{what} failed"
        log.warning("database: %s failed: %s", what, exc.__class__.__name__)

    def _succeed(self) -> None:
        self.ok, self.last_error = True, None

    # ------------------------------------------------------------------ setup
    def init(self) -> bool:
        try:
            db.init_db()
            with db.SessionLocal() as session:
                if session.scalar(select(func.count()).select_from(db.ZoneRow)) == 0:
                    session.add_all(db.ZoneRow(
                        id=z.id, number=z.number, name=z.name, short_name=z.short_name,
                        boundary={"type": "Polygon", "coordinates": [z.geojson_ring()]}) for z in ZONES)
                    session.commit()
            self._succeed()
            return True
        except SQLAlchemyError as exc:
            self._fail("initialisation", exc)
            return False

    def ensure_history(self, model: CityModel, now: datetime, days: int
                       ) -> tuple[list[tuple[str, str, datetime, float]], list[tuple[str, str, datetime]]]:
        """Load stored history, (re)generating it if missing or more than a day old."""
        try:
            with db.SessionLocal() as session:
                latest = session.scalar(select(func.max(db.ReadingRow.ts)).where(db.ReadingRow.is_history))
                if latest is None or _utc(latest) < now - timedelta(days=1):
                    log.info("generating %s days of synthetic history…", days)
                    session.execute(delete(db.ReadingRow).where(db.ReadingRow.is_history))
                    session.execute(delete(db.IncidentRow).where(db.IncidentRow.is_history))
                    readings, incidents = generate_history(model, now, days)
                    session.execute(insert(db.ReadingRow), readings)
                    session.execute(insert(db.IncidentRow), incidents)
                    session.commit()
                    self._succeed()
                    return ([(r["zone_id"], r["metric"], r["ts"], r["value"]) for r in readings],
                            [(i["zone_id"], i["category"], i["ts"]) for i in incidents])

                rows = session.execute(select(db.ReadingRow.zone_id, db.ReadingRow.metric, db.ReadingRow.ts,
                                              db.ReadingRow.value).where(db.ReadingRow.is_history)).all()
                inc = session.execute(select(db.IncidentRow.zone_id, db.IncidentRow.category, db.IncidentRow.ts)
                                      .where(db.IncidentRow.is_history)).all()
            self._succeed()
            return ([(z, m, _utc(t), v) for z, m, t, v in rows], [(z, c, _utc(t)) for z, c, t in inc])
        except SQLAlchemyError as exc:
            self._fail("loading history", exc)
            return [], []

    def load_history_between(self, start: datetime, end: datetime
                             ) -> tuple[list[tuple], list[tuple]]:
        """History rows in [start, end] for replay: (zone, metric, ts, value), (id, zone, cat, sev, ts, lat, lon)."""
        try:
            with db.SessionLocal() as session:
                rows = session.execute(
                    select(db.ReadingRow.zone_id, db.ReadingRow.metric, db.ReadingRow.ts, db.ReadingRow.value)
                    .where(db.ReadingRow.is_history, db.ReadingRow.ts >= start, db.ReadingRow.ts <= end)
                    .order_by(db.ReadingRow.ts)).all()
                inc = session.execute(
                    select(db.IncidentRow.id, db.IncidentRow.zone_id, db.IncidentRow.category,
                           db.IncidentRow.severity, db.IncidentRow.ts, db.IncidentRow.lat, db.IncidentRow.lon)
                    .where(db.IncidentRow.is_history, db.IncidentRow.ts >= start, db.IncidentRow.ts <= end)
                    .order_by(db.IncidentRow.ts)).all()
            self._succeed()
            return ([(z, m, _utc(t), v) for z, m, t, v in rows],
                    [(i, z, c, s, _utc(t), la, lo) for i, z, c, s, t, la, lo in inc])
        except SQLAlchemyError as exc:
            self._fail("loading replay data", exc)
            return [], []

    # ------------------------------------------------------------------ writes
    def save_live(self, readings: list[CivicReading], incidents: list[CivicIncident]) -> None:
        if not readings and not incidents:
            return
        try:
            with db.SessionLocal() as session:
                if readings:
                    session.execute(insert(db.ReadingRow), [{
                        "source": r.source, "source_type": r.source_type.value, "provider": r.provider,
                        "zone_id": r.zone_id, "ts": r.timestamp, "ingested_at": r.ingested_at,
                        "metric": r.metric, "value": r.value, "unit": r.unit, "confidence": r.confidence,
                        "data_status": r.data_status.value, "sensor_id": r.sensor_id, "is_history": False,
                        "meta": r.metadata} for r in readings])
                for i in incidents:
                    session.merge(db.IncidentRow(
                        id=i.id, source=i.source, zone_id=i.zone_id, ts=i.timestamp, ingested_at=i.ingested_at,
                        category=i.category, severity=i.severity, lat=i.lat, lon=i.lon,
                        data_status=i.data_status.value, is_history=False, meta=i.metadata))
                session.commit()
            self._succeed()
        except SQLAlchemyError as exc:
            self._fail("saving readings", exc)

    def save_alert(self, alert: Alert, key: str) -> None:
        try:
            with db.SessionLocal() as session:
                session.merge(db.AlertRow(
                    id=alert.id, key=key, zone_id=alert.zone_id, level=alert.level, kind=alert.kind,
                    title=alert.title, observed=alert.observed, possible_relationship=alert.possible_relationship,
                    causation_note=alert.causation_note, opened_at=alert.opened_at, updated_at=alert.updated_at,
                    resolved_at=alert.resolved_at))
                session.commit()
            self._succeed()
        except SQLAlchemyError as exc:
            self._fail("saving alert", exc)
            raise

    def save_snapshot(self, now: datetime, zones: list[ZoneState]) -> None:
        try:
            with db.SessionLocal() as session:
                session.add_all(db.ZoneSnapshotRow(
                    ts=now, zone_id=z.id, status=z.status.value,
                    anomalies=[a.metric for a in z.anomalies],
                    relationships=[r.rule_id for r in z.relationships if r.strength != "weak"]) for z in zones)
                session.commit()
            self._succeed()
        except SQLAlchemyError as exc:
            self._fail("saving snapshot", exc)

    def save_simulation_event(self, now: datetime, event_type: str, zone_id: str | None, params: dict) -> None:
        try:
            with db.SessionLocal() as session:
                session.add(db.SimulationEventRow(at=now, event_type=event_type, zone_id=zone_id, params=params))
                session.commit()
            self._succeed()
        except SQLAlchemyError as exc:
            self._fail("saving simulation event", exc)

    def clear_live(self, older_than: datetime | None = None) -> None:
        """Delete live (non-history) data — all of it on reset, or only rows older than a cutoff."""
        try:
            with db.SessionLocal() as session:
                if older_than is None:
                    session.execute(delete(db.ReadingRow).where(db.ReadingRow.is_history.is_(False)))
                    session.execute(delete(db.IncidentRow).where(db.IncidentRow.is_history.is_(False)))
                    session.execute(delete(db.AlertRow))
                    session.execute(delete(db.ZoneSnapshotRow))
                else:
                    session.execute(delete(db.ReadingRow).where(
                        db.ReadingRow.is_history.is_(False), db.ReadingRow.ts < older_than))
                    session.execute(delete(db.ZoneSnapshotRow).where(db.ZoneSnapshotRow.ts < older_than))
                session.commit()
            self._succeed()
        except SQLAlchemyError as exc:
            self._fail("clearing live data", exc)
