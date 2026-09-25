import {
  ArrowLeft, Bot, Bus, CarFront, ChevronDown, ChevronRight, CircleHelp, CloudRain, Droplets, FileWarning, Info, Link2, Users,
  Wind, Zap, type LucideIcon,
} from "lucide-react";
import { useCallback, useState } from "react";
import { usePolling } from "../../hooks/usePolling";
import type { FeedHealth, ZoneDetail, ZoneState } from "../../types";
import { agoText, clockTime } from "../../utils/format";
import { CHANCE_WORD, FORECAST_COLOR, isHealthyFeed, PREDICTION_ICON, STATUS_META, STRENGTH_META } from "../../utils/status";
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
  district?: string; // name of the district the block belongs to
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

// What a resident would notice, in everyday words (no numbers needed to get it).
const PLAIN: Record<string, { icon: LucideIcon; say: (dev: number | null) => string }> = {
  rain_mm_h: { icon: CloudRain, say: () => "Heavy rain" },
  congestion_pct: { icon: CarFront, say: (d) => `Traffic ${d !== null && d >= 60 ? "much heavier" : d !== null && d < 30 ? "a bit heavier" : "heavier"} than usual` },
  transit_delay_min: { icon: Bus, say: () => "Buses running late" },
  water_level_cm: { icon: Droplets, say: () => "Water on the streets" },
  waterlogging_reports: { icon: Droplets, say: () => "People reporting waterlogging" },
  outage_signal_reports: { icon: Zap, say: () => "Power cuts and signal failures reported" },
  accident_reports: { icon: CarFront, say: () => "Road accident reported" },
  aqi: { icon: Wind, say: () => "Air quality is poor" },
  incident_reports: { icon: FileWarning, say: () => "More complaints than usual" },
};

const SIMPLE_WORD = { GREEN: "All normal here", YELLOW: "Needs attention", RED: "Possible disruption" } as const;

/**
 * Opens when a block is clicked. First a 10-second answer — how is it, what would I notice,
 * what should I do — and one button for the full explanation with the evidence behind it.
 */
export function ZonePanel(props: Props) {
  const [detailed, setDetailed] = useState(false);
  return detailed ? <DetailedView {...props} onBack={() => setDetailed(false)} /> : <SimpleView {...props} onExplain={() => setDetailed(true)} />;
}

