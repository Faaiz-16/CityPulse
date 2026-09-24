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

/** Hotspot label: the heart of a group of unusual areas — where, how serious, what. */
export function hotspotLabelIcon(z: ZoneState, cells: number, selected: boolean, small: boolean): L.DivIcon {
  const key = `spot|${z.id}|${z.status}|${z.headline}|${cells}|${selected}|${small}`;
  return cached(key, () => {
    const color = MAP_STATUS[z.status];
    const red = z.status === "RED";
    const Icon: LucideIcon = red ? OctagonAlert : CircleAlert;
    const html = renderToStaticMarkup(
      <div style={{ transform: "translate(-50%, -50%)", width: "max-content", fontFamily: FONT, cursor: "pointer",
        padding: "4px 9px 5px", borderRadius: 9, background: "rgba(8,12,18,0.86)",
        border: `${selected ? 2 : 1.2}px solid ${selected ? "#e8eef5" : color}`, boxShadow: "0 4px 14px rgba(0,0,0,0.45)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5, color, fontSize: red ? 13 : 12, fontWeight: 700 }}>
          <Icon size={red ? 14 : 12} strokeWidth={2.6} />
          {z.short_name}
        </div>
        {!small && (
          <div style={{ color: "#cbd5e1", fontSize: 10.5, fontWeight: 500 }}>
            {red ? "Possible disruption" : "Needs attention"}{cells > 1 ? ` · ${cells} areas` : ""}
          </div>
        )}
      </div>,
    );
    return L.divIcon({ html, className: "cp-divicon", iconSize: [0, 0] });
  });
}

/** Small name tag for a selected normal area. */
export function placeLabelIcon(z: ZoneState): L.DivIcon {
  return cached(`place|${z.id}|${z.status}`, () => {
    const html = renderToStaticMarkup(
      <div style={{ transform: "translate(-50%, -50%)", width: "max-content", display: "flex", alignItems: "center", gap: 5,
        padding: "3px 8px", borderRadius: 999, fontSize: 11, fontWeight: 600, fontFamily: FONT, color: "#e2e8f0",
        background: "rgba(8,12,18,0.8)", border: "1px solid rgba(232,238,245,0.6)" }}>
        <CheckCircle2 size={11} color={MAP_STATUS[z.status]} strokeWidth={2.6} />
        {z.short_name} <span style={{ color: "#64748b" }}>{z.id}</span>
      </div>,
    );
    return L.divIcon({ html, className: "cp-divicon", iconSize: [0, 0] });
  });
}

/** Grid reference (A–I, 1–9) along the edges of the grid. */
export function gridRefIcon(text: string): L.DivIcon {
  return cached(`ref|${text}`, () => L.divIcon({
    html: `<div style="transform:translate(-50%,-50%);font:600 11px ${FONT};color:rgba(226,232,240,0.75);letter-spacing:0.04em">${text}</div>`,
    className: "cp-divicon", iconSize: [0, 0],
  }));
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
