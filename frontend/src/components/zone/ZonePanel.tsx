import { Bot, ChevronDown, CircleHelp, FileWarning, Info, Link2, Users } from "lucide-react";
import { useCallback, useState } from "react";
import { usePolling } from "../../hooks/usePolling";
import type { FeedHealth, ZoneDetail, ZoneState } from "../../types";
import { agoText, clockTime } from "../../utils/format";
import { isHealthyFeed, STATUS_META, STRENGTH_META } from "../../utils/status";
import { Drawer } from "../drawers/Drawer";
import { SourceTag } from "../SummaryPanel";
import { StatusBadge } from "../ui/StatusBadge";
import { RelationshipCard } from "./InsightCards";
import { MetricCard } from "./MetricCard";
import { SignalChart } from "./SignalChart";

const CARD_ORDER = [
  "rain_mm_h", "congestion_pct", "transit_delay_min", "water_level_cm", "waterlogging_reports",
  "accident_reports", "outage_signal_reports", "aqi", "incident_reports",
];

interface Props {
  zone: ZoneState;
  feeds: FeedHealth[];
  now: number;
  loadDetail: (zoneId: string) => Promise<ZoneDetail>;
  onClose: () => void;
}

function Block({ title, tag, children }: { title: string; tag?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border-t px-4 py-3.5" style={{ borderColor: "var(--line)" }}>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <h3 className="label-caps">{title}</h3>
        {tag}
      </div>
      {children}
    </section>
  );
}

/**
 * Opens when a zone is clicked. First the story in plain words (what, evidence, possible
 * relationship, what to do); the analytical detail is one more click away.
 */
