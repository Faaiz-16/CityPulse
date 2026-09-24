// Leaflet writes colours into SVG attributes, where CSS variables don't resolve,
// so the map uses concrete values that match the tokens in index.css.
import type { ZoneStatus } from "../../types";

export const MAP_STATUS: Record<ZoneStatus, string> = {
  GREEN: "#34d399",
  YELLOW: "#fbbf24",
  RED: "#f87171",
};

export const RAIN = "#38bdf8";
export const RAIN_LIGHT = "#7dd3fc";
export const TRAFFIC_WARM = "#fb923c";
export const TRAFFIC_HOT = "#f87171";
export const HAZE = "#a855f7";

/** Incident kinds shown on the map (level 1–2); everything else is a faint background dot. */
// `metric` = the zone report metric that must be *unusual* before these become icons; routine
// background reports stay faint dots so a normal city looks calm.
export const INCIDENT_KINDS: Record<string, { kind: string; color: string; label: string; metric: string }> = {
  waterlogging: { kind: "water", color: "#38bdf8", label: "Waterlogging", metric: "waterlogging_reports" },
  power_outage: { kind: "power", color: "#facc15", label: "Power / signal outage", metric: "outage_signal_reports" },
  traffic_signal: { kind: "power", color: "#facc15", label: "Power / signal outage", metric: "outage_signal_reports" },
  road_accident: { kind: "accident", color: "#f87171", label: "Road accident", metric: "accident_reports" },
  tree_fall: { kind: "tree", color: "#a3e635", label: "Fallen tree", metric: "rain_mm_h" },
};
export const MINOR_REPORT = "#94a3b8";

export const SENSOR_COLORS: Record<string, string> = {
  traffic: "#fbbf24",
  rain_gauge: "#38bdf8",
  air_quality: "#c084fc",
  water_level: "#22d3ee",
};
