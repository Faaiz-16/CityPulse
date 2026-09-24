import type { PulseInfo } from "../types";
import { STATUS_META } from "../utils/status";

const BEAT_W = 64;
const BEATS = 8;
// One heartbeat: flat, small bump, sharp spike, dip, recovery, flat.
const BEAT = "l14 0 l4 -4 l4 4 l6 0 l3 -18 l4 30 l3 -16 l4 4 l3 -5 l3 5 l16 0";

/**
 * The city's "pulse". Its rhythm and colour are data, not decoration:
 *  - colour = worst zone status (green / amber / red)
 *  - speed  = beats per minute, which rise with the number of active anomalies
 *    and zones in possible disruption (computed by the backend).
 */
export function PulseStrip({ pulse }: { pulse: PulseInfo }) {
  const meta = STATUS_META[pulse.city_status];
  const beatSeconds = 60 / pulse.bpm;
  const d = `M0 20 ${Array.from({ length: BEATS + 2 }, () => BEAT).join(" ")}`;
  const { RED = 0, YELLOW = 0 } = pulse.zones_by_status;
  const text =
    RED + YELLOW === 0
      ? "Steady — all zones normal"
      : [RED && `${RED} possible disruption`, YELLOW && `${YELLOW} need attention`].filter(Boolean).join(" · ");

  return (
    <div
      className="flex items-center gap-3 rounded-xl px-3 py-1.5"
      style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}
      role="img"
      aria-label={`City pulse: ${meta.word}. ${text}. ${pulse.bpm} beats per minute.`}
    >
      <div className="relative h-8 w-40 overflow-hidden sm:w-48" aria-hidden>
        <svg
          className="cp-pulse-line absolute left-0 top-0 h-8"
          width={BEAT_W * (BEATS + 2)}
          viewBox={`0 0 ${BEAT_W * (BEATS + 2)} 40`}
          style={{ animation: `cp-scroll ${beatSeconds}s linear infinite` }}
        >
          <path d={d} fill="none" stroke={meta.color} strokeWidth="2.2" strokeLinejoin="round" />
        </svg>
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: "linear-gradient(90deg, var(--panel-2), transparent 25%, transparent 75%, var(--panel-2))" }}
        />
        <style>{`@keyframes cp-scroll { from { transform: translateX(0) } to { transform: translateX(-${BEAT_W}px) } }`}</style>
      </div>
      <div className="leading-tight">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold" style={{ color: meta.color }}>
            {meta.word === "Normal" ? "City normal" : meta.word}
          </span>
          <span className="font-mono text-[11px] text-[var(--faint)]">{pulse.bpm} bpm</span>
        </div>
        <div className="text-[11px] text-[var(--muted)]">{text}</div>
      </div>
    </div>
  );
}
