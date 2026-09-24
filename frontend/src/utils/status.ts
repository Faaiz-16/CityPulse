import {
  AlertTriangle,
  Bus,
  Car,
  CheckCircle2,
  CircleAlert,
  CloudRain,
  Droplets,
  FileWarning,
  Gauge,
  type LucideIcon,
  OctagonAlert,
  Thermometer,
  Waves,
  Wind,
  Zap,
} from "lucide-react";
import type { FeedStatusValue, Severity, Strength, ZoneStatus } from "../types";

// Status is never shown by colour alone: every use pairs the colour with a word and an icon.
export const STATUS_META: Record<ZoneStatus, { color: string; soft: string; word: string; icon: LucideIcon }> = {
  GREEN: { color: "var(--ok)", soft: "var(--ok-soft)", word: "Normal", icon: CheckCircle2 },
  YELLOW: { color: "var(--warn)", soft: "var(--warn-soft)", word: "Attention", icon: CircleAlert },
  RED: { color: "var(--bad)", soft: "var(--bad-soft)", word: "Possible disruption", icon: OctagonAlert },
};

export const FEED_META: Record<FeedStatusValue, { color: string; hint: string }> = {
  LIVE: { color: "var(--ok)", hint: "Real-time data from a public API" },
  SIMULATED: { color: "var(--sim)", hint: "Fresh data from the demo city simulation" },
  FALLBACK: { color: "var(--warn)", hint: "Primary source failing — showing substitute or last-known data" },
  DELAYED: { color: "var(--warn)", hint: "Updates arriving later than expected" },
  STALE: { color: "var(--bad)", hint: "Data is old — not used as current" },
  UNAVAILABLE: { color: "var(--bad)", hint: "No usable data from this feed" },
  ARCHIVE: { color: "var(--link)", hint: "Recorded data being replayed — not live" },
};

/** Feed statuses that mean "delivering usable data as designed". */
export const isHealthyFeed = (s: FeedStatusValue) => s === "LIVE" || s === "SIMULATED" || s === "ARCHIVE";

export const SEVERITY_META: Record<Severity, { color: string; word: string }> = {
  none: { color: "var(--muted)", word: "Normal" },
  low: { color: "var(--warn)", word: "Slightly unusual" },
  moderate: { color: "var(--warn-strong)", word: "Unusual" },
  high: { color: "var(--bad)", word: "Highly unusual" },
};

export const STRENGTH_META: Record<Strength, { color: string; bars: number; word: string }> = {
  weak: { color: "var(--muted)", bars: 1, word: "Weak — insufficient evidence" },
  moderate: { color: "var(--warn)", bars: 2, word: "Moderate" },
  strong: { color: "var(--link)", bars: 3, word: "Strong" },
};

// Icons for issue types and metrics (keys come from the backend metric catalogue).
export const ISSUE_ICONS: Record<string, LucideIcon> = {
  rain: CloudRain,
  traffic: Car,
  transit: Bus,
  air: Wind,
  water: Waves,
  incident: FileWarning,
  temp: Thermometer,
  outage: Zap,
};

export const METRIC_ICONS: Record<string, LucideIcon> = {
  rain_mm_h: CloudRain,
  congestion_pct: Car,
  transit_delay_min: Bus,
  aqi: Wind,
  water_level_cm: Waves,
  incident_reports: FileWarning,
  waterlogging_reports: Droplets,
  outage_signal_reports: Zap,
  temperature_c: Thermometer,
  avg_speed_kmh: Gauge,
};

export const ISSUE_WORDS: Record<string, string> = {
  rain: "Rain",
  traffic: "Traffic",
  transit: "Buses",
  air: "Air quality",
  water: "Flooding",
  incident: "Reports",
};

export const ALERT_ICON = AlertTriangle;