function SimpleView({ zone, district, onClose, onExplain }: Props & { onExplain: () => void }) {
  const meta = STATUS_META[zone.status];
  const StatusIcon = meta.icon;
  const seen = new Set<string>();
  const notice = zone.anomalies.filter((a) => PLAIN[a.metric] && !seen.has(PLAIN[a.metric].say(a.deviation_pct)) && seen.add(PLAIN[a.metric].say(a.deviation_pct))).slice(0, 3);
  const advice = [...new Set(zone.risks.map((r) => r.resident_advice))][0];
  return (
    <Drawer side="right" width="w-[360px]" title={zone.short_name}
      subtitle={`Block ${zone.id}${district ? ` · ${district} district` : ""} · Jaipur`}
      icon={<StatusIcon size={19} className="mt-0.5" color={meta.color} aria-hidden />} onClose={onClose}>
      <div className="space-y-4 p-4">
        <div className="rounded-2xl px-4 py-3.5" style={{ background: `color-mix(in srgb, ${meta.color} 12%, transparent)`, border: `1px solid color-mix(in srgb, ${meta.color} 40%, transparent)` }}>
          <div className="flex items-center gap-2 text-[19px] font-bold" style={{ color: meta.color }}>
            <StatusIcon size={22} aria-hidden /> {SIMPLE_WORD[zone.status]}
          </div>
          <p className="mt-1 text-[14px] leading-snug text-[#e2e8f0]">
            {zone.status === "GREEN" ? "Nothing unusual right now." : zone.headline}
          </p>
        </div>

        {notice.length > 0 && (
          <div>
            <h3 className="label-caps mb-2">What you'd notice</h3>
            <ul className="space-y-2">
              {notice.map((a) => {
                const { icon: Icon, say } = PLAIN[a.metric];
                return (
                  <li key={a.id} className="flex items-center gap-3 text-[15px]">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg" style={{ background: "rgba(255,255,255,0.06)" }}>
                      <Icon size={17} color={a.severity === "high" ? "var(--bad)" : "var(--warn)"} aria-hidden />
                    </span>
                    {say(a.deviation_pct)}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {zone.predictions?.length > 0 && (
          <div>
            <h3 className="label-caps mb-2" style={{ color: FORECAST_COLOR }}>What may happen next</h3>
            <ul className="space-y-2">
              {zone.predictions.slice(0, 3).map((p) => {
                const Icon = PREDICTION_ICON[p.kind];
                return (
                  <li key={p.kind} className="flex items-center gap-3">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg" style={{ border: `1px dashed ${FORECAST_COLOR}` }}>
                      <Icon size={16} color={FORECAST_COLOR} aria-hidden />
                    </span>
                    <span className="leading-tight">
                      <span className="block text-[15px]">{p.label}</span>
                      <span className="text-[12px] text-[var(--muted)]">{CHANCE_WORD[p.likelihood]} · {p.horizon}</span>
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <div>
          <h3 className="label-caps mb-1.5">What to do</h3>
          <p className="flex gap-2 text-[15px] leading-snug">
            <Users size={17} className="mt-0.5 shrink-0 text-[var(--pulse)]" aria-hidden />
            {advice ?? (zone.predictions?.some((p) => p.likelihood !== "low")
              ? "Nothing yet — but be prepared: conditions nearby may reach this block soon."
              : zone.status === "GREEN" ? "No action needed." : "Nothing to do yet — CityPulse is keeping an eye on it.")}
          </p>
        </div>

        <button type="button" onClick={onExplain}
          className="flex w-full items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-[13.5px] font-semibold hover:bg-white/10"
          style={{ border: "1px solid var(--line)", background: "rgba(255,255,255,0.04)" }}>
          Explain in detail <ChevronRight size={16} aria-hidden />
        </button>
      </div>
    </Drawer>
  );
}

function DetailedView({ zone, feeds, now, loadDetail, onClose, onBack }: Props & { onBack: () => void }) {
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
      subtitle="The full explanation · evidence from the last 10 minutes"
      icon={<StatusIcon size={19} className="mt-0.5" color={STATUS_META[zone.status].color} aria-hidden />} onClose={onClose}>
      <div className="px-4 pt-3">
        <button type="button" onClick={onBack}
          className="flex items-center gap-1 text-[12.5px] font-semibold text-[var(--muted)] hover:text-[var(--text)]">
          <ArrowLeft size={14} aria-hidden /> Back to the simple view
        </button>
      </div>
      <div className="px-4 pb-3.5 pt-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={zone.status} label={zone.status_label} size="lg" />
        </div>
        <p className="mt-2 text-[16px] font-semibold leading-snug">{zone.headline}</p>
      </div>

      <Block title="What's happening" tag={d ? <SourceTag by={d.explanation_by} /> : undefined}>
        <p className="text-[13.5px] leading-relaxed text-[#dbe4ee]">
          {d?.explanation?.whats_happening ?? (zone.status === "GREEN" ? "Everything in this block is within its normal range for this time of day." : zone.headline)}
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

      {zone.predictions?.length > 0 && (
        <Block title="What may happen next" tag={<span className="text-[10.5px]" style={{ color: FORECAST_COLOR }}>Forecast · not certain</span>}>
          <ul className="space-y-2 text-[13px]">
            {zone.predictions.map((p) => {
              const Icon = PREDICTION_ICON[p.kind];
              return (
                <li key={p.kind} className="flex gap-2.5">
                  <Icon size={15} className="mt-0.5 shrink-0" color={FORECAST_COLOR} aria-hidden />
                  <span>
                    <span className="font-semibold">{p.label}</span>
                    <span className="text-[var(--muted)]"> — {CHANCE_WORD[p.likelihood].toLowerCase()}, {p.horizon}</span>
                    <span className="block text-[12px] text-[var(--muted)]">{p.reason}</span>
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="mt-2 text-[11.5px] italic text-[var(--muted)]">
            Based on how these situations usually develop — a possibility, not a certainty.
          </p>
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
