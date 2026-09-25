// Mirrors backend/app/schemas.py — the structured civic state served by /api/dashboard.

export type ZoneStatus = "GREEN" | "YELLOW" | "RED";
export type FeedStatusValue = "LIVE" | "SIMULATED" | "FALLBACK" | "DELAYED" | "STALE" | "UNAVAILABLE" | "ARCHIVE";
export type Severity = "none" | "low" | "moderate" | "high";
export type Strength = "weak" | "moderate" | "strong";

export interface MetricAssessment {
  metric: string;
  label: string;
  unit: string;
  source: string;
  current: number | null;
  baseline: number | null;
  deviation_pct: number | null;
  robust_z: number | null;
  threshold: string;
  is_anomaly: boolean;
  severity: Severity;
  trend: "rising" | "falling" | "steady" | "unknown";
  samples: number;
  last_updated: string | null;
  data_status: string | null;
  available: boolean;
}

export interface Anomaly {
  id: string;
  zone_id: string;
  metric: string;
  label: string;
  severity: Severity;
  current: number;
  baseline: number | null;
  deviation_pct: number | null;
  unit: string;
  since: string;
  description: string;
}

export interface Relationship {
  id: string;
  zone_id: string;
  rule_id: string;
  title: string;
  signals: string[];
  strength: Strength;
  score: number;
  co_movement_r: number | null;
  lead_lag: string | null;
  window_minutes: number;
  evidence: string[];
  statement: string;
  caveat: string;
}

export interface RiskInsight {
  id: string;
  zone_id: string;
  kind: "potential_disruption" | "early_warning";
  level: "elevated" | "high";
  headline: string;
  evidence: string[];
  resident_advice: string;
}

export interface IncidentView {
  id: string;
  zone_id: string;
  category: string;
  label: string;
  severity: string;
  timestamp: string;
  lat: number;
  lon: number;
  data_status: string;
}

export interface ZoneState {
  id: string;
  number: number;
  name: string;
  short_name: string;
  status: ZoneStatus;
  status_label: string;
  headline: string;
  issue_types: string[];
  metrics: Record<string, MetricAssessment>;
  anomalies: Anomaly[];
  relationships: Relationship[];
  risks: RiskInsight[];
  insufficient_evidence: string[];
  cannot_assess: string[];
  incident_counts: Record<string, number>;
  recent_incidents: IncidentView[];
  anchor: [number, number];
  predictions: Prediction[]; // possible next impacts here (a forecast, not a certainty)
}

export interface Prediction {
  kind: "flooding" | "power_cut" | "traffic" | "bus_delays" | "air_quality";
  label: string;
  likelihood: "low" | "medium" | "high";
  score: number;
  horizon: string;
  reason: string;
  source_zone: string;
  nearby: boolean;
}

export interface FeedHealth {
  id: string;
  label: string;
  source_type: string;
  status: FeedStatusValue;
  provider: string;
  last_success_at: string | null;
  age_seconds: number | null;
  expected_interval_seconds: number;
  message: string;
  fault_mode: "none" | "outage" | "delay" | "malformed";
  records_accepted: number;
  records_rejected: number;
}

export interface Alert {
  id: number;
  zone_id: string | null;
  level: "info" | "warning" | "critical";
  kind: string;
  title: string;
  observed: string[];
  possible_relationship: string | null;
  causation_note: string;
  opened_at: string;
  updated_at: string;
  resolved_at: string | null;
  active: boolean;
}

export interface SummarySection {
  whats_happening: string;
  why_it_matters: string;
  possible_connection: string;
}

export interface Summary {
  headline: string;
  sections: SummarySection;
  generated_by: "template" | "ai";
  generated_at: string;
  note: string | null;
}

export interface TickerEvent {
  at: string;
  zone_id: string | null;
  kind: string;
  text: string;
  severity: Severity;
}

