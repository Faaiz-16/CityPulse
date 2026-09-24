import type { TimelineEntry, ZoneState } from "../types";
import { clockTime } from "../utils/format";
import { MAP_STATUS } from "./map/mapColors";

/**
 * Heat-map timeline: one row per affected block, one cell per 15-second snapshot over the last
 * 30 minutes. Shows how the situation developed — where trouble started and how long it lasted.
 */
export function PulseTimeline({ timeline, zones, onSelectZone }: {
  timeline: TimelineEntry[];
  zones: ZoneState[];
  onSelectZone: (id: string) => void;
}) {
  const cells = timeline.slice(-60);
  const rows = zones
    .map((z) => ({ z, n: cells.filter((c) => c.zones[z.id] && c.zones[z.id] !== "GREEN").length }))
    .filter((r) => r.n > 0)
    .sort((a, b) => b.n - a.n)
    .slice(0, 8)
    .map((r) => r.z);
  const first = cells[0]?.at;
  const last = cells[cells.length - 1]?.at;
  return (
    <div className="panel pointer-events-auto p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="label-caps">Affected blocks over time</h2>
        <span className="font-mono text-[10px] text-[var(--faint)]">
          {first ? `${clockTime(first, false)} → ${clockTime(last, false)}` : "collecting…"}
        </span>
      </div>
      {rows.length === 0 && <p className="text-[12px] text-[var(--muted)]">Every block has been normal for the last 30 minutes.</p>}
      <div className="space-y-1" role="table" aria-label="Area status history">
        {rows.map((z) => (
          <div key={z.id} className="flex items-center gap-2" role="row">
            <button
              type="button"
              onClick={() => onSelectZone(z.id)}
              className="w-24 shrink-0 truncate text-left text-[11px] text-[var(--muted)] hover:text-[var(--text)]"
              role="rowheader" title={z.name}
            >
              {z.short_name}
            </button>
            <div className="flex h-3 flex-1 gap-px overflow-hidden rounded-sm" role="cell">
              {cells.length === 0 && <div className="flex-1 rounded-sm bg-[var(--line-soft)]" />}
              {cells.map((c) => {
                const s = c.zones[z.id];
                return (
                  <div
                    key={c.at}
                    className="flex-1"
                    style={{ background: s ? MAP_STATUS[s] : "var(--line-soft)", opacity: s === "GREEN" ? 0.35 : 0.95 }}
                    title={`${z.short_name} ${clockTime(c.at)}: ${s ?? "no data"}`}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
