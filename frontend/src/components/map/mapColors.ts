// Leaflet writes colours into SVG attributes, where CSS variables don't resolve,
// so the map uses concrete values that match the tokens in index.css.
import type { ZoneStatus } from "../../types";

export const MAP_STATUS: Record<ZoneStatus, string> = {
  GREEN: "#34d399",
  YELLOW: "#fbbf24",
  RED: "#f87171",
};

export const RAIN = "#60a5fa";

export const INCIDENT_COLORS: Record<string, string> = {
  waterlogging: "#60a5fa",
  power_outage: "#facc15",
  traffic_signal: "#fb923c",
  road_accident: "#f87171",
  tree_fall: "#a3e635",
};
export const INCIDENT_DEFAULT = "#94a3b8";

export const SENSOR_COLORS: Record<string, string> = {
  traffic: "#fbbf24",
  rain_gauge: "#60a5fa",
  air_quality: "#c084fc",
  water_level: "#22d3ee",
};
