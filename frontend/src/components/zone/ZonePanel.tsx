import { Bot, CircleHelp, FileWarning, Info, X } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { usePolling } from "../../hooks/usePolling";
import { api } from "../../services/api";
import type { FeedHealth, ZoneState } from "../../types";
import { agoText, clockTime } from "../../utils/format";
import { ExplanationBlock, SourceTag } from "../SummaryPanel";
import { StatusBadge } from "../ui/StatusBadge";
import { RelationshipCard, RiskCard } from "./InsightCards";
import { MetricCard } from "./MetricCard";
import { SignalChart } from "./SignalChart";

const CARD_ORDER = [
  "rain_mm_h",
  "congestion_pct",
  "transit_delay_min",
  "waterlogging_reports",
  "water_level_cm",
  "aqi",
  "outage_signal_reports",
  "incident_reports",
];

interface Props {
  zone: ZoneState;
  feeds: FeedHealth[];
  now: number;
  onClose: () => void;
}

function Section({ title, children, hint }: { title: string; children: React.ReactNode; hint?: string }) {
  return (
    <section className="border-t px-5 py-4" style={{ borderColor: "var(--line)" }}>
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <h3 className="label-caps">{title}</h3>
        {hint && <span className="text-[10.5px] text-[var(--faint)]">{hint}</span>}
      </div>
      {children}
    </section>
  );
}

/** The investigation layer: why might this be happening, which signals support it, how unusual, what changed. */
export function ZonePanel({ zone, feeds, now, onClose }: Props) {
  const fetcher = useCallback(() => api.zone(zone.id), [zone.id]);
  const { data: detail } = usePolling(fetcher, 3000);
  const closeRef = useRef<HTMLButtonElement>(null);
  const d = detail?.zone.id === zone.id ? detail : null;

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zone.id, onClose]);

  const degraded = feeds.filter((f) => f.status !== "LIVE" && f.status !== "SIMULATED");
  const links = [...zone.relationships].sort((a, b) => b.score - a.score);

  return (
    <aside
      className="panel cp-fade-in pointer-events-auto flex max-h-full min-h-0 flex-col overflow-hidden shadow-2xl"
      aria-label={`${zone.name} details`}
    >
      <header className="px-5 pb-4 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="label-caps">Zone details</p>
            <h2 className="text-xl font-bold tracking-tight">{zone.name}</h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[var(--muted)] hover:bg-white/5 hover:text-[var(--text)]"
            aria-label="Close zone details"
          >
            <X size={18} />
          </button>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusBadge status={zone.status} label={zone.status_label} size="lg" />
          <span className="text-[14px] font-medium">{zone.headline}</span>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--faint)]">
          <span>{zone.anomalies.length} unusual signal{zone.anomalies.length === 1 ? "" : "s"}</span>
          <span>{links.filter((r) => r.strength !== "weak").length} possible link(s)</span>
          <span>Rolling window: last 10 min</span>
        </div>
      </header>

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        {zone.risks.length > 0 && (
          <div className="space-y-2 px-5 pb-4">
            {zone.risks.map((r) => (
              <RiskCard key={r.id} risk={r} />
            ))}
          </div>
        )}

        <Section title="In plain language">
          {d?.explanation ? (
            <>
              <div className="mb-2">
                <SourceTag by={d.explanation_by} />
              </div>
              <ExplanationBlock sections={d.explanation} />
            </>
          ) : (
            <p className="text-[13px] text-[var(--muted)]">Loading explanation…</p>
          )}
        </Section>

        <Section title="Signals now vs. normal" hint="Observed measurements">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {CARD_ORDER.filter((k) => zone.metrics[k]).map((k) => (
              <MetricCard key={k} m={zone.metrics[k]} series={d?.series[k]} />
            ))}
          </div>
        </Section>

        <Section title="Possible relationships" hint="Possible links — not confirmed causes">
          {links.length === 0 && zone.insufficient_evidence.length === 0 && zone.cannot_assess.length === 0 && (
            <p className="text-[13px] text-[var(--muted)]">No relationships detected — nothing unusual to connect.</p>
          )}
          <div className="space-y-2">
            {links.map((r, i) => (
              <RelationshipCard key={r.id} rel={r} defaultOpen={i === 0 && r.strength !== "weak"} />
            ))}
          </div>
          {zone.insufficient_evidence.map((n) => (
            <p key={n} className="mt-2 flex gap-2 rounded-lg p-2.5 text-[12.5px] text-[var(--muted)]" style={{ background: "var(--panel-2)" }}>
              <CircleHelp size={14} className="mt-0.5 shrink-0" aria-hidden /> {n}
            </p>
          ))}
          {zone.cannot_assess.map((n) => (
            <p key={n} className="mt-2 flex gap-2 rounded-lg p-2.5 text-[12.5px] text-[var(--warn)]" style={{ background: "var(--warn-soft)" }}>
              <Info size={14} className="mt-0.5 shrink-0" aria-hidden /> {n}
            </p>
          ))}
        </Section>

        <Section title="Last 15 minutes" hint="100 = normal for this time of day">
          {d ? <SignalChart series={d.series} baselines={d.baselines} /> : <div className="h-56 animate-pulse rounded-lg bg-[var(--panel-2)]" />}
        </Section>

        <Section title="Recent civic reports" hint="Anonymous · last 10 min">
          {zone.recent_incidents.length === 0 ? (
            <p className="text-[13px] text-[var(--muted)]">No reports in the rolling window.</p>
          ) : (
            <ul className="space-y-1 text-[12.5px]">
              {zone.recent_incidents.slice(0, 10).map((i) => (
                <li key={i.id} className="flex items-center gap-2">
                  <FileWarning size={13} className="text-[var(--muted)]" aria-hidden />
                  <span>{i.label}</span>
                  <span className="ml-auto font-mono text-[11px] text-[var(--faint)]">{clockTime(i.timestamp)}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        {d && d.agent_trace.length > 0 && (
          <Section title="Monitoring agent — last check">
            <ol className="space-y-0.5 text-[12px] text-[var(--muted)]">
              {d.agent_trace.map((line, i) => (
                <li key={i} className="flex gap-2">
                  <Bot size={12} className="mt-0.5 shrink-0 text-[var(--pulse)]" aria-hidden />
                  {line}
                </li>
              ))}
            </ol>
          </Section>
        )}

        <Section title="Data behind this view">
          <ul className="space-y-1 text-[12px]">
            {feeds.map((f) => (
              <li key={f.id} className="flex items-center gap-2">
                <span className="w-32 truncate text-[var(--muted)]">{f.label}</span>
                <span className="font-semibold" style={{ color: f.status === "LIVE" || f.status === "SIMULATED" ? "var(--ok)" : "var(--warn)" }}>
                  {f.status}
                </span>
                <span className="ml-auto text-[var(--faint)]">{agoText(f.last_success_at, now)}</span>
              </li>
            ))}
          </ul>
          {degraded.length > 0 && (
            <p className="mt-2 text-[11.5px] text-[var(--warn)]">
              Some feeds are degraded. Signals from them are marked “not assessed” rather than guessed.
            </p>
          )}
          <p className="mt-2 text-[11px] text-[var(--faint)]">
            Certain = measured values above. Possible = relationships (timing + location only). CityPulse never claims one signal caused another.
          </p>
        </Section>
      </div>
    </aside>
  );
}
