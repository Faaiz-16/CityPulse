import { WifiOff } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { AlertsCard } from "./components/AlertsCard";
import { DemoPill } from "./components/DemoPill";
import { DemoDrawer } from "./components/drawers/DemoDrawer";
import { InsightsDrawer } from "./components/drawers/InsightsDrawer";
import { Header, type Mode } from "./components/Header";
import { CityMap, type MapLayers } from "./components/map/CityMap";
import { LayerToggles, PulseLegend } from "./components/map/MapControls";
import { ReplayBar } from "./components/ReplayBar";
import { ZonePanel } from "./components/zone/ZonePanel";
import { useNow, usePolling } from "./hooks/usePolling";
import { useReplay } from "./hooks/useReplay";
import { api } from "./services/api";
import { deriveAlerts, type MapAlert } from "./utils/alerts";
import { clockTime } from "./utils/format";

const POLL_MS = 3000;

// Deep links: ?zone=C2-9 opens a block; ?replay=1&frame=30 opens the replay at a recorded minute.
const params = new URLSearchParams(window.location.search);
const INITIAL_ZONE = /^[A-E][1-5]-[1-9]$/.test(params.get("zone") ?? "") ? params.get("zone") : null;
const INITIAL_REPLAY = params.get("replay") === "1";
const INITIAL_FRAME = Number(params.get("frame") ?? 0) || 0;
const INITIAL_DRAWER = params.get("demo") === "1" ? "demo" : params.get("insights") === "1" ? "insights" : null;

const SMALL_SCREEN = window.innerWidth < 640;

type LeftDrawer = "demo" | "insights" | null;

