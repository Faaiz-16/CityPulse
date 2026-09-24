import { Bell, CarFront, CheckCircle2, CloudRain, Database, Droplets, FileWarning, OctagonAlert, TriangleAlert, Waves, Wind, Zap, Bus, type LucideIcon } from "lucide-react";
import type { AlertLevel, MapAlert } from "../utils/alerts";

const LEVEL: Record<AlertLevel, { color: string; word: string }> = {
  critical: { color: "#f87171", word: "Critical" },
  warning: { color: "#fb923c", word: "Warning" },
  notice: { color: "#fbbf24", word: "Notice" },
  info: { color: "#94a3b8", word: "Info" },
};
const KIND_ICON: Record<string, LucideIcon> = {
  disruption: OctagonAlert, warning: TriangleAlert, rain: CloudRain, water: Waves, traffic: CarFront, transit: Bus,
  accident: CarFront, outage: Zap, air: Wind, incident: FileWarning, feed: Database, flood: Droplets,
};

interface Props {
  alerts: MapAlert[];
  max?: number;
  onSelect: (a: MapAlert) => void;
  onMore: () => void;
}

/** Only the few things worth a resident's attention; details are one click away. */
export function AlertsCard({ alerts, max = 4, onSelect, onMore }: Props) {
  const shown = alerts.slice(0, max);
  const rest = alerts.length - shown.length;
  return (
    <section className="glass pointer-events-auto w-full p-3" aria-label="Active alerts">
      <div className="mb-2 flex items-center gap-2 px-1">
        <Bell size={13} className="text-[var(--muted)]" aria-hidden />
        <h2 className="label-caps">Active alerts</h2>
        {alerts.length > 0 && <span className="ml-auto text-[11px] text-[var(--faint)]">{alerts.length}</span>}
      </div>
      {shown.length === 0 ? (
        <p className="flex items-center gap-2 px-1 pb-1 text-[13px] text-[#cbd5e1]">
          <CheckCircle2 size={15} color="var(--ok)" aria-hidden /> All clear — nothing unusual right now.
        </p>
      ) : (
        <ul className="space-y-1">
          {shown.map((a) => {
            const meta = LEVEL[a.level];
            const Icon = KIND_ICON[a.kind] ?? TriangleAlert;
            return (
              <li key={a.id} className="cp-fade-in">
                <button
                  type="button"
                  onClick={() => onSelect(a)}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left hover:bg-white/5"
                  style={{ boxShadow: `inset 3px 0 0 ${meta.color}` }}
                >
                  <Icon size={16} color={meta.color} className="shrink-0" aria-label={meta.word} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-semibold leading-tight">{a.title}</span>
                    <span className="block text-[11px] text-[var(--muted)]">{a.place}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {rest > 0 && (
        <button type="button" onClick={onMore} className="mt-1 w-full rounded-lg px-2 py-1 text-left text-[11.5px] text-[var(--muted)] hover:bg-white/5">
          +{rest} more in Insights
        </button>
      )}
    </section>
  );
}
