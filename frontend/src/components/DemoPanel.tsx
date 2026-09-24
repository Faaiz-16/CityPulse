import { CheckCircle2, Circle, CloudRain, FlaskConical, History, Play, RotateCcw, Car, Wind, X, Zap } from "lucide-react";
import { useState } from "react";
import { api } from "../services/api";
import type { FeedHealth, SimulationStatus, ZoneState } from "../types";
import { clockTime } from "../utils/format";

const EVENTS = [
  { id: "heavy_rain", label: "Heavy rain", icon: CloudRain },
  { id: "traffic_spike", label: "Traffic spike", icon: Car },
  { id: "incident_cluster", label: "Outage cluster", icon: Zap },
  { id: "poor_air", label: "Poor air", icon: Wind },
];
const FAULTS = [
  { id: "none", label: "Healthy" },
  { id: "outage", label: "Outage" },
  { id: "delay", label: "Delayed" },
  { id: "malformed", label: "Malformed" },
];

interface Props {
  sim: SimulationStatus;
  zones: ZoneState[];
  feeds: FeedHealth[];
  selectedZone: string | null;
  onClose: () => void;
  onChanged: () => void;
  onStartReplay: () => void;
}

/** Judge/demo controls. Events change the simulated city; the pipeline must detect them itself. */
export function DemoPanel({ sim, zones, feeds, selectedZone, onClose, onChanged, onStartReplay }: Props) {
  const [zone, setZone] = useState(selectedZone ?? "Z3");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);

  async function act(fn: () => Promise<{ message: string }>) {
    setBusy(true);
    try {
      const r = await fn();
      setMessage({ text: r.message });
      onChanged();
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : "Request failed", error: true });
    } finally {
      setBusy(false);
    }
  }

  const stages = sim.scenario ? [...sim.scenario.stages].sort((a, b) => {
    if (!a.reached_at) return 1;
    if (!b.reached_at) return -1;
    return a.reached_at.localeCompare(b.reached_at);
  }) : [];

  return (
    <div className="panel cp-fade-in flex w-full shrink-0 flex-col overflow-hidden" role="dialog" aria-label="Demo controls">
      <div className="flex items-center gap-2 border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
        <FlaskConical size={16} className="text-[var(--pulse)]" aria-hidden />
        <h2 className="text-sm font-semibold">Demo controls</h2>
        <span className="text-[11px] text-[var(--faint)]">simulated city</span>
        <button type="button" onClick={onClose} className="ml-auto rounded-md p-1 text-[var(--muted)] hover:bg-white/5" aria-label="Close demo controls">
          <X size={16} />
        </button>
      </div>

      <div className="space-y-4 p-4">
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => act(api.runScenario)}
            className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[13px] font-semibold text-[#04221d] disabled:opacity-50"
            style={{ background: "var(--pulse)" }}
          >
            <Play size={14} aria-hidden /> Run full scenario
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => act(api.reset)}
            className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[13px] font-semibold disabled:opacity-50"
            style={{ border: "1px solid var(--line)", background: "var(--panel-2)" }}
          >
            <RotateCcw size={14} aria-hidden /> Normal state
          </button>
          <button
            type="button"
            onClick={onStartReplay}
            className="col-span-2 flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[13px] font-semibold"
            style={{ border: "1px solid #c084fc66", background: "rgba(192,132,252,0.1)", color: "#e9d5ff" }}
          >
            <History size={14} aria-hidden /> Replay recorded storm (past data)
          </button>
        </div>

        {sim.scenario && (
          <div className="rounded-lg p-3" style={{ background: "var(--panel-2)" }}>
            <div className="mb-1.5 flex items-center justify-between text-[12px]">
              <span className="font-semibold">{sim.scenario.name}</span>
              <span className="font-mono text-[var(--faint)]">{sim.scenario.elapsed_s}s</span>
            </div>
            <p className="mb-2 text-[11px] text-[var(--faint)]">Stages tick off only when the analysis actually detects them.</p>
            <ol className="space-y-1 text-[12px]">
              {stages.map((s) => (
                <li key={s.key} className="flex items-center gap-2">
                  {s.reached_at ? <CheckCircle2 size={13} color="var(--ok)" aria-label="reached" /> : <Circle size={13} className="text-[var(--faint)]" aria-label="pending" />}
                  <span className={s.reached_at ? "" : "text-[var(--faint)]"}>{s.label}</span>
                  {s.reached_at && <span className="ml-auto font-mono text-[10.5px] text-[var(--faint)]">{clockTime(s.reached_at)}</span>}
                </li>
              ))}
            </ol>
          </div>
        )}

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <h3 className="label-caps">Trigger an event</h3>
            <label className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
              in
              <select
                value={zone}
                onChange={(e) => setZone(e.target.value)}
                className="rounded-md px-1.5 py-1 text-[12px]"
                style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}
              >
                {zones.map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {EVENTS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                disabled={busy}
                onClick={() => act(() => api.triggerEvent(id, zone))}
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-[12.5px] hover:bg-white/5 disabled:opacity-50"
                style={{ border: "1px solid var(--line)" }}
              >
                <Icon size={14} className="text-[var(--muted)]" aria-hidden /> {label}
              </button>
            ))}
          </div>
          {sim.active_events.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-[11.5px] text-[var(--muted)]">
              {sim.active_events.map((e, i) => (
                <li key={i}>
                  ● {e.label} — intensity {Math.round(e.level * 100)}%
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h3 className="label-caps mb-1.5">Simulate a feed failure</h3>
          <ul className="space-y-1.5">
            {feeds.map((f) => (
              <li key={f.id} className="flex items-center gap-2 text-[12.5px]">
                <span className="flex-1 truncate">{f.label}</span>
                <select
                  aria-label={`${f.label} fault mode`}
                  value={f.fault_mode}
                  disabled={busy}
                  onChange={(e) => act(() => api.setFault(f.id, e.target.value))}
                  className="rounded-md px-1.5 py-1 text-[12px]"
                  style={{
                    background: "var(--panel-2)",
                    border: `1px solid ${f.fault_mode === "none" ? "var(--line)" : "var(--warn)"}`,
                  }}
                >
                  {FAULTS.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
        </div>

        {message && (
          <p className="text-[12px]" role="status" style={{ color: message.error ? "var(--bad)" : "var(--muted)" }}>
            {message.text}
          </p>
        )}
      </div>
    </div>
  );
}
