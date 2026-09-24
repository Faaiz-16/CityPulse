"""The common civic data model and the structured civic state.

Every feed, whatever its raw format, is converted into ``CivicReading`` (a measured value)
or ``CivicIncident`` (a discrete report). The analysis engine produces a ``CityState``
which is the single source of truth for the map, the dashboard, the AI layer and the agent.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SourceType(StrEnum):
    WEATHER = "weather"
    TRAFFIC = "traffic"
    INCIDENTS = "incidents"
    AIR_QUALITY = "air_quality"
    IOT_SENSORS = "iot_sensors"


class DataStatus(StrEnum):
    """How a single record was obtained."""

    LIVE = "live"  # from a real public API
    SIMULATED = "simulated"  # from the synthetic city model (by design)
    FALLBACK = "fallback"  # synthetic substitute because the live API failed


class FeedStatus(StrEnum):
    """Health of a whole feed, shown in the UI."""

    LIVE = "LIVE"
    SIMULATED = "SIMULATED"
    FALLBACK = "FALLBACK"
    DELAYED = "DELAYED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class ZoneStatus(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


Severity = Literal["none", "low", "moderate", "high"]
Strength = Literal["weak", "moderate", "strong"]


# ---------------------------------------------------------------------------
# Common data model (output of normalization)
# ---------------------------------------------------------------------------

class CivicReading(BaseModel):
    source: str  # feed id, e.g. "weather"
    source_type: SourceType
    provider: str  # e.g. "open-meteo", "synthetic-city-model"
    zone_id: str
    timestamp: datetime  # when it was observed (UTC, timezone-aware)
    ingested_at: datetime  # when CityPulse received it (UTC)
    metric: str
    value: float
    unit: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    data_status: DataStatus
    sensor_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CivicIncident(BaseModel):
    """An anonymous civic report. Deliberately has no field that could identify a person."""

    id: str
    source: str
    zone_id: str
    timestamp: datetime
    ingested_at: datetime
    category: str
    severity: Literal["low", "moderate", "high"]
    lat: float
    lon: float
    confidence: float = 1.0
    data_status: DataStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Analysis output (the structured civic state)
# ---------------------------------------------------------------------------

class MetricAssessment(BaseModel):
    metric: str
    label: str
    unit: str
    source: str
    current: float | None  # None = no current data (feed down)
    baseline: float | None
    deviation_pct: float | None
    robust_z: float | None
    threshold: str  # human-readable rule, e.g. "> 30% above baseline"
    is_anomaly: bool
    severity: Severity
    trend: Literal["rising", "falling", "steady", "unknown"]
    samples: int
    last_updated: datetime | None
    data_status: str | None  # data_status of the latest reading
    available: bool


class Anomaly(BaseModel):
    id: str
    zone_id: str
    metric: str
    label: str
    severity: Severity
    current: float
    baseline: float | None
    deviation_pct: float | None
    unit: str
    since: datetime
    description: str  # plain, observed-fact wording


class Relationship(BaseModel):
    """A *possible* link between signals. Never a causal claim."""

    id: str
    zone_id: str
    rule_id: str
    title: str
    signals: list[str]
    strength: Strength
    score: float
    co_movement_r: float | None
    lead_lag: str | None
    window_minutes: int
    evidence: list[str]
    statement: str
    caveat: str


class RiskInsight(BaseModel):
    id: str
    zone_id: str
    kind: Literal["potential_disruption", "early_warning"]
    level: Literal["elevated", "high"]
    headline: str
    evidence: list[str]
    resident_advice: str


class IncidentView(BaseModel):
    id: str
    zone_id: str
    category: str
    label: str
    severity: str
    timestamp: datetime
    lat: float
    lon: float
    data_status: str


class ZoneState(BaseModel):
    id: str
    number: int
    name: str
    short_name: str
    status: ZoneStatus
    status_label: str
    headline: str
    issue_types: list[str]  # icon keys: rain, traffic, incident, air, water, transit
    metrics: dict[str, MetricAssessment]
    anomalies: list[Anomaly]
    relationships: list[Relationship]
    risks: list[RiskInsight]
    insufficient_evidence: list[str]
    cannot_assess: list[str]
    incident_counts: dict[str, int]
    recent_incidents: list[IncidentView]
    centroid: tuple[float, float]


class FeedHealth(BaseModel):
    id: str
    label: str
    source_type: SourceType
    status: FeedStatus
    provider: str
    last_success_at: datetime | None
    age_seconds: float | None
    expected_interval_seconds: float
    message: str
    fault_mode: str  # "none" | "outage" | "delay" | "malformed"
    records_accepted: int
    records_rejected: int


class Alert(BaseModel):
    id: int
    zone_id: str | None
    level: Literal["info", "warning", "critical"]
    kind: str
    title: str
    observed: list[str]
    possible_relationship: str | None
    causation_note: str
    opened_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    active: bool


class SummarySection(BaseModel):
    whats_happening: str
    why_it_matters: str
    possible_connection: str


class Summary(BaseModel):
    headline: str
    sections: SummarySection
    generated_by: Literal["template", "ai"]
    generated_at: datetime
    note: str | None = None


class TickerEvent(BaseModel):
    at: datetime
    zone_id: str | None
    kind: str  # incident | anomaly | relationship | alert | feed | simulation
    text: str
    severity: Severity = "none"


class PulseInfo(BaseModel):
    city_status: ZoneStatus
    bpm: int  # rhythm of the pulse strip; derived from how much is unusual
    active_anomalies: int
    active_relationships: int
    zones_by_status: dict[str, int]


class CityState(BaseModel):
    generated_at: datetime
    city_name: str
    mode: Literal["live", "replay"] = "live"
    replay_time: datetime | None = None
    pulse: PulseInfo
    zones: list[ZoneState]
    feeds: list[FeedHealth]
    alerts: list[Alert]
    summary: Summary
    ticker: list[TickerEvent]
    simulation: dict[str, Any]
    config: dict[str, Any]
