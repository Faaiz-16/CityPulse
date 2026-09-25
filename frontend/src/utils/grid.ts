import type { ZoneState } from "../types";

// Jaipur: 5 × 5 districts (A–E west → east, 1–5 north → south), each split into 3 × 3 blocks
// numbered 1–9 like a keypad. A block ID is "C2-9" = block 9 (south-east) of district C2.
export const BLOCKS = 3;
export const SIZE = 15; // blocks per side

/** Global block row/col (0–14) from a block ID. */
export function parseRef(id: string): { row: number; col: number } {
  const dc = id.charCodeAt(0) - 65, dr = Number(id[1]) - 1, k = Number(id.slice(3)) - 1;
  return { row: dr * BLOCKS + Math.floor(k / BLOCKS), col: dc * BLOCKS + (k % BLOCKS) };
}

/** Block ID from global block row/col. */
export function refOf(row: number, col: number): string {
  const d = `${String.fromCharCode(65 + Math.floor(col / BLOCKS))}${Math.floor(row / BLOCKS) + 1}`;
  return `${d}-${(row % BLOCKS) * BLOCKS + (col % BLOCKS) + 1}`;
}

export const districtOf = (id: string) => id.slice(0, 2);

const RANK = { RED: 0, YELLOW: 1, GREEN: 2 } as const;
const SEV = { high: 3, moderate: 2, low: 1, none: 0 } as const;

/** How strongly a block stands out: status first, then how many and how severe its unusual signals. */
export function weight(z: ZoneState): number {
  return (2 - RANK[z.status]) * 1000 + z.risks.length * 100 + z.anomalies.reduce((s, a) => s + SEV[a.severity], 0);
}

export interface Hotspot {
  lead: ZoneState; // the block at the heart of it
  cells: ZoneState[]; // every touching unusual block (lead first)
  status: ZoneState["status"];
}

/**
 * Touching unusual blocks form one hotspot (a storm covers several blocks). The map labels and the
 * alerts talk about hotspots, so one storm is one story — not nine.
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
          if (r < 0 || c < 0 || r >= SIZE || c >= SIZE) continue;
          const id = refOf(r, c);
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

/** "Walled City" or "Walled City + 8 nearby blocks". */
export function hotspotPlace(h: Hotspot): string {
  const others = h.cells.length - 1;
  return others > 0 ? `${h.lead.short_name} + ${others} nearby block${others > 1 ? "s" : ""}` : h.lead.short_name;
}

/** A risk headline without its " in <area name>" tail. */
export function withoutPlace(text: string, z: ZoneState): string {
  return text.replace(` in ${z.name}`, "");
}