export default function App() {
  const dashboard = usePolling(api.dashboard, POLL_MS);
  const boundaries = usePolling(api.zones, 60000);
  const mapInfo = usePolling(api.map, 3_600_000); // grid + main roads: static
  const timeline = usePolling(api.timeline, 15000);
  const [layers, setLayers] = useState<MapLayers>({ rain: true, traffic: true, reports: true, air: true, sensors: false });
  const replay = useReplay(INITIAL_REPLAY ? INITIAL_FRAME : null);
  const sensors = usePolling(layers.sensors && !replay.active ? api.sensors : null, 5000);
  const [selectedZone, setSelectedZone] = useState<string | null>(INITIAL_ZONE);
  const [drawer, setDrawer] = useState<LeftDrawer>(INITIAL_DRAWER);
  const wallNow = useNow();

  const refreshAll = useCallback(() => {
    dashboard.refresh();
    timeline.refresh();
  }, [dashboard, timeline]);
  const act = useCallback(async (fn: () => Promise<{ message: string }>) => {
    try {
      await fn();
    } finally {
      refreshAll();
    }
  }, [refreshAll]);
  const closeZone = useCallback(() => setSelectedZone(null), []);
  const closeDrawer = useCallback(() => setDrawer(null), []);
  // A demo situation is ready: close the drawer and take the viewer straight to it.
  const showSituation = useCallback((zoneId: string | null) => {
    setDrawer(null);
    setSelectedZone(zoneId);
  }, []);
  const { start: startReplayRaw } = replay;
  const startReplay = useCallback(() => {
    setDrawer(null);
    startReplayRaw(0, true);
  }, [startReplayRaw]);

  // In replay mode every panel reads the recorded frame instead of the live state.
  const inReplay = replay.active && !!replay.state;
  const state = inReplay ? replay.state : dashboard.data;
  const replayIndex = replay.index;
  const loadDetail = useMemo(
    () => (inReplay ? (id: string) => api.replayZone(replayIndex, id) : api.zone),
    [inReplay, replayIndex],
  );
  const alerts = useMemo(() => (state ? deriveAlerts(state) : []), [state]);
  const districtNames = useMemo(
    () => Object.fromEntries((boundaries.data ?? []).map((b) => [b.district, b.district_name])) as Record<string, string>,
    [boundaries.data],
  );

  if (!state || (replay.active && !replay.state)) {
    return (
      <div className="grid h-full place-items-center p-6 text-center">
        <div>
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-[var(--line)] border-t-[var(--pulse)]" aria-hidden />
          <p className="font-semibold">{replay.active ? "Preparing the recorded storm replay…" : "Connecting to CityPulse…"}</p>
          {dashboard.error && !replay.active && (
            <p className="mt-2 max-w-sm text-sm text-[var(--muted)]">
              The CityPulse server isn't reachable yet — retrying every few seconds.
            </p>
          )}
        </div>
      </div>
    );
  }

  const sim = state.simulation;
  const demoActive = !inReplay && (!!sim.scenario || sim.active_events.length > 0);
  const mode: Mode = inReplay ? "REPLAY" : demoActive ? "DEMO" : "LIVE";
  const now = inReplay ? new Date(state.generated_at).getTime() : wallNow;
  const zone = selectedZone ? state.zones.find((z) => z.id === selectedZone) ?? null : null;
  const offline = !inReplay && !!dashboard.error;

  const onAlert = (a: MapAlert) => (a.zoneId ? setSelectedZone(a.zoneId) : setDrawer("insights"));
  const toggle = (d: Exclude<LeftDrawer, null>) => setDrawer((cur) => (cur === d ? null : d));

  return (
    <div className="relative h-full w-full overflow-hidden">
      {/* The map is the hero: full-bleed, everything else floats over it. */}
      <div className="absolute inset-0">
        <CityMap boundaries={boundaries.data ?? []} mapInfo={mapInfo.data} zones={state.zones} sensors={sensors.data ?? []} layers={layers}
          selectedZone={selectedZone} panelOpen={!!zone} onSelectZone={setSelectedZone} />
      </div>
      <div className="map-vignette absolute inset-0 z-[400]" aria-hidden />

      <div className="pointer-events-none absolute inset-0 z-[1000] p-3">
        <div className="absolute left-3 right-3 top-3">
          <Header state={state} now={now} mode={mode} offline={offline} demoOpen={drawer === "demo"} insightsOpen={drawer === "insights"}
            onDemo={() => toggle("demo")} onInsights={() => toggle("insights")} onReplay={startReplay} />
        </div>

        {/* second row: layers (left), demo status (centre) */}
        {!drawer && (
          <div className="absolute left-3 top-[76px]">
            <LayerToggles layers={layers} onChange={setLayers} />
          </div>
        )}
        {demoActive && drawer !== "demo" && (
          <div className="absolute left-1/2 top-[76px] hidden -translate-x-1/2 md:block">
            <DemoPill sim={sim} act={act} onOpen={() => setDrawer("demo")}
              place={state.zones.find((z) => z.id === sim.scenario?.focus_zone)?.short_name} />
          </div>
        )}
        {offline && (
          <div className="glass absolute left-1/2 top-[128px] flex -translate-x-1/2 items-center gap-2 px-3 py-1.5 text-[12.5px] text-[var(--bad)]" role="alert">
            <WifiOff size={14} aria-hidden /> Connection lost — showing the last update from {clockTime(state.generated_at)}. Retrying…
          </div>
        )}
        {replay.error && (
          <div className="glass absolute left-1/2 top-[128px] -translate-x-1/2 px-3 py-1.5 text-[12.5px] text-[var(--warn)]" role="alert">
            Replay: {replay.error}
          </div>
        )}

        {/* left drawers */}
        {drawer && (
          <div className="absolute bottom-3 left-3 top-[76px] flex max-w-[calc(100%-24px)]">
            {drawer === "demo" && !inReplay && (
              <DemoDrawer sim={sim} zones={state.zones} feeds={state.feeds} onClose={closeDrawer} onChanged={refreshAll}
                onStartReplay={startReplay} onShow={showSituation} districtNames={districtNames} />
            )}
            {drawer === "insights" && (
              <InsightsDrawer state={state} timeline={timeline.data ?? []} now={now}
                onSelectZone={(id) => setSelectedZone(id)} onClose={closeDrawer} />
            )}
          </div>
        )}

        {/* right: the zone story, only when asked for */}
        {zone && (
          <div className="absolute bottom-3 right-3 top-[76px] z-10 flex max-w-[calc(100%-24px)]">
            <ZonePanel key={zone.id} zone={zone} feeds={state.feeds} now={now} loadDetail={loadDetail} onClose={closeZone}
              district={districtNames[zone.id.slice(0, 2)]} />
          </div>
        )}

        {/* bottom: legend (left), replay controls, alerts (right) */}
        {!drawer && !inReplay && (
          <div className="absolute bottom-3 left-[58px] hidden md:block">
            <PulseLegend />
          </div>
        )}
        {inReplay && (
          <div className={`absolute bottom-3 left-3 ${zone ? "right-[468px]" : "right-3 lg:right-[344px]"}`}>
            <ReplayBar replay={replay} zones={state.zones} />
          </div>
        )}
        {!zone && (
          <div className={`absolute bottom-3 right-3 w-[320px] max-w-[calc(100%-24px)] ${drawer ? "hidden lg:block" : ""}`}>
            <AlertsCard alerts={alerts} max={SMALL_SCREEN ? 2 : 4} onSelect={onAlert} onMore={() => setDrawer("insights")} />
          </div>
        )}
      </div>
    </div>
  );
}