export function ZonePanel({ zone, feeds, now, loadDetail, onClose }: Props) {
  const fetcher = useCallback(() => loadDetail(zone.id), [loadDetail, zone.id]);
  const { data: detail } = usePolling(fetcher, 3000);
  const d = detail?.zone.id === zone.id ? detail : null;
  const [more, setMore] = useState(false);

  const links = [...zone.relationships].filter((r) => r.strength !== "weak").sort((a, b) => b.score - a.score);
  const lead = links[0];
  const advice = [...new Set(zone.risks.map((r) => r.resident_advice))];
  const StatusIcon = STATUS_META[zone.status].icon;

  return (
    <Drawer side="right" width="w-[440px]" title={zone.name}
      subtitle="Evidence from the last 10 minutes"
      icon={<StatusIcon size={19} className="mt-0.5" color={STATUS_META[zone.status].color} aria-hidden />} onClose={onClose}>
      <div className="px-4 pb-3.5 pt-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={zone.status} label={zone.status_label} size="lg" />
        </div>
        <p className="mt-2 text-[16px] font-semibold leading-snug">{zone.headline}</p>
      </div>

      <Block title="What's happening" tag={d ? <SourceTag by={d.explanation_by} /> : undefined}>
        <p className="text-[13.5px] leading-relaxed text-[#dbe4ee]">
          {d?.explanation?.whats_happening ?? (zone.status === "GREEN" ? "Everything in this zone is within its normal range for this time of day." : zone.headline)}
        </p>
      </Block>

      {zone.anomalies.length > 0 && (
        <Block title="Evidence" tag={<span className="text-[10.5px] text-[var(--faint)]">Measured</span>}>
          <ul className="space-y-1 text-[13px]">
            {zone.anomalies.slice(0, 5).map((a) => (
              <li key={a.id} className="flex gap-2">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: a.severity === "high" ? "var(--bad)" : "var(--warn)" }} aria-hidden />
                <span>{a.description}</span>
              </li>
            ))}
          </ul>
        </Block>
      )}

      {(lead || zone.insufficient_evidence.length > 0 || zone.cannot_assess.length > 0) && (
        <Block title="Possible relationship" tag={<span className="text-[10.5px] text-[#d8b4fe]">Not a confirmed cause</span>}>
          {lead ? (
            <div className="rounded-xl p-3" style={{ background: "rgba(192,132,252,0.08)", border: "1px solid rgba(192,132,252,0.3)" }}>
              <div className="flex items-center gap-2 text-[12px] font-semibold text-[#e9d5ff]">
                <Link2 size={14} aria-hidden /> {lead.title}
                <span className="ml-auto text-[11px]" style={{ color: STRENGTH_META[lead.strength].color }}>{STRENGTH_META[lead.strength].word}</span>
              </div>
              <p className="mt-1 text-[13px] leading-relaxed">{lead.statement}</p>
              <p className="mt-1.5 text-[11.5px] italic text-[var(--muted)]">{lead.caveat}</p>
              {links.length > 1 && <p className="mt-1 text-[11.5px] text-[var(--muted)]">+{links.length - 1} more possible link{links.length > 2 ? "s" : ""} — see the data below.</p>}
            </div>
          ) : null}
          {zone.insufficient_evidence.map((n) => (
            <p key={n} className="mt-2 flex gap-2 text-[12.5px] text-[var(--muted)]"><CircleHelp size={14} className="mt-0.5 shrink-0" aria-hidden />{n}</p>
          ))}
          {zone.cannot_assess.map((n) => (
            <p key={n} className="mt-2 flex gap-2 text-[12.5px] text-[var(--warn)]"><Info size={14} className="mt-0.5 shrink-0" aria-hidden />{n}</p>
          ))}
        </Block>
      )}

      {advice.length > 0 && (
        <Block title="For residents">
          <p className="flex gap-2 text-[13.5px] leading-relaxed"><Users size={15} className="mt-0.5 shrink-0 text-[var(--pulse)]" aria-hidden />{advice.join(" ")}</p>
        </Block>
      )}

      <div className="border-t px-4 py-2" style={{ borderColor: "var(--line)" }}>
        <button type="button" onClick={() => setMore(!more)} aria-expanded={more}
          className="flex w-full items-center justify-between rounded-lg px-1 py-1.5 text-[12.5px] font-semibold text-[var(--muted)] hover:text-[var(--text)]">
          {more ? "Hide the data" : "Show the data behind this"}
          <ChevronDown size={15} className={`transition-transform ${more ? "rotate-180" : ""}`} aria-hidden />
        </button>
      </div>

      {more && (
        <div className="cp-fade-in">
          <Block title="Signals now vs normal">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {CARD_ORDER.filter((k) => zone.metrics[k]).map((k) => <MetricCard key={k} m={zone.metrics[k]} series={d?.series[k]} />)}
            </div>
          </Block>
          {zone.relationships.length > 0 && (
            <Block title="Why these flags?">
              <div className="space-y-2">
                {zone.relationships.map((r, i) => <RelationshipCard key={r.id} rel={r} defaultOpen={i === 0 && r.strength !== "weak"} />)}
              </div>
            </Block>
          )}
          <Block title="Last 15 minutes" tag={<span className="text-[10.5px] text-[var(--faint)]">100 = normal</span>}>
            {d ? <SignalChart series={d.series} baselines={d.baselines} /> : <div className="h-56 animate-pulse rounded-lg bg-[var(--panel-2)]" />}
          </Block>
          <Block title="Recent civic reports" tag={<span className="text-[10.5px] text-[var(--faint)]">Anonymous</span>}>
            {zone.recent_incidents.length === 0 ? (
              <p className="text-[12.5px] text-[var(--muted)]">No reports in the last 10 minutes.</p>
            ) : (
              <ul className="space-y-1 text-[12.5px]">
                {zone.recent_incidents.slice(0, 8).map((i) => (
                  <li key={i.id} className="flex items-center gap-2">
                    <FileWarning size={13} className="text-[var(--muted)]" aria-hidden />{i.label}
                    <span className="ml-auto font-mono text-[11px] text-[var(--faint)]">{clockTime(i.timestamp)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Block>
          {d && d.agent_trace.length > 0 && (
            <Block title="Monitoring agent — last check">
              <ol className="space-y-0.5 text-[12px] text-[var(--muted)]">
                {d.agent_trace.map((line, i) => (
                  <li key={i} className="flex gap-2"><Bot size={12} className="mt-0.5 shrink-0 text-[var(--pulse)]" aria-hidden />{line}</li>
                ))}
              </ol>
            </Block>
          )}
          <Block title="Data sources">
            <ul className="space-y-1 text-[12px]">
              {feeds.map((f) => (
                <li key={f.id} className="flex items-center gap-2">
                  <span className="w-36 truncate text-[var(--muted)]">{f.label}</span>
                  <span className="font-semibold" style={{ color: isHealthyFeed(f.status) ? "var(--ok)" : "var(--warn)" }}>{f.status}</span>
                  <span className="ml-auto text-[var(--faint)]">{agoText(f.last_success_at, now)}</span>
                </li>
              ))}
            </ul>
          </Block>
        </div>
      )}
    </Drawer>
  );
}
