import { FlaskConical } from "lucide-react";
import type { SimulationStatus } from "../types";
import { PlaybackControls } from "./drawers/DemoDrawer";

type Act = (fn: () => Promise<{ message: string }>) => Promise<void>;

/** While a demo runs and the drawer is closed: what's playing, progress, pause/speed. */
export function DemoPill({ sim, place, act, onOpen }: { sim: SimulationStatus; place?: string; act: Act; onOpen: () => void }) {
  const sc = sim.scenario;
  const done = sc ? sc.stages.filter((s) => s.reached_at).length : 0;
  return (
    <div className="glass pointer-events-auto flex items-center gap-2.5 py-1.5 pl-3 pr-1.5 text-[12px]" role="status">
      <button type="button" onClick={onOpen} className="flex items-center gap-2 text-left" title="Open demo controls">
        <FlaskConical size={14} className="text-[var(--pulse)]" aria-hidden />
        <span className="font-bold tracking-wide text-[var(--pulse)]">DEMO</span>
        {sc ? (
          <>
            <span className="font-semibold">{sc.name}</span>
            {place && <span className="text-[var(--muted)]">· {place}</span>}
            {!sc.complete && (
              <span className="hidden text-[var(--muted)] sm:inline">· {done}/{sc.stages.length} detected{sim.clock.paused ? " · paused" : ""}</span>
            )}
          </>
        ) : (
          <span className="text-[var(--muted)]">{sim.active_events.length} simulated event{sim.active_events.length === 1 ? "" : "s"}</span>
        )}
      </button>
      {sc && !sc.complete && <PlaybackControls sim={sim} busy={false} act={act} compact />}
    </div>
  );
}
