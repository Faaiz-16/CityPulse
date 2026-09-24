import {
  CarFront, CheckCircle2, ChevronDown, Circle, CloudLightning, CloudRain, FlaskConical, History, Layers, Loader2, Pause, Play,
  RotateCcw, SlidersHorizontal, Waves, Wind, Zap, Database, Clapperboard, type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../services/api";
import type { FeedHealth, ScenarioPreset, SimulationStatus, ZoneState } from "../../types";
import { FEED_META, STATUS_META } from "../../utils/status";
import { Drawer } from "./Drawer";

export const PRESET_ICONS: Record<string, LucideIcon> = {
  rain: CloudRain, water: Waves, traffic: CarFront, accident: CarFront, outage: Zap, air: Wind, storm: CloudLightning, multi: Layers,
};
const SEVERITY_COLOR = { high: "#f87171", moderate: "#fbbf24", low: "#94a3b8" };

type Tab = "scenarios" | "custom" | "feeds";

interface Props {
  sim: SimulationStatus;
  zones: ZoneState[];
  feeds: FeedHealth[];
  onClose: () => void;
  onChanged: () => void;
  onStartReplay: () => void;
  onShow: (zoneId: string | null) => void; // a situation is ready: show it on the map
  districtNames: Record<string, string>; // "C2" → "Walled City"
}

/** Everything needed to *create* a situation: scenarios, custom sliders, feed failures. */
export function DemoDrawer({ sim, zones, feeds, onClose, onChanged, onStartReplay, onShow, districtNames }: Props) {
  const [tab, setTab] = useState<Tab>("scenarios");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);

  async function act(fn: () => Promise<{ message: string }>, label = "Working…"): Promise<unknown> {
    setBusy(label);
    try {
      setMessage({ text: (await fn()).message });
      onChanged();
      return true;
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : "Request failed", error: true });
      return false;
    } finally {
      setBusy(null);
    }
  }

  const tabs: { id: Tab; label: string; icon: LucideIcon }[] = [
    { id: "scenarios", label: "Situations", icon: Clapperboard },
    { id: "custom", label: "Custom", icon: SlidersHorizontal },
    { id: "feeds", label: "Feed failures", icon: Database },
  ];

  return (
    <Drawer side="left" title="Demo" subtitle="Pick a situation — it appears on the map right away."
      icon={<FlaskConical size={18} className="mt-0.5 text-[var(--pulse)]" aria-hidden />} onClose={onClose}>
      <div className="flex gap-1 border-b px-3 pt-2" style={{ borderColor: "var(--line)" }} role="tablist">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
            className="flex items-center gap-1.5 border-b-2 px-2.5 pb-2 pt-1 text-[12.5px] font-semibold"
            style={{ borderColor: tab === id ? "var(--pulse)" : "transparent", color: tab === id ? "var(--text)" : "var(--faint)" }}>
            <Icon size={14} aria-hidden /> {label}
          </button>
        ))}
      </div>

      <div className="space-y-4 p-4">
        {tab === "scenarios" && <ScenariosTab sim={sim} zones={zones} busy={busy} act={act} onStartReplay={onStartReplay} onShow={onShow} />}
        {tab === "custom" && <CustomTab sim={sim} zones={zones} districtNames={districtNames} busy={!!busy} act={act} onShow={onShow} />}
        {tab === "feeds" && <FeedsTab feeds={feeds} busy={!!busy} act={act} />}
        {busy && (
          <p className="flex items-center gap-2 text-[12.5px] text-[var(--pulse)]" role="status">
            <Loader2 size={14} className="animate-spin" aria-hidden /> {busy}
          </p>
        )}
        {message && !busy && (
          <p className="text-[12px]" role="status" style={{ color: message.error ? "var(--bad)" : "var(--muted)" }}>{message.text}</p>
        )}
      </div>
    </Drawer>
  );
}

type Act = (fn: () => Promise<{ message: string }>, label?: string) => Promise<unknown>;

// ------------------------------------------------------------------ scenarios

