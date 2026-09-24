import { History, Pause, Play, SkipBack, StepBack, StepForward, X } from "lucide-react";
import type { ReplayControls } from "../hooks/useReplay";
import type { ZoneState } from "../types";
import { clockTime } from "../utils/format";
import { MAP_STATUS } from "./map/mapColors";

const SPEEDS = [1, 2, 4];

/**
 * Replay controls: play/pause, step, speed, and a scrubber drawn as a zone × time status strip
 * with the key moments CityPulse detected. Labelled as recorded data throughout.
 */
export function ReplayBar({ replay, zones }: { replay: ReplayControls; zones: ZoneState[] }) {
  const { meta, index, playing, speed } = replay;
  if (!meta) return null;
  const frames = meta.frames;
  const current = frames[index];
  const pct = (i: number) => (frames.length > 1 ? (i / (frames.length - 1)) * 100 : 0);

  return (
    <div className="panel pointer-events-auto w-full p-3" role="region" aria-label="Historical replay controls">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-bold tracking-wide"
          style={{ background: "rgba(192,132,252,0.15)", color: "#d8b4fe", border: "1px solid #c084fc66" }}
        >
          <History size={13} aria-hidden /> REPLAY · RECORDED DATA
        </span>
        <span className="text-[13px] font-semibold">{meta.name}</span>
        <span className="font-mono text-lg font-semibold" aria-live="polite">
          {clockTime(current?.t)}
        </span>

        <div className="ml-auto flex items-center gap-1">
          <IconButton label="Back to start" onClick={() => replay.setIndex(0)}>
            <SkipBack size={15} />
          </IconButton>
          <IconButton label="Previous minute" onClick={() => replay.setIndex(index - 1)}>
            <StepBack size={15} />
          </IconButton>
          <button
            type="button"
            onClick={() => {
              if (!playing && index >= frames.length - 1) replay.setIndex(0);
              replay.setPlaying(!playing);
            }}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-semibold text-[#1a0b2e]"
            style={{ background: "#c084fc" }}
          >
            {playing ? <Pause size={14} aria-hidden /> : <Play size={14} aria-hidden />}
            {playing ? "Pause" : "Play"}
          </button>
          <IconButton label="Next minute" onClick={() => replay.setIndex(index + 1)}>
            <StepForward size={15} />
          </IconButton>
          <div className="ml-1 flex rounded-lg p-0.5" style={{ border: "1px solid var(--line)" }} role="group" aria-label="Playback speed">
            {SPEEDS.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={speed === s}
                onClick={() => replay.setSpeed(s)}
                className="rounded-md px-2 py-1 text-[11px] font-semibold"
                style={{ background: speed === s ? "var(--panel-2)" : "transparent", color: speed === s ? "var(--text)" : "var(--faint)" }}
                title={`${s} recorded minute${s > 1 ? "s" : ""} per second`}
              >
                {s}×
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={replay.exit}
            className="ml-2 flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12px] font-semibold hover:bg-white/5"
            style={{ border: "1px solid var(--line)" }}
          >
            <X size={14} aria-hidden /> Back to live
          </button>
        </div>
      </div>

      {/* Scrubber: zone × time status strip with a transparent range input on top */}
      <div className="relative mt-3">
        <div className="space-y-px overflow-hidden rounded-md" aria-hidden>
          {zones.map((z) => (
            <div key={z.id} className="flex h-2">
              {frames.map((f) => {
                const s = f.statuses[z.id];
                return <div key={f.i} className="flex-1" style={{ background: MAP_STATUS[s], opacity: s === "GREEN" ? 0.25 : 0.9 }} />;
              })}
            </div>
          ))}
        </div>
        {meta.key_moments.map((m) => (
          <div key={m.label} className="pointer-events-none absolute -top-1 bottom-0 w-px bg-white/60" style={{ left: `${pct(m.i)}%` }} />
        ))}
        <div className="pointer-events-none absolute -top-1.5 bottom-[-6px] w-0.5 rounded bg-white" style={{ left: `${pct(index)}%` }} />
        <input
          type="range"
          min={0}
          max={frames.length - 1}
          value={index}
          onChange={(e) => {
            replay.setPlaying(false);
            replay.setIndex(Number(e.target.value));
          }}
          className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
          aria-label="Replay position"
          aria-valuetext={clockTime(current?.t)}
        />
        <div className="mt-1 flex justify-between font-mono text-[10px] text-[var(--faint)]">
          <span>{clockTime(frames[0]?.t, false)}</span>
          <span>rows: zones 1–5 · each column = 1 recorded minute</span>
          <span>{clockTime(frames[frames.length - 1]?.t, false)}</span>
        </div>
      </div>

      {/* What CityPulse detected, and when — click to jump */}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {meta.key_moments.map((m) => (
          <button
            key={m.label}
            type="button"
            onClick={() => {
              replay.setPlaying(false);
              replay.setIndex(m.i);
            }}
            className="rounded-md px-2 py-0.5 text-[11px] hover:bg-white/5"
            style={{ border: `1px solid ${index >= m.i ? "#c084fc88" : "var(--line)"}`, color: index >= m.i ? "var(--text)" : "var(--faint)" }}
          >
            <span className="font-mono">{clockTime(m.t, false)}</span> {m.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} title={label} className="rounded-lg p-1.5 text-[var(--muted)] hover:bg-white/5 hover:text-[var(--text)]">
      {children}
    </button>
  );
}
