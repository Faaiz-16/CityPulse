import L from "leaflet";
import { CarFront, CheckCircle2, CircleAlert, Droplets, OctagonAlert, TreePine, Wind, Zap, type LucideIcon } from "lucide-react";
import { renderToStaticMarkup } from "react-dom/server";
import type { ZoneState } from "../../types";
import { MAP_STATUS } from "./mapColors";

// Leaflet markers live outside React's tree, so their contents are built as static HTML.
// Icons are cached by their visual inputs so polling doesn't rebuild identical markers.
const cache = new Map<string, L.DivIcon>();
function cached(key: string, build: () => L.DivIcon): L.DivIcon {
  let icon = cache.get(key);
  if (!icon) {
    icon = build();
    cache.set(key, icon);
    if (cache.size > 400) cache.delete(cache.keys().next().value as string);
  }
  return icon;
}

const FONT = "Inter, system-ui, sans-serif";

/** Zone label: tiny when normal, clear when unusual, unmissable when disrupted. */
export function zoneLabelIcon(z: ZoneState, selected: boolean, small: boolean): L.DivIcon {
  const key = `zone|${z.id}|${z.status}|${z.headline}|${selected}|${small}`;
  return cached(key, () => {
    const color = MAP_STATUS[z.status];
    let inner: React.ReactNode;
    if (z.status === "GREEN") {
      inner = (
        <div style={{ display: "flex", alignItems: "center", gap: 5, padding: "3px 8px", borderRadius: 999, fontSize: 11,
          fontWeight: 600, color: "#cbd5e1", background: "rgba(8,12,18,0.72)", border: `1px solid ${selected ? "#e8eef5" : "rgba(52,211,153,0.35)"}` }}>
          <CheckCircle2 size={11} color={color} strokeWidth={2.6} />
          Zone {z.number}
          {!small && <span style={{ color: "#64748b", fontWeight: 500 }}>· {z.short_name}</span>}
        </div>
      );
    } else {
      const red = z.status === "RED";
      const Icon: LucideIcon = red ? OctagonAlert : CircleAlert;
      inner = (
        <div style={{ padding: red ? "6px 11px 7px" : "5px 9px 6px", borderRadius: 10, background: "rgba(8,12,18,0.88)",
          border: `${selected ? 2 : 1.5}px solid ${selected ? "#e8eef5" : color}`,
          boxShadow: red ? `0 0 0 4px ${color}33, 0 0 24px ${color}66` : `0 0 14px ${color}33` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, color, fontSize: red ? 12 : 11, fontWeight: 800, letterSpacing: "0.06em" }}>
            <Icon size={red ? 15 : 13} strokeWidth={2.6} />
            ZONE {z.number} · {red ? "POSSIBLE DISRUPTION" : "ATTENTION"}
          </div>
          {!small && (
            <div style={{ marginTop: 2, color: "#e2e8f0", fontSize: 11.5, fontWeight: 500 }}>{z.headline}</div>
          )}
        </div>
      );
    }
    const html = renderToStaticMarkup(
      <div style={{ transform: "translate(-50%, -50%)", width: "max-content", fontFamily: FONT, cursor: "pointer" }}>{inner}</div>,
    );
    return L.divIcon({ html, className: "cp-divicon", iconSize: [0, 0] });
  });
}

const KIND_ICON: Record<string, LucideIcon> = { water: Droplets, power: Zap, accident: CarFront, tree: TreePine };

/** A cluster of same-kind reports: glowing icon + count. */
export function incidentIcon(kind: string, color: string, count: number): L.DivIcon {
  return cached(`inc|${kind}|${color}|${Math.min(count, 99)}`, () => {
    const Icon = KIND_ICON[kind] ?? CircleAlert;
    const size = count > 1 ? 30 : 26;
    const html = renderToStaticMarkup(
      <div style={{ position: "relative", width: size, height: size, transform: "translate(-50%, -50%)", fontFamily: FONT }}>
        <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: `${color}26`, border: `1.5px solid ${color}`,
          boxShadow: `0 0 12px ${color}aa`, display: "grid", placeItems: "center", backdropFilter: "blur(2px)" }}>
          <Icon size={count > 1 ? 15 : 13} color={color} strokeWidth={2.4} />
        </div>
        {count > 1 && (
          <div style={{ position: "absolute", top: -7, right: -9, minWidth: 17, height: 17, padding: "0 4px", borderRadius: 999,
            background: color, color: "#05080d", fontSize: 10, fontWeight: 800, display: "grid", placeItems: "center" }}>
            {count > 99 ? "99+" : count}
          </div>
        )}
      </div>,
    );
    return L.divIcon({ html, className: "cp-divicon", iconSize: [0, 0] });
  });
}

/** Air-quality badge placed in the middle of a haze. */
export function airIcon(aqi: number): L.DivIcon {
  return cached(`air|${Math.round(aqi)}`, () => {
    const html = renderToStaticMarkup(
      <div style={{ transform: "translate(-50%, -50%)", width: "max-content", display: "flex", alignItems: "center", gap: 5,
        padding: "3px 8px", borderRadius: 999, background: "rgba(8,12,18,0.8)", border: "1px solid #a855f7",
        color: "#e9d5ff", fontSize: 11, fontWeight: 700, fontFamily: FONT, boxShadow: "0 0 14px #a855f766" }}>
        <Wind size={12} color="#c084fc" /> AQI {Math.round(aqi)}
      </div>,
    );
    return L.divIcon({ html, className: "cp-divicon", iconSize: [0, 0] });
  });
}