function ScenariosTab({ sim, zones, busy, act, onStartReplay, onShow }: {
  sim: SimulationStatus; zones: ZoneState[]; busy: string | null; act: Act; onStartReplay: () => void; onShow: (id: string | null) => void;
}) {
  const [stepByStep, setStepByStep] = useState(false);
  const run = async (p: ScenarioPreset) => {
    const label = stepByStep ? `Starting ${p.name}…` : `Setting up ${p.name} in ${p.place}…`;
    if (await act(() => api.runScenario(p.id, !stepByStep), label)) onShow(p.zone_id);
  };
  return (
    <>
      {sim.scenario && <NowShowing sim={sim} zones={zones} busy={!!busy} act={act} />}

      <div>
        <h3 className="label-caps mb-2">Choose a situation</h3>
        <div className="grid grid-cols-2 gap-2">
          <button type="button" disabled={!!busy} onClick={async () => { if (await act(api.reset, "Back to normal…")) onShow(null); }}
            className="flex flex-col items-start gap-1 rounded-xl p-2.5 text-left hover:bg-white/5 disabled:opacity-50"
            style={{ border: "1px solid var(--line)" }}>
            <CheckCircle2 size={18} color="var(--ok)" aria-hidden />
            <span className="text-[13px] font-semibold leading-tight">Normal city</span>
            <span className="text-[11px] text-[var(--muted)]">Clear everything</span>
          </button>
          {sim.presets.map((p) => {
            const Icon = PRESET_ICONS[p.icon] ?? CloudRain;
            const active = sim.scenario?.id === p.id;
            return (
              <button key={p.id} type="button" disabled={!!busy} onClick={() => run(p)} title={p.tagline}
                className="flex flex-col items-start gap-1 rounded-xl p-2.5 text-left hover:bg-white/5 disabled:opacity-50"
                style={{ border: `1px solid ${active ? "rgba(45,212,191,0.6)" : "var(--line)"}`, background: active ? "rgba(45,212,191,0.07)" : undefined }}>
                <span className="flex w-full items-center justify-between">
                  <Icon size={18} color={active ? "var(--pulse)" : "var(--muted)"} aria-hidden />
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: SEVERITY_COLOR[p.severity] }} title={`${p.severity} severity`} />
                </span>
                <span className="text-[13px] font-semibold leading-tight">{p.name}</span>
                <span className="text-[11px] text-[var(--muted)]">{p.place}</span>
              </button>
            );
          })}
        </div>
        <label className="mt-3 flex cursor-pointer items-center gap-2 text-[12px] text-[var(--muted)]">
          <input type="checkbox" checked={stepByStep} onChange={(e) => setStepByStep(e.target.checked)} className="cp-range" />
          Play step by step instead (watch it build up over ~2 minutes)
        </label>
      </div>

      <button type="button" onClick={onStartReplay}
        className="flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2 text-[12.5px] font-semibold"
        style={{ border: "1px solid #c084fc55", background: "rgba(192,132,252,0.08)", color: "#e9d5ff" }}>
        <History size={14} aria-hidden /> Replay a recorded storm (past data)
      </button>
    </>
  );
}

/** What's on the map now, and — on request — how CityPulse detected it, step by step. */
function NowShowing({ sim, zones, busy, act }: { sim: SimulationStatus; zones: ZoneState[]; busy: boolean; act: Act }) {
  const [open, setOpen] = useState(false);
  const sc = sim.scenario!;
  const focus = zones.find((z) => z.id === sc.focus_zone);
  const stages = [...sc.stages].sort((a, b) => {
    if (a.reached_at && b.reached_at) return a.reached_at.localeCompare(b.reached_at);
    if (a.reached_at) return -1;
    if (b.reached_at) return 1;
    return (a.expected_at_s ?? 0) - (b.expected_at_s ?? 0);
  });
  const done = sc.stages.filter((s) => s.reached_at).length;
  return (
    <section className="rounded-xl p-3" style={{ background: "rgba(45,212,191,0.07)", border: "1px solid rgba(45,212,191,0.35)" }} aria-label="Current situation">
      <div className="label-caps" style={{ color: "var(--pulse)" }}>{sim.clock.paused ? "Paused" : "Now showing"}</div>
      <div className="mt-0.5 text-[15px] font-semibold">{sc.name}</div>
      {focus && (
        <p className="mt-1 text-[12.5px]">
          <span className="font-semibold" style={{ color: STATUS_META[focus.status].color }}>{focus.short_name}: {focus.status_label}</span>
          <span className="text-[var(--muted)]"> — {focus.headline}</span>
        </p>
      )}

      {!sc.complete && <PlaybackControls sim={sim} busy={busy} act={act} />}

      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="mt-2.5 flex w-full items-center justify-between text-[12px] font-semibold text-[var(--muted)] hover:text-[var(--text)]">
        How CityPulse detected it ({done}/{sc.stages.length})
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {open && (
        <ol className="cp-fade-in mt-1.5 space-y-1 text-[12.5px]">
          {stages.map((s) => (
            <li key={s.key} className="flex items-center gap-2">
              {s.reached_at ? <CheckCircle2 size={14} color="var(--ok)" aria-label="detected" /> : <Circle size={14} className="text-[var(--faint)]" aria-label="waiting" />}
              <span className={s.reached_at ? "" : "text-[var(--faint)]"}>{s.label}</span>
              <span className="ml-auto font-mono text-[10.5px] text-[var(--faint)]">
                {s.reached_at ? `after ${s.t_plus_s ?? "?"} s` : "waiting"}
              </span>
            </li>
          ))}
          <li className="pt-1 text-[10.5px] text-[var(--faint)]">Each step is ticked only when the analysis actually detected it.</li>
        </ol>
      )}
    </section>
  );
}

