import { BarChart3 } from "lucide-react";
import type { CityState, TimelineEntry } from "../../types";
import { AlertsList } from "../AlertsList";
import { EventTicker } from "../EventTicker";
import { PulseTimeline } from "../PulseTimeline";
import { SummaryPanel } from "../SummaryPanel";
import { Drawer } from "./Drawer";

interface Props {
  state: CityState;
  timeline: TimelineEntry[];
  now: number;
  onSelectZone: (id: string) => void;
  onClose: () => void;
}

/** The analysis layer for people who want more than the map: full summary, agent log, history. */
export function InsightsDrawer({ state, timeline, now, onSelectZone, onClose }: Props) {
  return (
    <Drawer side="left" title="Insights" subtitle="Plain-language summary, monitoring agent and recent history."
      icon={<BarChart3 size={18} className="mt-0.5 text-[var(--pulse)]" aria-hidden />} onClose={onClose}>
      <div className="space-y-3 p-3">
        <SummaryPanel summary={state.summary} />
        <AlertsList alerts={state.alerts} now={now} onSelectZone={onSelectZone} />
        {state.mode !== "replay" && <PulseTimeline timeline={timeline} zones={state.zones} onSelectZone={onSelectZone} />}
        <div className="h-[340px]">
          <EventTicker events={state.ticker} onSelectZone={onSelectZone} />
        </div>
      </div>
    </Drawer>
  );
}
