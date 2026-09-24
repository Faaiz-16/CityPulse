import type { CityState, ZoneState } from "../types";
import { isHealthyFeed } from "./status";

export type AlertLevel = "critical" | "warning" | "notice" | "info";

export interface MapAlert {
  id: string;
  level: AlertLevel;
  title: string;
  zoneId: string | null;
  place: string;
  kind: string; // icon key
}

// Short, resident-friendly names for unusual signals.
const SIGNAL_TITLE: Record<string, { title: string; kind: string }> = {
  rain_mm_h: { title: "Heavy rainfall", kind: "rain" },
  water_level_cm: { title: "Water on the streets", kind: "water" },
  waterlogging_reports: { title: "Waterlogging reports", kind: "water" },
  congestion_pct: { title: "Heavy traffic", kind: "traffic" },
  transit_delay_min: { title: "Bus delays", kind: "transit" },
  accident_reports: { title: "Road accident reported", kind: "accident" },
  outage_signal_reports: { title: "Power / signal outages", kind: "outage" },
  aqi: { title: "Poor air quality", kind: "air" },
  incident_reports: { title: "Many civic reports", kind: "incident" },
};

const RANK: Record<AlertLevel, number> = { critical: 0, warning: 1, notice: 2, info: 3 };

/**
 * The few alerts worth showing on the map, derived from the analysed civic state:
 * possible disruptions first, then early warnings and the strongest unusual signals,
 * then data problems. Everything else lives in the zone panel and the Insights drawer.
 */
export function deriveAlerts(state: CityState): MapAlert[] {
  const out: MapAlert[] = [];
  const zones = [...state.zones].sort((a, b) => statusRank(a) - statusRank(b));
  for (const z of zones) {
    if (z.status === "GREEN") continue;
    const place = `Zone ${z.number} — ${z.short_name}`;
    for (const r of z.risks) {
      out.push({
        id: r.id,
        level: r.kind === "potential_disruption" ? "critical" : "warning",
        title: r.kind === "potential_disruption" ? r.headline.replace(/ in Zone .*$/, "") : `Early warning: ${r.headline.replace(/ in Zone .*$/, "").toLowerCase()}`,
        zoneId: z.id,
        place,
        kind: r.kind === "potential_disruption" ? "disruption" : "warning",
      });
    }
    for (const a of z.anomalies.slice(0, 2)) {
      const meta = SIGNAL_TITLE[a.metric];
      if (!meta) continue;
      out.push({
        id: `${z.id}:${a.metric}`,
        level: a.severity === "high" ? "warning" : "notice",
        title: meta.title,
        zoneId: z.id,
        place,
        kind: meta.kind,
      });
    }
  }
  for (const f of state.feeds) {
    if (isHealthyFeed(f.status)) continue;
    out.push({ id: `feed:${f.id}`, level: "info", title: `${f.label} ${feedWord(f.status)}`, zoneId: null, place: "Data feed", kind: "feed" });
  }
  return out.sort((a, b) => RANK[a.level] - RANK[b.level]);
}

function statusRank(z: ZoneState) {
  return z.status === "RED" ? 0 : z.status === "YELLOW" ? 1 : 2;
}

export function feedWord(status: string): string {
  switch (status) {
    case "FALLBACK":
      return "using fallback data";
    case "DELAYED":
      return "delayed";
    case "STALE":
      return "data is stale";
    case "UNAVAILABLE":
      return "temporarily unavailable";
    default:
      return status.toLowerCase();
  }
}