export function PlaybackControls({ sim, busy, act, compact = false }: { sim: SimulationStatus; busy: boolean; act: Act; compact?: boolean }) {
  const paused = sim.clock.paused;
  return (
    <div className={`flex items-center gap-1.5 ${compact ? "" : "mt-2.5"}`}>
      <button type="button" disabled={busy} onClick={() => act(() => api.playback(paused ? "resume" : "pause"))}
        className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12px] font-semibold hover:bg-white/10 disabled:opacity-50"
        style={{ border: "1px solid var(--line)" }} aria-label={paused ? "Resume" : "Pause"}>
        {paused ? <Play size={13} aria-hidden /> : <Pause size={13} aria-hidden />}
        {!compact && (paused ? "Resume" : "Pause")}
      </button>
      <div className="flex rounded-lg p-0.5" style={{ border: "1px solid var(--line)" }} role="group" aria-label="Scenario speed">
        {[1, 2, 4].map((s) => (
          <button key={s} type="button" disabled={busy} aria-pressed={sim.clock.speed === s}
            onClick={() => act(() => api.playback("speed", s))}
            className="rounded-md px-2 py-1 text-[11px] font-semibold disabled:opacity-50"
            style={{ background: sim.clock.speed === s ? "rgba(255,255,255,0.1)" : "transparent", color: sim.clock.speed === s ? "var(--text)" : "var(--faint)" }}>
            {s}×
          </button>
        ))}
      </div>
      {!compact && (
        <button type="button" disabled={busy} onClick={() => act(api.reset)}
          className="ml-auto flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12px] font-semibold hover:bg-white/10 disabled:opacity-50"
          style={{ border: "1px solid var(--line)" }}>
          <RotateCcw size={13} aria-hidden /> Reset
        </button>
      )}
    </div>
  );
}

// --------------------------------------------------------------------- custom

const CONTROL_LABELS: Record<string, { label: string; icon: LucideIcon }> = {
  rain: { label: "Rainfall", icon: CloudRain },
  flooding: { label: "Street flooding", icon: Waves },
  traffic: { label: "Traffic congestion", icon: CarFront },
  accident: { label: "Road accident", icon: CarFront },
  outage: { label: "Power outage", icon: Zap },
  air: { label: "Air pollution", icon: Wind },
};

function levelWord(v: number) {
  if (v <= 0) return "Off";
  if (v < 0.5) return "Light";
  if (v < 1) return "Moderate";
  if (v < 1.3) return "Heavy";
  return "Extreme";
}

