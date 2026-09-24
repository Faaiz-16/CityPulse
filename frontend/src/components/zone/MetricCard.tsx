import { ArrowDownRight, ArrowRight, ArrowUpRight, Minus } from "lucide-react";
import { Line, LineChart, ReferenceLine, ResponsiveContainer, YAxis } from "recharts";
import type { MetricAssessment, SeriesPoint } from "../../types";
import { num, pct, withUnit } from "../../utils/format";
import { METRIC_ICONS, SEVERITY_META } from "../../utils/status";

const TREND = {
  rising: { icon: ArrowUpRight, word: "rising" },
  falling: { icon: ArrowDownRight, word: "falling" },
  steady: { icon: ArrowRight, word: "steady" },
  unknown: { icon: Minus, word: "—" },
};

export function MetricCard({ m, series }: { m: MetricAssessment; series?: SeriesPoint[] }) {
  const Icon = METRIC_ICONS[m.metric];
  const sev = SEVERITY_META[m.severity];
  const T = TREND[m.trend];
  const accent = m.is_anomaly ? sev.color : "var(--line)";
  const absolute = ["rain_mm_h", "water_level_cm"].includes(m.metric);
  const reports = m.source === "incidents";

  return (
    <div
      className="rounded-xl p-3"
      style={{ background: "var(--panel-2)", border: `1px solid ${accent}`, boxShadow: m.is_anomaly ? `inset 3px 0 0 ${sev.color}` : undefined }}
    >
      <div className="flex items-center gap-1.5 text-[11.5px] text-[var(--muted)]" title={`Anomaly rule: ${m.threshold}`}>
        {Icon && <Icon size={13} className="shrink-0" aria-hidden />}
        <span className="leading-tight">{m.label}</span>
      </div>

      {!m.available ? (
        <div className="mt-2 text-[12px] text-[var(--warn)]">No current data — feed unavailable. Not assessed.</div>
      ) : (
        <>
          <div className="mt-1 flex items-end justify-between gap-2">
            <div>
              <div className="text-[22px] font-semibold leading-none tracking-tight">
                {reports ? num(m.current, 0) : withUnit(m.current, m.unit)}
                {reports && <span className="ml-1 text-[11px] font-normal text-[var(--muted)]">in window</span>}
              </div>
              <div className="mt-1 text-[11px] text-[var(--muted)]">
                {absolute ? (
                  <>Flag rule: {m.threshold}</>
                ) : (
                  <>
                    {reports ? `Usually ≈ ${num(m.baseline)} in 10 min` : `Normal ${withUnit(m.baseline, m.unit)}`}
                    {m.deviation_pct !== null && !reports && (
                      <span className="ml-1.5 font-semibold" style={{ color: m.is_anomaly ? sev.color : "var(--text)" }}>
                        {pct(m.deviation_pct)}
                      </span>
                    )}
                  </>
                )}
              </div>
            </div>
            {series && series.some((p) => p.v !== null) && (
              <div className="h-9 w-24" aria-hidden>
                <ResponsiveContainer>
                  <LineChart data={series}>
                    <YAxis hide domain={["auto", "auto"]} />
                    {m.baseline !== null && !absolute && <ReferenceLine y={m.baseline} stroke="#64748b" strokeDasharray="2 3" />}
                    <Line type="monotone" dataKey="v" stroke={m.is_anomaly ? sev.color : "#7dd3fc"} strokeWidth={1.6} dot={false} isAnimationActive={false} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
          <div className="mt-1.5 flex items-center justify-between gap-2 text-[10.5px] text-[var(--faint)]">
            <span className="flex items-center gap-0.5">
              <T.icon size={11} aria-hidden /> {T.word}
            </span>
            {m.is_anomaly ? (
              <span className="rounded px-1.5 py-px text-[10px] font-semibold" style={{ color: sev.color, background: `color-mix(in srgb, ${sev.color} 14%, transparent)` }}>
                {sev.word}
              </span>
            ) : (
              <span>within normal range</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
