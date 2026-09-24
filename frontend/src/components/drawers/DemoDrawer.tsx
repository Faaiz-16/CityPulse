import {
  CarFront, CheckCircle2, Circle, CloudLightning, CloudRain, FlaskConical, History, Layers, Pause, Play, RotateCcw,
  SlidersHorizontal, Waves, Wind, Zap, Database, Clapperboard, type LucideIcon,
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
const ZONE_NAMES: Record<string, string> = { Z1: "Zone 1 — Central", Z2: "Zone 2 — North", Z3: "Zone 3 — East", Z4: "Zone 4 — South", Z5: "Zone 5 — West" };

type Tab = "scenarios" | "custom" | "feeds";

interface Props {
  sim: SimulationStatus;
  zones: ZoneState[];
  feeds: FeedHealth[];
  onClose: () => void;
  onChanged: () => void;
  onStartReplay: () => void;
}

/** Everything needed to *create* a story: scenarios, playback, custom sliders, feed failures. */
export function DemoDrawer({ sim, zones, feeds, onClose, onChanged, onStartReplay }: Props) {
  const [tab, setTab] = useState<Tab>("scenarios");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);

  async function act(fn: () => Promise<{ message: string }>) {
    setBusy(true);
    try {
      setMessage({ text: (await fn()).message });
      onChanged();
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : "Request failed", error: true });
    } finally {
      setBusy(false);
    }
  }

  const tabs: { id: Tab; label: string; icon: LucideIcon }[] = [
    { id: "scenarios", label: "Scenarios", icon: Clapperboard },
    { id: "custom", label: "Custom", icon: SlidersHorizontal },
    { id: "feeds", label: "Feed failures", icon: Database },
  ];

  return (
    <Drawer side="left" title="Demo" subtitle="Create a civic incident — CityPulse must detect it on its own."
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
        {tab === "scenarios" && <ScenariosTab sim={sim} zones={zones} busy={busy} act={act} onStartReplay={onStartReplay} />}
        {tab === "custom" && <CustomTab sim={sim} busy={busy} act={act} />}
        {tab === "feeds" && <FeedsTab feeds={feeds} busy={busy} act={act} />}
        {message && (
          <p className="text-[12px]" role="status" style={{ color: message.error ? "var(--bad)" : "var(--muted)" }}>{message.text}</p>
        )}
      </div>
    </Drawer>
  );
}

type Act = (fn: () => Promise<{ message: string }>) => Promise<void>;

// ------------------------------------------------------------------ scenarios

function ScenariosTab({ sim, zones, busy, act, onStartReplay }: {
  sim: SimulationStatus; zones: ZoneState[]; busy: boolean; act: Act; onStartReplay: () => void;
}) {
  const [selected, setSelected] = useState<string>(sim.scenario?.id ?? "heavy_rain");
  return (
    <>
      {sim.scenario && <NowPlaying sim={sim} zones={zones} busy={busy} act={act} />}

      <div>
        <h3 className="label-caps mb-2">Choose a scenario</h3>
        <div className="space-y-1.5" role="radiogroup" aria-label="Scenarios">
          <button type="button" role="radio" aria-checked={false} disabled={busy} onClick={() => act(api.reset)}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left hover:bg-white/5 disabled:opacity-50"
            style={{ border: "1px solid var(--line)" }}>
            <CheckCircle2 size={17} color="var(--ok)" aria-hidden />
            <span className="flex-1">
              <span className="block text-[13px] font-semibold">Normal city</span>
              <span className="block text-[11.5px] text-[var(--muted)]">Clear every event and feed fault</span>
            </span>
            <RotateCcw size={14} className="text-[var(--faint)]" aria-hidden />
          </button>
          {sim.presets.map((p) => (
            <PresetCard key={p.id} preset={p} selected={selected === p.id} busy={busy}
              onSelect={() => setSelected(p.id)} onRun={() => act(() => api.runScenario(p.id))} />
          ))}
        </div>
      </div>

      <button type="button" onClick={onStartReplay}
        className="flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2 text-[12.5px] font-semibold"
        style={{ border: "1px solid #c084fc55", background: "rgba(192,132,252,0.08)", color: "#e9d5ff" }}>
        <History size={14} aria-hidden /> Replay a recorded storm (past data)
      </button>
    </>
  );
}

