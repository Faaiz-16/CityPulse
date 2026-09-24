import { Bot, ChevronRight, OctagonAlert, TriangleAlert, Info, CheckCircle2 } from "lucide-react";
import type { Alert } from "../types";
import { agoText } from "../utils/format";

const LEVEL = {
  critical: { color: "var(--bad)", icon: OctagonAlert, word: "Critical" },
  warning: { color: "var(--warn)", icon: TriangleAlert, word: "Warning" },
  info: { color: "var(--sim)", icon: Info, word: "Info" },
};

interface Props {
  alerts: Alert[];
  now: number;
  onSelectZone: (id: string) => void;
}

/** Alerts raised by the monitoring agent. Observed facts, possible link and causation note are kept apart. */
export function AlertsList({ alerts, now, onSelectZone }: Props) {
  const active = alerts.filter((a) => a.active);
  const resolved = alerts.filter((a) => !a.active).slice(0, 3);
  return (
    <div className="panel p-4">
      <div className="mb-2 flex items-center gap-2">
        <Bot size={15} className="text-[var(--pulse)]" aria-hidden />
        <h2 className="label-caps">Monitoring agent</h2>
        <span className="ml-auto text-[11px] text-[var(--muted)]">{active.length} active</span>
      </div>
      {active.length === 0 && (
        <p className="flex items-center gap-2 text-[13px] text-[var(--muted)]">
          <CheckCircle2 size={14} color="var(--ok)" aria-hidden /> Watching all feeds — nothing needs attention.
        </p>
      )}
      <ul className="space-y-2">
        {active.map((a) => {
          const meta = LEVEL[a.level];
          const Icon = meta.icon;
          return (
            <li key={a.id} className="cp-fade-in">
              <button
                type="button"
                disabled={!a.zone_id}
                onClick={() => a.zone_id && onSelectZone(a.zone_id)}
                className="group w-full rounded-xl p-2.5 text-left transition-colors enabled:hover:bg-white/5"
                style={{ border: `1px solid color-mix(in srgb, ${meta.color} 45%, transparent)`, background: `color-mix(in srgb, ${meta.color} 7%, transparent)` }}
              >
                <div className="flex items-start gap-2">
                  <Icon size={15} color={meta.color} className="mt-0.5 shrink-0" aria-label={meta.word} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-semibold leading-snug">{a.title}</div>
                    {a.observed[0] && (
                      <div className="mt-1 text-[12px] leading-snug text-[var(--muted)]">
                        <span className="font-semibold text-[var(--text)]">Observed: </span>
                        {a.observed.slice(0, 2).join(" ")}
                      </div>
                    )}
                    {a.possible_relationship && (
                      <div className="mt-1 text-[12px] leading-snug text-[#e9d5ff]">
                        <span className="font-semibold">Possible link: </span>
                        {a.possible_relationship}
                      </div>
                    )}
                    {a.kind !== "data_quality" && (
                      <div className="mt-1 text-[11px] italic text-[var(--faint)]">{a.causation_note}</div>
                    )}
                    <div className="mt-1 text-[10.5px] text-[var(--faint)]">Opened {agoText(a.opened_at, now)}</div>
                  </div>
                  {a.zone_id && <ChevronRight size={15} className="mt-0.5 text-[var(--faint)] group-hover:text-[var(--text)]" aria-hidden />}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
      {resolved.length > 0 && (
        <div className="mt-3 border-t pt-2" style={{ borderColor: "var(--line)" }}>
          <div className="label-caps mb-1">Recently resolved</div>
          <ul className="space-y-0.5 text-[12px] text-[var(--faint)]">
            {resolved.map((a) => (
              <li key={a.id} className="truncate">
                ✓ {a.title} · {agoText(a.resolved_at, now)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
