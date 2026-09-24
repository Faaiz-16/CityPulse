import { Activity, BarChart3, Database, FlaskConical, Heart, History } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { CityState } from "../types";
import { feedWord } from "../utils/alerts";
import { agoText, clockTime } from "../utils/format";
import { FEED_META, isHealthyFeed, STATUS_META } from "../utils/status";

export type Mode = "LIVE" | "DEMO" | "REPLAY";

const MODE_META: Record<Mode, { color: string; hint: string }> = {
  LIVE: { color: "var(--ok)", hint: "Live pipeline" },
  DEMO: { color: "var(--pulse)", hint: "Controlled scenario running" },
  REPLAY: { color: "var(--link)", hint: "Recorded data — not live" },
};

interface Props {
  state: CityState;
  now: number;
  mode: Mode;
  offline: boolean;
  demoOpen: boolean;
  insightsOpen: boolean;
  onDemo: () => void;
  onInsights: () => void;
  onReplay: () => void;
}

/** A single slim bar: identity, the city's pulse, mode, data health and three entry points. */
export function Header({ state, now, mode, offline, demoOpen, insightsOpen, onDemo, onInsights, onReplay }: Props) {
  return (
    <header className="glass pointer-events-auto flex items-center gap-2 px-2 py-2 sm:gap-4 sm:px-3">
      <div className="flex items-center gap-2.5">
        <div className="grid h-8 w-8 place-items-center rounded-lg" style={{ background: "rgba(45,212,191,0.14)" }}>
          <Activity size={18} color="var(--pulse)" strokeWidth={2.6} aria-hidden />
        </div>
        <div className="leading-tight">
          <h1 className="sr-only text-[15px] font-bold tracking-tight sm:not-sr-only">CityPulse</h1>
          <p className="hidden text-[11px] text-[var(--muted)] xl:block">Understand what&apos;s happening in your city — at a glance.</p>
        </div>
      </div>

      <PulseChip state={state} />

      <div className="ml-auto flex items-center gap-2">
        <ModeClock mode={mode} state={state} offline={offline} />
        {mode !== "REPLAY" && <div className="hidden sm:block"><DataHealth state={state} now={now} /></div>}
        <div className="mx-0.5 hidden h-6 w-px bg-[var(--line)] sm:block" aria-hidden />
        <HeaderButton icon={BarChart3} label="Insights" active={insightsOpen} onClick={onInsights} />
        {mode !== "REPLAY" && <HeaderButton icon={History} label="Replay" onClick={onReplay} />}
        {mode !== "REPLAY" && <HeaderButton icon={FlaskConical} label="Demo" active={demoOpen} accent onClick={onDemo} />}
      </div>
    </header>
  );
}

/** Heart that beats at the city's pulse: colour = worst zone, rhythm = how much is unusual. */
function PulseChip({ state }: { state: CityState }) {
  const meta = STATUS_META[state.pulse.city_status];
  const word = state.pulse.city_status === "GREEN" ? "City normal" : meta.word;
  const { RED = 0, YELLOW = 0 } = state.pulse.zones_by_status;
  const detail = RED + YELLOW === 0 ? "All zones normal"
    : [RED && `${RED} zone${RED > 1 ? "s" : ""} disrupted`, YELLOW && `${YELLOW} need${YELLOW > 1 ? "" : "s"} attention`].filter(Boolean).join(" · ");
  return (
    <div className="flex items-center gap-2.5 rounded-xl px-2.5 py-1" style={{ background: `color-mix(in srgb, ${meta.color} 10%, transparent)` }}
      role="status" aria-label={`City pulse: ${word}. ${detail}. ${state.pulse.bpm} beats per minute.`}>
      <Heart size={18} color={meta.color} fill={meta.color} className="cp-heart" style={{ animationDuration: `${60 / state.pulse.bpm}s` }} aria-hidden />
      <div className="leading-tight">
        <div className="flex items-baseline gap-2">
          <span className="text-[13px] font-semibold" style={{ color: meta.color }}>{word}</span>
          <span className="hidden font-mono text-[11px] text-[var(--faint)] sm:inline">{state.pulse.bpm} bpm</span>
        </div>
        <div className="hidden text-[11px] text-[var(--muted)] sm:block">{detail}</div>
      </div>
    </div>
  );
}

function ModeClock({ mode, state, offline }: { mode: Mode; state: CityState; offline: boolean }) {
  const meta = MODE_META[mode];
  const color = offline ? "var(--bad)" : meta.color;
  return (
    <div className="flex items-center gap-2 rounded-lg px-2 py-1" title={offline ? "Connection lost — showing the last update" : meta.hint}>
      <span className="relative flex h-2 w-2" aria-hidden>
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-50" style={{ background: color }} />
        <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: color }} />
      </span>
      <span className="hidden text-[11px] font-bold tracking-wider min-[420px]:inline" style={{ color }}>{offline ? "OFFLINE" : mode}</span>
      <span className="hidden font-mono text-[12px] text-[#cbd5e1] sm:inline">{clockTime(state.generated_at)}</span>
    </div>
  );
}

/** One chip for all feeds; the details open on click. */
function DataHealth({ state, now }: { state: CityState; now: number }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const bad = state.feeds.filter((f) => !isHealthyFeed(f.status));
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);
  const color = bad.length ? FEED_META[bad[0].status].color : "var(--ok)";
  const simulated = state.feeds.every((f) => f.status !== "LIVE");
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11.5px] hover:bg-white/5"
        style={{ border: `1px solid ${bad.length ? color : "var(--line)"}` }}>
        <Database size={13} color={color} aria-hidden />
        <span className="hidden font-medium lg:inline" style={{ color: bad.length ? color : "var(--muted)" }}>
          {bad.length ? `${bad[0].label} ${feedWord(bad[0].status)}${bad.length > 1 ? ` +${bad.length - 1}` : ""}` : `Data OK${simulated ? " · demo city" : ""}`}
        </span>
      </button>
      {open && (
        <div className="glass-strong cp-fade-in absolute right-0 top-full z-[1300] mt-2 w-72 rounded-xl p-3 text-[12px] shadow-2xl" role="dialog" aria-label="Data feeds">
          <div className="label-caps mb-2">Data feeds</div>
          <ul className="space-y-1.5">
            {state.feeds.map((f) => (
              <li key={f.id} className="flex items-center gap-2" title={f.message}>
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: FEED_META[f.status].color }} aria-hidden />
                <span className="flex-1 truncate">{f.label}</span>
                <span className="font-semibold" style={{ color: FEED_META[f.status].color }}>{f.status}</span>
                <span className="w-14 text-right text-[var(--faint)]">{agoText(f.last_success_at, now)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2.5 border-t pt-2 text-[11px] leading-snug text-[var(--muted)]" style={{ borderColor: "var(--line)" }}>
            {simulated ? "Feeds come from the demonstration city simulation, labelled SIMULATED — never presented as live." : "LIVE feeds come from public APIs."}
            {" "}Summaries: {state.config.ai_enabled ? "AI-assisted, fact-checked" : "rule-based"}.
          </p>
        </div>
      )}
    </div>
  );
}

function HeaderButton({ icon: Icon, label, onClick, active, accent }: {
  icon: typeof Activity; label: string; onClick: () => void; active?: boolean; accent?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active}
      className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12px] font-semibold transition-colors hover:bg-white/10 sm:px-2.5"
      style={{
        background: active ? "rgba(255,255,255,0.1)" : accent ? "rgba(45,212,191,0.14)" : "transparent",
        color: accent ? "var(--pulse)" : "var(--text)",
      }}>
      <Icon size={15} aria-hidden />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}
