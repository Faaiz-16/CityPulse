import { useSyncExternalStore } from "react";
import type { ZoneState } from "../../types";
import { CHANCE_WORD, FORECAST_COLOR, STATUS_META } from "../../utils/status";
import { MAP_STATUS } from "./mapColors";

/**
 * The block under the pointer, shared between the map (which sets it) and the fixed hover card
 * (which shows it). A tiny store instead of React state, so hovering re-renders only the card —
 * not the app or the map.
 */
let hovered: string | null = null;
const listeners = new Set<() => void>();

export function setHoveredBlock(id: string | null) {
  if (id === hovered) return;
  hovered = id;
  listeners.forEach((l) => l());
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

/** The hovered block's name, status and "what may happen next", in one fixed place above the map. */
export function HoverCard({ zones }: { zones: ZoneState[] }) {
  const id = useSyncExternalStore(subscribe, () => hovered);
  const z = id ? zones.find((x) => x.id === id) : null;
  if (!z) return null;
  const next = z.predictions?.[0];
  return (
    <div className="glass px-3 py-1.5 text-[12px] leading-snug" role="status" aria-live="polite">
      <div>
        <strong>{z.short_name}</strong> <span className="text-[var(--faint)]">· {z.id}</span>
        <span className="mx-1.5 text-[var(--faint)]">·</span>
        <span style={{ color: MAP_STATUS[z.status] }}>{STATUS_META[z.status].word}</span>
      </div>
      {next && (
        <div style={{ color: FORECAST_COLOR }}>
          Next: {next.label} · {CHANCE_WORD[next.likelihood].toLowerCase()}
        </div>
      )}
    </div>
  );
}
