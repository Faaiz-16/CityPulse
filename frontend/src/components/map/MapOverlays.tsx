import { CloudRain, Layers, Radio, FileWarning } from "lucide-react";
import type { ZoneStatus } from "../../types";
import { STATUS_META } from "../../utils/status";
import type { MapLayers } from "./CityMap";
import { MAP_STATUS, RAIN } from "./mapColors";

export function MapLegend() {
  return (
    <div className="panel pointer-events-auto p-3 text-xs" aria-label="Map legend">
      <div className="label-caps mb-2">Zone status</div>
      <ul className="space-y-1.5">
        {(["GREEN", "YELLOW", "RED"] as ZoneStatus[]).map((s) => {
          const Icon = STATUS_META[s].icon;
          return (
            <li key={s} className="flex items-center gap-2">
              <span className="h-3 w-5 rounded-sm" style={{ background: `${MAP_STATUS[s]}55`, border: `1.5px solid ${MAP_STATUS[s]}` }} />
              <Icon size={13} color={MAP_STATUS[s]} aria-hidden />
              <span>{STATUS_META[s].word}</span>
            </li>
          );
        })}
      </ul>
      <div className="mt-2.5 space-y-1.5 border-t pt-2.5 text-[var(--muted)]" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full" style={{ background: `${RAIN}55`, border: `1px dashed ${RAIN}` }} />
          Rain (bigger = heavier)
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-[#94a3b8]" /> Civic report (anonymous)
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[#d8b4fe]">⟷</span> Possible link found
        </div>
      </div>
      <p className="mt-2.5 max-w-[190px] text-[10px] leading-snug text-[var(--faint)]">
        Demonstration zones on a real basemap — not official boundaries. Data is simulated unless a feed says LIVE.
      </p>
    </div>
  );
}

interface ToggleProps {
  layers: MapLayers;
  onChange: (layers: MapLayers) => void;
}

export function LayerToggles({ layers, onChange }: ToggleProps) {
  const items: { key: keyof MapLayers; label: string; icon: typeof Layers }[] = [
    { key: "rain", label: "Rain", icon: CloudRain },
    { key: "reports", label: "Reports", icon: FileWarning },
    { key: "sensors", label: "IoT sensors", icon: Radio },
  ];
  return (
    <div className="panel pointer-events-auto flex items-center gap-1 p-1" role="group" aria-label="Map layers">
      <Layers size={14} className="mx-1.5 text-[var(--muted)]" aria-hidden />
      {items.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          type="button"
          aria-pressed={layers[key]}
          onClick={() => onChange({ ...layers, [key]: !layers[key] })}
          className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors"
          style={{
            background: layers[key] ? "var(--panel-2)" : "transparent",
            color: layers[key] ? "var(--text)" : "var(--faint)",
            border: `1px solid ${layers[key] ? "var(--line)" : "transparent"}`,
          }}
        >
          <Icon size={13} aria-hidden />
          <span className="hidden sm:inline">{label}</span>
          <span className="sr-only sm:hidden">{label}</span>
        </button>
      ))}
    </div>
  );
}
