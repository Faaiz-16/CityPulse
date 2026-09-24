import { CarFront, ChevronDown, CloudRain, Droplets, FileWarning, Radio, Wind, Zap, type LucideIcon } from "lucide-react";
import { useState } from "react";
import type { MapLayers } from "./CityMap";

const LAYERS: { key: keyof MapLayers; label: string; icon: LucideIcon }[] = [
  { key: "rain", label: "Rain", icon: CloudRain },
  { key: "traffic", label: "Traffic", icon: CarFront },
  { key: "reports", label: "Reports", icon: FileWarning },
  { key: "air", label: "Air", icon: Wind },
  { key: "sensors", label: "Sensors", icon: Radio },
];

export function LayerToggles({ layers, onChange }: { layers: MapLayers; onChange: (l: MapLayers) => void }) {
  return (
    <div className="glass pointer-events-auto flex items-center gap-0.5 p-1" role="group" aria-label="Map layers">
      {LAYERS.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          type="button"
          aria-pressed={layers[key]}
          onClick={() => onChange({ ...layers, [key]: !layers[key] })}
          className="flex items-center gap-1.5 rounded-[9px] px-2.5 py-1.5 text-[12px] font-medium transition-colors"
          style={{ background: layers[key] ? "rgba(255,255,255,0.08)" : "transparent", color: layers[key] ? "var(--text)" : "var(--faint)" }}
          title={`${layers[key] ? "Hide" : "Show"} ${label.toLowerCase()}`}
        >
          <Icon size={14} aria-hidden />
          <span className="hidden md:inline">{label}</span>
          <span className="sr-only md:hidden">{label}</span>
        </button>
      ))}
    </div>
  );
}

/** The legend explains the visual language — nothing more. */
export function PulseLegend() {
  const [open, setOpen] = useState(() => typeof window === "undefined" || window.innerWidth >= 768);
  const Swatch = ({ children }: { children: React.ReactNode }) => (
    <span className="grid h-4 w-6 shrink-0 place-items-center" aria-hidden>{children}</span>
  );
  return (
    <div className="glass pointer-events-auto w-[196px] px-3 py-2.5 text-[12px]">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center justify-between">
        <span className="label-caps">Live pulse legend</span>
        <ChevronDown size={14} className={`text-[var(--faint)] transition-transform ${open ? "" : "-rotate-90"}`} aria-hidden />
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5 text-[#cbd5e1]">
          <li className="flex items-center gap-2"><Swatch><span className="h-3.5 w-3.5 border border-[#f87171] bg-[#f8717126]" /></Swatch>Possible disruption</li>
          <li className="flex items-center gap-2"><Swatch><span className="h-3.5 w-3.5 border border-[#fbbf24aa] bg-[#fbbf2414]" /></Swatch>Needs attention</li>
          <li className="flex items-center gap-2"><Swatch><span className="h-3.5 w-3.5 border border-[#94a3b855]" /></Swatch>Normal area</li>
          <li className="flex items-center gap-2"><Swatch><span className="flex gap-0.5"><i className="h-1.5 w-1.5 rounded-full bg-[#7dd3fc] shadow-[0_0_6px_#38bdf8]" /><i className="h-1.5 w-1.5 rounded-full bg-[#38bdf8] shadow-[0_0_6px_#38bdf8]" /></span></Swatch>Rain</li>
          <li className="flex items-center gap-2"><Swatch><span className="h-1 w-5 rounded-full bg-[#f87171] shadow-[0_0_6px_#f87171]" /></Swatch>Heavy traffic</li>
          <li className="flex items-center gap-2"><Swatch><Zap size={13} color="#facc15" /></Swatch>Power / signal outage</li>
          <li className="flex items-center gap-2"><Swatch><CarFront size={13} color="#f87171" /></Swatch>Road accident</li>
          <li className="flex items-center gap-2"><Swatch><Droplets size={13} color="#38bdf8" /></Swatch>Waterlogging</li>
          <li className="flex items-center gap-2"><Swatch><span className="h-3 w-5 rounded-full bg-[#a855f7] opacity-60 blur-[2px]" /></Swatch>Poor air</li>
        </ul>
      )}
      {open && <p className="mt-2 text-[10px] leading-snug text-[var(--faint)]">Jaipur in a 9 × 9 grid of ~2.5 km demonstration areas — not official wards.</p>}
    </div>
  );
}
