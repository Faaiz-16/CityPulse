import type { ZoneState } from "../types";

// Jaipur is a 9 × 9 grid: columns A–I (west → east), rows 1–9 (north → south). "F4" = Walled City.

export function parseRef(id: string): { row: number; col: number } {
  return { row: Number(id.slice(1)) - 1, col: id.charCodeAt(0) - 65 };
}

const RANK = { RED: 0, YELLOW: 1, GREEN: 2 } as const;
const SEV = { high: 3, moderate: 2, low: 1, none: 0 } as const;

/** How strongly an area stands out: status first, then how many and how severe its unusual signals. */
export function weight(z: ZoneState): number {
  return (2 - RANK[z.status]) * 1000 + z.risks.length * 100 + z.anomalies.reduce((s, a) => s + SEV[a.severity], 0);
}

export interface Hotspot {
  lead: ZoneState; // the area at the heart of it
  cells: ZoneState[]; // every touching unusual area (lead first)
  status: ZoneState["status"];
}

/**
 * Touching unusual areas form one hotspot (a storm covers several cells). The map labels and the
 * alerts talk about hotspots, so one storm is one story — not five.
 */
export function hotspots(zones: ZoneState[]): Hotspot[] {
  const unusual = new Map(zones.filter((z) => z.status !== "GREEN").map((z) => [z.id, z]));
  const seen = new Set<string>();
  const out: Hotspot[] = [];
  for (const start of unusual.values()) {
    if (seen.has(start.id)) continue;
    const cells: ZoneState[] = [];
    const queue = [start];
    seen.add(start.id);
    while (queue.length) {
      const z = queue.pop()!;
      cells.push(z);
      const { row, col } = parseRef(z.id);
      for (let dr = -1; dr <= 1; dr++) {
        for (let dc = -1; dc <= 1; dc++) {
          const r = row + dr, c = col + dc;
          if (r < 0 || c < 0 || r > 8 || c > 8) continue;
          const id = `${String.fromCharCode(65 + c)}${r + 1}`;
          const n = unusual.get(id);
          if (n && !seen.has(id)) {
            seen.add(id);
            queue.push(n);
          }
        }
      }
    }
    cells.sort((a, b) => weight(b) - weight(a));
    out.push({ lead: cells[0], cells, status: cells.some((c) => c.status === "RED") ? "RED" : "YELLOW" });
  }
  return out.sort((a, b) => weight(b.lead) - weight(a.lead));
}

/** "Walled City" or "Walled City + 4 nearby areas". */
export function hotspotPlace(h: Hotspot): string {
  const others = h.cells.length - 1;
  return others > 0 ? `${h.lead.short_name} + ${others} nearby area${others > 1 ? "s" : ""}` : h.lead.short_name;
}

/** A risk headline without its " in <area name>" tail. */
export function withoutPlace(text: string, z: ZoneState): string {
  return text.replace(` in ${z.name}`, "");
}
