import type { CityState } from "../types";
import { hotspotPlace, hotspots, withoutPlace } from "./grid";
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
 * The few alerts worth showing on the map, derived from the analysed civic state. Touching
 * unusual areas are one hotspot, so a storm over five cells is one alert, not five:
 * possible disruptions first, then early warnings and the strongest unusual signals,
 * then data problems. Everything else lives in the area panel and the Insights drawer.
 */
export function deriveAlerts(state: CityState): MapAlert[] {
  const out: MapAlert[] = [];
  for (const h of hotspots(state.zones)) {
    const lead = h.lead;
    const place = hotspotPlace(h);
    const risk = lead.risks.find((r) => r.kind === "potential_disruption") ?? lead.risks[0];
    if (risk) {
      const title = withoutPlace(risk.headline, lead);
      out.push({
        id: `${lead.id}:${risk.kind}`,
        level: risk.kind === "potential_disruption" ? "critical" : "warning",
        title: risk.kind === "potential_disruption" ? title : `Early warning: ${title.toLowerCase()}`,
        zoneId: lead.id,
        place,
        kind: risk.kind === "potential_disruption" ? "disruption" : "warning",
      });
    }
    // The strongest distinct signals across the hotspot (e.g. heavy rain + water on streets).
    const signals = new Map<string, { severity: string; zoneId: string }>();
    for (const z of h.cells) {
      for (const a of z.anomalies) {
        const prev = signals.get(a.metric);
        if (!prev || (a.severity === "high" && prev.severity !== "high")) signals.set(a.metric, { severity: a.severity, zoneId: z.id });
      }
    }
    let added = 0;
    for (const [metric, { severity, zoneId }] of signals) {
      const meta = SIGNAL_TITLE[metric];
      if (!meta || added >= 2) continue;
      added++;
      out.push({ id: `${lead.id}:${metric}`, level: severity === "high" ? "warning" : "notice", title: meta.title, zoneId, place, kind: meta.kind });
    }
  }
  for (const f of state.feeds) {
    if (isHealthyFeed(f.status)) continue;
    out.push({ id: `feed:${f.id}`, level: "info", title: `${f.label} ${feedWord(f.status)}`, zoneId: null, place: "Data feed", kind: "feed" });
  }
  return out.sort((a, b) => RANK[a.level] - RANK[b.level]);
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