function CustomTab({ sim, zones, districtNames, busy, act, onShow }: {
  sim: SimulationStatus; zones: ZoneState[]; districtNames: Record<string, string>; busy: boolean; act: Act; onShow: (id: string | null) => void;
}) {
  const [zone, setZone] = useState(sim.custom?.zone_id ?? "C2-9");
  const [duration, setDuration] = useState(sim.custom?.duration_s ?? 600);
  const [values, setValues] = useState<Record<string, number>>(
    () => Object.fromEntries(sim.custom_controls.map((c) => [c, sim.custom?.values[c] ?? 0])),
  );
  useEffect(() => {
    if (sim.custom) setValues((v) => ({ ...v, ...sim.custom!.values }));
  }, [sim.custom]);
  const any = Object.values(values).some((v) => v > 0);
  // Blocks grouped by district (A1 … E5), keypad order inside each.
  const districts = [...new Set(zones.map((z) => z.id.slice(0, 2)))].sort((a, b) => a[1].localeCompare(b[1]) || a[0].localeCompare(b[0]));
  return (
    <>
      <p className="text-[12px] text-[var(--muted)]">
        Set conditions around one block. The simulated feeds change and build up over a minute or two; CityPulse has to
        notice and connect them itself.
      </p>
      <label className="flex items-center justify-between gap-2 text-[12.5px]">
        <span className="font-semibold">Block</span>
        <select value={zone} onChange={(e) => setZone(e.target.value)} className="max-w-[230px] rounded-lg px-2 py-1.5 text-[12.5px]"
          style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}>
          {districts.map((d) => (
            <optgroup key={d} label={`District ${d}${districtNames[d] ? ` · ${districtNames[d]}` : ""}`}>
              {zones.filter((z) => z.id.startsWith(`${d}-`)).map((z) => <option key={z.id} value={z.id}>{z.id} · {z.short_name}</option>)}
            </optgroup>
          ))}
        </select>
      </label>
      <div className="space-y-3">
        {sim.custom_controls.map((c) => {
          const meta = CONTROL_LABELS[c] ?? { label: c, icon: SlidersHorizontal };
          const Icon = meta.icon;
          return (
            <label key={c} className="block text-[12.5px]">
              <span className="mb-1 flex items-center gap-2">
                <Icon size={14} className="text-[var(--muted)]" aria-hidden />
                <span className="flex-1">{meta.label}</span>
                <span className="text-[11.5px] font-semibold" style={{ color: values[c] > 0 ? "var(--pulse)" : "var(--faint)" }}>{levelWord(values[c])}</span>
              </span>
              <input type="range" min={0} max={1.5} step={0.1} value={values[c]} className="cp-range w-full"
                onChange={(e) => setValues({ ...values, [c]: Number(e.target.value) })} aria-label={`${meta.label} intensity`} />
            </label>
          );
        })}
      </div>
      <label className="flex items-center justify-between gap-2 text-[12.5px]">
        <span className="font-semibold">Lasts</span>
        <select value={duration} onChange={(e) => setDuration(Number(e.target.value))} className="rounded-lg px-2 py-1.5 text-[12.5px]"
          style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}>
          <option value={300}>5 minutes</option>
          <option value={600}>10 minutes</option>
          <option value={1200}>20 minutes</option>
        </select>
      </label>
      <div className="flex gap-2">
        <button type="button" disabled={busy || !any}
          onClick={async () => { if (await act(() => api.custom(zone, values, duration), "Applying…")) onShow(zone); }}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[13px] font-semibold text-[#04221d] disabled:opacity-40"
          style={{ background: "var(--pulse)" }}>
          <Play size={14} aria-hidden /> Apply
        </button>
        <button type="button" disabled={busy} onClick={() => {
          const zero = Object.fromEntries(Object.keys(values).map((k) => [k, 0]));
          setValues(zero);
          act(() => api.custom(zone, zero, duration));
        }}
          className="rounded-lg px-3 py-2 text-[13px] font-semibold hover:bg-white/10 disabled:opacity-50" style={{ border: "1px solid var(--line)" }}>
          Clear
        </button>
      </div>
      {sim.active_events.length > 0 && (
        <ul className="space-y-0.5 text-[11.5px] text-[var(--muted)]">
          {sim.active_events.map((e, i) => <li key={i}>● {e.label} — {Math.round(e.level * 100)}%</li>)}
        </ul>
      )}
    </>
  );
}

// ---------------------------------------------------------------------- feeds

const FAULTS = [
  { id: "none", label: "Healthy" },
  { id: "outage", label: "Outage" },
  { id: "delay", label: "Delayed" },
  { id: "malformed", label: "Malformed data" },
];

function FeedsTab({ feeds, busy, act }: { feeds: FeedHealth[]; busy: boolean; act: Act }) {
  return (
    <>
      <p className="text-[12px] text-[var(--muted)]">
        Break a feed and watch CityPulse keep working — and say exactly what it can no longer check.
      </p>
      <ul className="space-y-2">
        {feeds.map((f) => (
          <li key={f.id} className="flex items-center gap-2 text-[12.5px]">
            <span className="h-2 w-2 rounded-full" style={{ background: FEED_META[f.status].color }} aria-hidden />
            <span className="flex-1 truncate">{f.label}</span>
            <span className="w-24 text-right text-[10.5px] font-semibold" style={{ color: FEED_META[f.status].color }}>{f.status}</span>
            <select aria-label={`${f.label} fault`} value={f.fault_mode} disabled={busy}
              onChange={(e) => act(() => api.setFault(f.id, e.target.value))}
              className="rounded-lg px-1.5 py-1 text-[12px]"
              style={{ background: "var(--panel-2)", border: `1px solid ${f.fault_mode === "none" ? "var(--line)" : "var(--warn)"}` }}>
              {FAULTS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </li>
        ))}
      </ul>
    </>
  );
}
