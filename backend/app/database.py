"""Database engine, session factory and ORM tables.

SQLite by default (zero setup). Because everything goes through SQLAlchemy, switching to
PostgreSQL only needs a different ``CITYPULSE_DATABASE_URL``.

The live analysis does NOT depend on the database: recent readings are kept in memory
(see ``services/store.py``). The database stores history (for baselines and replay),
alerts, zone snapshots and the simulation log. If it becomes unavailable, the live pulse
keeps running and ``/api/health`` reports storage as degraded.
"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class ZoneRow(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(64))
    short_name: Mapped[str] = mapped_column(String(32))
    boundary: Mapped[dict] = mapped_column(JSON)  # GeoJSON polygon


class ReadingRow(Base):
    __tablename__ = "civic_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(64))
    zone_id: Mapped[str] = mapped_column(String(8))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metric: Mapped[str] = mapped_column(String(32))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    data_status: Mapped[str] = mapped_column(String(16))
    sensor_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_history: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (Index("ix_readings_zone_metric_ts", "zone_id", "metric", "ts"),)


class IncidentRow(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    zone_id: Mapped[str] = mapped_column(String(8))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    data_status: Mapped[str] = mapped_column(String(16))
    is_history: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (Index("ix_incidents_zone_ts", "zone_id", "ts"),)


class AlertRow(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(96), index=True)  # de-duplication key
    zone_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    level: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    observed: Mapped[list] = mapped_column(JSON, default=list)
    possible_relationship: Mapped[str | None] = mapped_column(String(500), nullable=True)
    causation_note: Mapped[str] = mapped_column(String(300))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ZoneSnapshotRow(Base):
    """One row per zone per snapshot — powers the heat-map timeline."""

    __tablename__ = "zone_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    zone_id: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(8))
    anomalies: Mapped[list] = mapped_column(JSON, default=list)
    relationships: Mapped[list] = mapped_column(JSON, default=list)


class SimulationEventRow(Base):
    __tablename__ = "simulation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str] = mapped_column(String(48))
    zone_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        if path not in (":memory:", ""):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 5})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # WAL lets API reads run while the pipeline writes
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