export interface PulseInfo {
  city_status: ZoneStatus;
  bpm: number;
  active_anomalies: number;
  active_relationships: number;
  zones_by_status: Record<ZoneStatus, number>;
}

export interface ScenarioStage {
  key: string;
  label: string;
  reached_at: string | null;
  t_plus_s?: number | null;
  expected_at_s?: number | null;
}

export interface ScenarioPreset {
  id: string;
  name: string;
  tagline: string;
  zone_id: string;
  place: string;
  ready_s: number;
  severity: "high" | "moderate" | "low";
  duration_s: number;
  feeds: string[];
  expected: string;
  icon: string;
  storyline: { key: string; label: string; expected_at_s: number }[];
}

export interface SimulationStatus {
  active_events: { event: string; label: string; zone_id: string; started_at: string; ends_at: string; level: number }[];
  scenario: {
    id: string;
    name: string;
    focus_zone: string;
    expected: string;
    started_at: string;
    elapsed_s: number;
    complete: boolean;
    stages: ScenarioStage[];
  } | null;
  clock: { paused: boolean; speed: number };
  custom: { zone_id: string; values: Record<string, number>; duration_s: number } | null;
  presets: ScenarioPreset[];
  custom_controls: string[];
  available_events: { id: string; label: string }[];
}

export interface PublicConfig {
  rolling_window_minutes: number;
  current_window_seconds: number;
  tick_seconds: number;
  live_apis: boolean;
  ai_enabled: boolean;
  ai_status: string;
  timezone: string;
  thresholds: Record<string, number>;
  baseline_history_days: number;
}

export interface CityState {
  generated_at: string;
  city_name: string;
  mode: "live" | "replay";
  replay_time: string | null;
  pulse: PulseInfo;
  zones: ZoneState[];
  feeds: FeedHealth[];
  alerts: Alert[];
  summary: Summary;
  ticker: TickerEvent[];
  simulation: SimulationStatus;
  config: PublicConfig;
}

export interface ZoneBoundary {
  id: string;
  number: number;
  name: string;
  short_name: string;
  row: number; // global block row, 0 (north) … 14
  col: number; // global block column, 0 (west) … 14
  district: string; // "C2"
  district_name: string; // "Walled City"
  centroid: [number, number];
  anchor: [number, number];
  boundary: { type: "Polygon"; coordinates: number[][][] };
}

export interface Road {
  cell: string;
  kind: "major" | "minor";
  name: string;
  path: [number, number][];
}

export interface MapInfo {
  city: string;
  // 5 × 5 districts (A–E, 1–5), each 3 × 3 blocks → a 15 × 15 block grid
  grid: { north: number; south: number; west: number; east: number; rows: number; cols: number; districts: number; blocks: number; col_letters: string };
  roads: Road[];
  roads_attribution: string;
}

export interface SeriesPoint {
  t: string;
  v: number | null;
}

export interface Sensor {
  id: string;
  zone_id: string;
  kind: "traffic" | "rain_gauge" | "air_quality" | "water_level";
  lat: number;
  lon: number;
  values: Record<string, { value: number; unit: string; ts: string; data_status: string }>;
}

export interface ZoneDetail {
  zone: ZoneState;
  explanation: SummarySection | null;
  explanation_by: "template" | "ai";
  series: Record<string, SeriesPoint[]>;
  baselines: Record<string, number | null>;
  reports_per_minute: { minute: string; count: number }[];
  sensors: Sensor[];
  alerts: Alert[];
  agent_trace: string[];
}

export interface TimelineEntry {
  at: string;
  zones: Record<string, ZoneStatus>;
}

export interface ReplayMeta {
  available: boolean;
  name: string;
  description: string;
  focus_zone: string;
  start: string;
  end: string;
  step_seconds: number;
  frames: { i: number; t: string; city_status: ZoneStatus; statuses: Record<string, ZoneStatus> }[];
  key_moments: { i: number; t: string; label: string }[];
}
