import { Activity } from "lucide-react";
import type { CityState } from "../types";
import { agoText, clockTime } from "../utils/format";
import { FeedHealthBar } from "./FeedHealthBar";
import { PulseStrip } from "./PulseStrip";

interface Props {
  state: CityState;
  now: number;
  connectionError: string | null;
}

export function TopBar({ state, now, connectionError }: Props) {
  const stale = now - new Date(state.generated_at).getTime() > 15000;
  return (
    <header
      className="relative z-[1100] flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-4 py-2.5"
      style={{ borderColor: "var(--line)", background: "var(--panel)" }}
    >
      <div className="flex items-center gap-2.5">
        <div
          className="grid h-9 w-9 place-items-center rounded-xl"
          style={{ background: "color-mix(in srgb, var(--pulse) 15%, transparent)" }}
        >
          <Activity size={20} color="var(--pulse)" strokeWidth={2.5} aria-hidden />
        </div>
        <div className="leading-tight">
          <h1 className="text-lg font-bold tracking-tight">CityPulse</h1>
          <p className="hidden text-[11px] text-[var(--muted)] md:block">
            Understand what&apos;s happening in your city — at a glance.
          </p>
        </div>
      </div>

      <PulseStrip pulse={state.pulse} />

      <div className="ml-auto flex flex-wrap items-center gap-3">
        <FeedHealthBar feeds={state.feeds} now={now} />
        <div className="text-right leading-tight" aria-live="polite">
          <div className="flex items-center justify-end gap-1.5 text-xs">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: connectionError || stale ? "var(--bad)" : "var(--ok)" }}
              aria-hidden
            />
            <span className="font-semibold">{connectionError ? "Offline" : "Live"}</span>
            <span className="font-mono text-[var(--muted)]">{clockTime(state.generated_at)}</span>
          </div>
          <div className="text-[11px] text-[var(--muted)]">Updated {agoText(state.generated_at, now)}</div>
        </div>
      </div>
    </header>
  );
}