function PresetCard({ preset, selected, busy, onSelect, onRun }: {
  preset: ScenarioPreset; selected: boolean; busy: boolean; onSelect: () => void; onRun: () => void;
}) {
  const Icon = PRESET_ICONS[preset.icon] ?? CloudRain;
  return (
    <div className="rounded-xl" style={{ border: `1px solid ${selected ? "rgba(45,212,191,0.5)" : "var(--line)"}`, background: selected ? "rgba(45,212,191,0.06)" : "transparent" }}>
      <button type="button" role="radio" aria-checked={selected} onClick={onSelect}
        className="flex w-full items-center gap-3 px-3 py-2 text-left">
        <Icon size={17} className="shrink-0" color={selected ? "var(--pulse)" : "var(--muted)"} aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2 text-[13px] font-semibold">
            {preset.name}
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: SEVERITY_COLOR[preset.severity] }} title={`${preset.severity} severity`} />
          </span>
          <span className="block truncate text-[11.5px] text-[var(--muted)]">{preset.tagline}</span>
        </span>
        <span className="shrink-0 text-[10.5px] text-[var(--faint)]">Zone {preset.zone_id.slice(1)}</span>
      </button>
      {selected && (
        <div className="cp-fade-in space-y-2 px-3 pb-3 text-[12px]">
          <dl className="grid grid-cols-[72px_1fr] gap-x-2 gap-y-1 text-[var(--muted)]">
            <dt>Where</dt><dd className="text-[var(--text)]">{ZONE_NAMES[preset.zone_id]}</dd>
            <dt>Feeds</dt><dd className="text-[var(--text)]">{preset.feeds.join(" · ")}</dd>
            <dt>Expect</dt><dd className="text-[var(--text)]">{preset.expected}</dd>
            <dt>Story</dt><dd className="text-[var(--text)]">{Math.max(...preset.storyline.map((s) => s.expected_at_s))} s at 1× — faster at 2×/4×</dd>
          </dl>
          <button type="button" disabled={busy} onClick={onRun}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[13px] font-semibold text-[#04221d] disabled:opacity-50"
            style={{ background: "var(--pulse)" }}>
            <Play size={14} aria-hidden /> Run scenario
          </button>
        </div>
      )}
    </div>
  );
}

/** The running story: playback controls + beats ticked only when the analysis detects them. */
export function NowPlaying({ sim, zones, busy, act }: { sim: SimulationStatus; zones: ZoneState[]; busy: boolean; act: Act }) {
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
    <section className="rounded-xl p-3" style={{ background: "rgba(45,212,191,0.07)", border: "1px solid rgba(45,212,191,0.35)" }} aria-label="Running scenario">
      <div className="flex items-center gap-2">
        <span className="label-caps" style={{ color: "var(--pulse)" }}>{sim.clock.paused ? "Paused" : "Now playing"}</span>
        <span className="ml-auto font-mono text-[12px] text-[#cbd5e1]">T+{sc.elapsed_s}s</span>
      </div>
      <div className="mt-0.5 text-[14px] font-semibold">{sc.name}</div>
      <div className="text-[11.5px] text-[var(--muted)]">{ZONE_NAMES[sc.focus_zone]} · {done}/{sc.stages.length} detected</div>

      <PlaybackControls sim={sim} busy={busy} act={act} />

      <ol className="mt-3 space-y-1 text-[12.5px]">
        {stages.map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            {s.reached_at ? <CheckCircle2 size={14} color="var(--ok)" aria-label="detected" /> : <Circle size={14} className="text-[var(--faint)]" aria-label="waiting" />}
            <span className={s.reached_at ? "" : "text-[var(--faint)]"}>{s.label}</span>
            <span className="ml-auto font-mono text-[10.5px] text-[var(--faint)]">
              {s.reached_at ? `T+${s.t_plus_s ?? "?"}s` : `~T+${s.expected_at_s}s`}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-1.5 text-[10.5px] text-[var(--faint)]">
        Beats tick only when the analysis detects them. “~T+” = typical time at 1×; at 2×/4× detection lands later in scenario time because analysis windows run on the real clock.
      </p>
      {focus && (
        <p className="mt-3 rounded-lg px-2.5 py-1.5 text-[12px]" style={{ background: "rgba(0,0,0,0.25)" }}>
          <span className="text-[var(--muted)]">CityPulse now says: </span>
          <span className="font-semibold" style={{ color: STATUS_META[focus.status].color }}>{focus.status_label}</span>
          <span className="text-[var(--muted)]"> — {focus.headline}</span>
        </p>
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

function CustomTab({ sim, busy, act }: { sim: SimulationStatus; busy: boolean; act: Act }) {
  const [zone, setZone] = useState(sim.custom?.zone_id ?? "Z3");
  const [duration, setDuration] = useState(sim.custom?.duration_s ?? 600);
  const [values, setValues] = useState<Record<string, number>>(
    () => Object.fromEntries(sim.custom_controls.map((c) => [c, sim.custom?.values[c] ?? 0])),
  );
  useEffect(() => {
    if (sim.custom) setValues((v) => ({ ...v, ...sim.custom!.values }));
  }, [sim.custom]);
  const any = Object.values(values).some((v) => v > 0);
  return (
    <>
      <p className="text-[12px] text-[var(--muted)]">
        Set conditions in one zone. The simulated feeds change; CityPulse has to notice and connect them itself.
      </p>
      <label className="flex items-center justify-between gap-2 text-[12.5px]">
        <span className="font-semibold">Zone</span>
        <select value={zone} onChange={(e) => setZone(e.target.value)} className="rounded-lg px-2 py-1.5 text-[12.5px]"
          style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}>
          {Object.entries(ZONE_NAMES).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
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
        <button type="button" disabled={busy || !any} onClick={() => act(() => api.custom(zone, values, duration))}
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
