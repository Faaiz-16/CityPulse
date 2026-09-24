import { Bell, CircleDot, FileWarning, Link2, PlayCircle, Radio, TrendingUp } from "lucide-react";
import type { TickerEvent } from "../types";
import { clockTime } from "../utils/format";

const KIND_ICON = {
  incident: FileWarning,
  anomaly: TrendingUp,
  relationship: Link2,
  alert: Bell,
  feed: Radio,
  simulation: PlayCircle,
  status: CircleDot,
} as const;

const SEV_COLOR = { none: "var(--muted)", low: "var(--warn)", moderate: "var(--warn-strong)", high: "var(--bad)" };

/** Live narrative stream of what the pipeline noticed, newest first. */
export function EventTicker({ events, onSelectZone }: { events: TickerEvent[]; onSelectZone: (id: string) => void }) {
  return (
    <div className="panel flex min-h-0 flex-col p-4">
      <h2 className="label-caps mb-2">Live civic signal stream</h2>
      {events.length === 0 ? (
        <p className="text-[13px] text-[var(--muted)]">Waiting for the first signals…</p>
      ) : (
        <ol className="scroll-thin -mr-2 min-h-0 flex-1 space-y-1 overflow-y-auto pr-2" aria-live="polite">
          {events.slice(0, 30).map((e, i) => {
            const Icon = KIND_ICON[e.kind as keyof typeof KIND_ICON] ?? CircleDot;
            const color = e.kind === "relationship" ? "#d8b4fe" : SEV_COLOR[e.severity];
            return (
              <li key={`${e.at}-${i}`} className={i < 3 ? "cp-fade-in" : undefined}>
                <button
                  type="button"
                  disabled={!e.zone_id}
                  onClick={() => e.zone_id && onSelectZone(e.zone_id)}
                  className="flex w-full items-start gap-2 rounded-md px-1 py-0.5 text-left text-[12px] leading-snug enabled:hover:bg-white/5"
                >
                  <span className="mt-px font-mono text-[10.5px] text-[var(--faint)]">{clockTime(e.at)}</span>
                  <Icon size={13} color={color} className="mt-0.5 shrink-0" aria-hidden />
                  <span className="text-[var(--text)]">{e.text}</span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
