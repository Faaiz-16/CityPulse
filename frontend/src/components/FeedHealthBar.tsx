import { CloudSun, Car, FileText, Wind, Radio, type LucideIcon } from "lucide-react";
import { useState } from "react";
import type { FeedHealth } from "../types";
import { agoText } from "../utils/format";
import { FEED_META } from "../utils/status";

const FEED_ICONS: Record<string, LucideIcon> = {
  weather: CloudSun,
  traffic: Car,
  incidents: FileText,
  air_quality: Wind,
  iot_sensors: Radio,
};

const SHORT: Record<string, string> = {
  weather: "Weather",
  traffic: "Traffic",
  incidents: "Reports",
  air_quality: "Air",
  iot_sensors: "Sensors",
};

/** One chip per feed: icon, name, status word. Click for details (message, age, rejects). */
export function FeedHealthBar({ feeds, now }: { feeds: FeedHealth[]; now: number }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="relative flex flex-wrap items-center gap-1.5" aria-label="Data feed health">
      {feeds.map((f) => {
        const meta = FEED_META[f.status];
        const Icon = FEED_ICONS[f.id] ?? Radio;
        const healthy = f.status === "LIVE" || f.status === "SIMULATED";
        return (
          <div key={f.id} className="relative">
            <button
              type="button"
              onClick={() => setOpen(open === f.id ? null : f.id)}
              aria-expanded={open === f.id}
              className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] transition-colors hover:bg-white/5"
              style={{
                border: `1px solid ${healthy ? "var(--line)" : meta.color}`,
                background: healthy ? "transparent" : `color-mix(in srgb, ${meta.color} 12%, transparent)`,
              }}
              title={`${f.label}: ${f.status} — ${f.message}`}
            >
              <Icon size={13} aria-hidden className="text-[var(--muted)]" />
              <span className="hidden text-[var(--muted)] lg:inline">{SHORT[f.id] ?? f.label}</span>
              <span className="font-semibold tracking-wide" style={{ color: meta.color }}>
                {f.status}
              </span>
            </button>
            {open === f.id && (
              <div
                className="panel cp-fade-in absolute right-0 top-full z-[1200] mt-2 w-72 p-3 text-xs shadow-2xl"
                role="dialog"
                aria-label={`${f.label} feed details`}
              >
                <div className="mb-1 flex items-center justify-between">
                  <span className="font-semibold">{f.label}</span>
                  <span className="font-semibold" style={{ color: meta.color }}>
                    {f.status}
                  </span>
                </div>
                <p className="mb-2 text-[var(--muted)]">{meta.hint}.</p>
                <p className="mb-2">{f.message}</p>
                <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-[var(--muted)]">
                  <dt>Source</dt>
                  <dd className="text-right text-[var(--text)]">{f.provider}</dd>
                  <dt>Last update</dt>
                  <dd className="text-right text-[var(--text)]">{agoText(f.last_success_at, now)}</dd>
                  <dt>Expected every</dt>
                  <dd className="text-right text-[var(--text)]">{f.expected_interval_seconds} s</dd>
                  <dt>Records accepted</dt>
                  <dd className="text-right text-[var(--text)]">{f.records_accepted.toLocaleString()}</dd>
                  <dt>Malformed rejected</dt>
                  <dd className="text-right text-[var(--text)]">{f.records_rejected.toLocaleString()}</dd>
                </dl>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
