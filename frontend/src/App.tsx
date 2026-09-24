import { FlaskConical, History, WifiOff } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { AlertsList } from "./components/AlertsList";
import { DemoPanel } from "./components/DemoPanel";
import { EventTicker } from "./components/EventTicker";
import { CityMap, type MapLayers } from "./components/map/CityMap";
import { LayerToggles, MapLegend } from "./components/map/MapOverlays";
import { PulseTimeline } from "./components/PulseTimeline";
import { ReplayBar } from "./components/ReplayBar";
import { SummaryPanel } from "./components/SummaryPanel";
import { TopBar } from "./components/TopBar";
import { ZonePanel } from "./components/zone/ZonePanel";
import { useNow, usePolling } from "./hooks/usePolling";
import { useReplay } from "./hooks/useReplay";
import { api } from "./services/api";
import { clockTime } from "./utils/format";

const POLL_MS = 3000;

export default function App() {
  const dashboard = usePolling(api.dashboard, POLL_MS);
  const boundaries = usePolling(api.zones, 60000);
  const timeline = usePolling(api.timeline, 15000);
  const [layers, setLayers] = useState<MapLayers>({ rain: true, reports: true, sensors: false });
  const replay = useReplay();
  const sensors = usePolling(layers.sensors && !replay.active ? api.sensors : null, 5000);
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const [demoOpen, setDemoOpen] = useState(false);
  const wallNow = useNow();

  const refreshAll = useCallback(() => {
    dashboard.refresh();
    timeline.refresh();
  }, [dashboard, timeline]);
  const closeZone = useCallback(() => setSelectedZone(null), []);
  const { start: startReplayRaw } = replay;
  const startReplay = useCallback(() => {
    setDemoOpen(false);
    startReplayRaw();
  }, [startReplayRaw]);

  // In replay mode every panel reads the recorded frame instead of the live state.
  const inReplay = replay.active && !!replay.state;
  const state = inReplay ? replay.state : dashboard.data;
  const replayIndex = replay.index;
  const loadDetail = useMemo(
    () => (inReplay ? (id: string) => api.replayZone(replayIndex, id) : api.zone),
    [inReplay, replayIndex],
  );

  if (!state || (replay.active && !replay.state)) {
    return (
      <div className="grid h-full place-items-center p-6 text-center">
        <div>
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-[var(--line)] border-t-[var(--pulse)]" aria-hidden />
          <p className="font-semibold">{replay.active ? "Preparing the recorded storm replay…" : "Connecting to CityPulse…"}</p>
          {dashboard.error && !replay.active && (
            <p className="mt-2 max-w-sm text-sm text-[var(--muted)]">
              {dashboard.error} Make sure the backend is running on port 8000 — retrying every few seconds.
            </p>
          )}
        </div>
      </div>
    );
  }

  // Relative times ("opened 2 min ago") are measured against the replay clock in replay mode.
  const now = inReplay ? new Date(state.generated_at).getTime() : wallNow;
  const zone = selectedZone ? state.zones.find((z) => z.id === selectedZone) ?? null : null;

  return (
    <div className="flex h-full flex-col">
      <TopBar state={state} now={now} connectionError={inReplay ? null : dashboard.error} />

      {dashboard.error && !inReplay && (
        <div className="flex items-center gap-2 px-4 py-1.5 text-[12.5px]" style={{ background: "var(--bad-soft)", color: "var(--bad)" }} role="alert">
          <WifiOff size={14} aria-hidden />
          Connection to the CityPulse server lost — showing the last update from {clockTime(state.generated_at)}. Retrying…
        </div>
      )}
      {replay.error && (
        <div className="px-4 py-1.5 text-[12.5px]" style={{ background: "var(--warn-soft)", color: "var(--warn)" }} role="alert">
          Replay: {replay.error}
        </div>
      )}

      <main className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Left: the 10-second read in words */}
        <div className="scroll-thin order-2 flex flex-col gap-3 overflow-y-auto p-3 lg:order-1 lg:w-[380px] lg:shrink-0 xl:w-[400px]">
          {demoOpen && !inReplay && (
            <DemoPanel
              sim={state.simulation}
              zones={state.zones}
              feeds={state.feeds}
              selectedZone={selectedZone}
              onClose={() => setDemoOpen(false)}
              onChanged={refreshAll}
              onStartReplay={startReplay}
            />
          )}
          <SummaryPanel summary={state.summary} />
          <AlertsList alerts={state.alerts} now={now} onSelectZone={setSelectedZone} />
          {!inReplay && (
            <div className="lg:hidden">
              <PulseTimeline timeline={timeline.data ?? []} zones={state.zones} onSelectZone={setSelectedZone} />
            </div>
          )}
          <div className="flex min-h-[220px] flex-1 flex-col">
            <EventTicker events={state.ticker} onSelectZone={setSelectedZone} />
          </div>
        </div>

        {/* Map: the hero */}
        <div className="relative order-1 h-[62vh] min-h-[380px] lg:order-2 lg:h-auto lg:flex-1">
          <CityMap
            boundaries={boundaries.data ?? []}
            zones={state.zones}
            sensors={sensors.data ?? []}
            layers={layers}
            selectedZone={selectedZone}
            onSelectZone={setSelectedZone}
          />

          <div className="pointer-events-none absolute inset-0 z-[1000] flex flex-col p-3">
            <div className="flex items-start justify-between gap-2">
              <LayerToggles layers={layers} onChange={setLayers} />
              {!replay.active && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={startReplay}
                    className="panel pointer-events-auto flex items-center gap-1.5 px-3 py-2 text-xs font-semibold hover:bg-white/5"
                    title="Replay a recorded storm through the same analysis pipeline"
                  >
                    <History size={14} className="text-[#c084fc]" aria-hidden /> Replay<span className="hidden sm:inline"> storm</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setDemoOpen(!demoOpen)}
                    aria-expanded={demoOpen}
                    className="panel pointer-events-auto flex items-center gap-1.5 px-3 py-2 text-xs font-semibold hover:bg-white/5"
                  >
                    <FlaskConical size={14} className="text-[var(--pulse)]" aria-hidden /> Demo<span className="hidden sm:inline"> controls</span>
                  </button>
                </div>
              )}
            </div>

            <div className="flex-1" />

            {inReplay ? (
              <div className={`pt-3 ${zone ? "lg:mr-[472px]" : ""}`}>
                <ReplayBar replay={replay} zones={state.zones} />
              </div>
            ) : (
              <div className="hidden items-end justify-between gap-3 pt-3 md:flex">
                <MapLegend />
                {!zone && (
                  <div className="hidden w-[420px] lg:block">
                    <PulseTimeline timeline={timeline.data ?? []} zones={state.zones} onSelectZone={setSelectedZone} />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Investigation panel: full map height on the right (the replay bar shrinks beside it) */}
          {zone && (
            <div className="absolute bottom-3 right-3 top-16 z-[1001] hidden w-[460px] lg:flex">
              <ZonePanel zone={zone} feeds={state.feeds} now={now} loadDetail={loadDetail} onClose={closeZone} />
            </div>
          )}
        </div>
      </main>

      {/* On small screens the zone panel becomes a full-screen sheet */}
      {zone && (
        <div className="fixed inset-0 z-[1300] flex bg-black/60 p-2 lg:hidden">
          <ZonePanel zone={zone} feeds={state.feeds} now={now} loadDetail={loadDetail} onClose={closeZone} />
        </div>
      )}
    </div>
  );
}
