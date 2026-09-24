import L from "leaflet";
import { renderToStaticMarkup } from "react-dom/server";
import type { ZoneState } from "../../types";
import { ISSUE_ICONS, ISSUE_WORDS, STATUS_META } from "../../utils/status";
import { MAP_STATUS } from "./mapColors";

/**
 * The zone label is the heart of the 10-second read: WHERE (zone name), SEVERITY (status
 * word + colour + icon) and WHAT (issue icons with words). Built as static HTML because
 * Leaflet markers live outside React's tree.
 */
export function zoneLabelIcon(zone: ZoneState, selected: boolean, small = false): L.DivIcon {
  const color = MAP_STATUS[zone.status];
  const StatusIcon = STATUS_META[zone.status].icon;
  const hasLink = zone.relationships.some((r) => r.strength !== "weak");
  const issues = zone.issue_types.slice(0, 5);
  const compact = small || issues.length > 2; // icons only (with tooltips) to keep the label narrow
  const quiet = small && zone.status === "GREEN"; // on phones, normal zones show just name + tick

  const html = renderToStaticMarkup(
    <div style={{ position: "relative", transform: "translate(-50%, -50%)", width: "max-content" }}>
      {zone.status === "RED" && (
        <span
          className="cp-ring"
          style={{
            position: "absolute", left: "50%", top: "50%", width: 120, height: 120, marginLeft: -60, marginTop: -60,
            borderRadius: "50%", border: `2px solid ${color}`, pointerEvents: "none",
          }}
        />
      )}
      <div
        style={{
          position: "relative",
          background: "rgba(13,19,27,0.92)",
          border: `${selected ? 2 : 1.5}px solid ${selected ? "#e8eef5" : color}`,
          borderRadius: 12,
          padding: small ? "4px 7px 5px" : "6px 10px 7px",
          boxShadow: `0 6px 22px rgba(0,0,0,0.45), 0 0 0 4px ${color}22`,
          color: "#e8eef5",
          fontFamily: "Inter, system-ui, sans-serif",
          textAlign: "left",
          minWidth: small ? 0 : 132,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600 }}>
          <span style={{ color, display: "flex" }}>
            <StatusIcon size={15} strokeWidth={2.5} />
          </span>
          <span>{small ? `${zone.number} · ${zone.short_name}` : `Zone ${zone.number} · ${zone.short_name}`}</span>
        </div>
        {!quiet && (
          <div style={{ color, fontSize: 10.5, fontWeight: 700, letterSpacing: "0.06em", marginTop: 2 }}>
            {zone.status_label.toUpperCase()}
          </div>
        )}
        {issues.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 5 }}>
            {issues.map((k) => {
              const Icon = ISSUE_ICONS[k];
              return (
                <span
                  key={k}
                  title={ISSUE_WORDS[k] ?? k}
                  style={{
                    display: "inline-flex", alignItems: "center", gap: 3, fontSize: 10.5, padding: "1px 5px",
                    borderRadius: 6, background: "rgba(255,255,255,0.07)", color: "#cbd5e1",
                  }}
                >
                  {Icon && <Icon size={11} />}
                  {!compact && (ISSUE_WORDS[k] ?? k)}
                </span>
              );
            })}
          </div>
        )}
        {hasLink && (
          <div style={{ marginTop: 4, fontSize: 10, color: "#d8b4fe", fontWeight: 600 }}>⟷ possible link</div>
        )}
      </div>
    </div>,
  );
  return L.divIcon({ html, className: "zone-label", iconSize: [0, 0] });
}
