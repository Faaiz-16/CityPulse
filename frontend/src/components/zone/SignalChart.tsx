import { Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SeriesPoint } from "../../types";
import { clockTime } from "../../utils/format";

interface Props {
  series: Record<string, SeriesPoint[]>;
  baselines: Record<string, number | null>;
}

const LINES = [
  { key: "congestion_pct", name: "Traffic", color: "#fbbf24" },
  { key: "transit_delay_min", name: "Bus delays", color: "#fb923c" },
  { key: "aqi", name: "Air quality (AQI)", color: "#c084fc" },
];

/**
 * All signals on one time axis. Lines are indexed so 100 = normal for this time of day,
 * which lets very different units (%, minutes, AQI) be compared; rain is shown as bars.
 */
export function SignalChart({ series, baselines }: Props) {
  const base = series.rain_mm_h ?? [];
  const data = base.map((p, i) => {
    const row: Record<string, number | string | null> = { t: p.t, rain: p.v };
    for (const l of LINES) {
      const v = series[l.key]?.[i]?.v;
      const b = baselines[l.key];
      row[l.key] = v !== null && v !== undefined && b ? Math.round((v / b) * 100) : null;
    }
    return row;
  });

  return (
    <div className="h-56 w-full" role="img" aria-label="Chart of rainfall and traffic, bus delay and air-quality indices over the last 15 minutes">
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="#1a2430" vertical={false} />
          <XAxis dataKey="t" tickFormatter={(t) => clockTime(t, false)} tick={{ fill: "#64748b", fontSize: 10 }} minTickGap={40} stroke="#233040" />
          <YAxis yAxisId="idx" tick={{ fill: "#64748b", fontSize: 10 }} stroke="#233040" domain={[0, (max: number) => Math.max(200, Math.ceil(max / 50) * 50)]} />
          <YAxis yAxisId="rain" orientation="right" tick={{ fill: "#60a5fa", fontSize: 10 }} stroke="#233040" domain={[0, (max: number) => Math.max(10, Math.ceil(max))]} />
          <ReferenceLine yAxisId="idx" y={100} stroke="#93a1b2" strokeDasharray="4 4" label={{ value: "normal", fill: "#93a1b2", fontSize: 10, position: "insideTopLeft" }} />
          <Tooltip
            contentStyle={{ background: "#16202b", border: "1px solid #233040", borderRadius: 8, fontSize: 12 }}
            labelFormatter={(t) => clockTime(String(t))}
            formatter={(v, name) => (name === "Rain (mm/h)" ? [`${v} mm/h`, name] : [`${v} (100 = normal)`, name])}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} iconSize={9} />
          <Bar yAxisId="rain" dataKey="rain" name="Rain (mm/h)" fill="#60a5fa" fillOpacity={0.45} isAnimationActive={false} />
          {LINES.map((l) => (
            <Line key={l.key} yAxisId="idx" type="monotone" dataKey={l.key} name={l.name} stroke={l.color} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
