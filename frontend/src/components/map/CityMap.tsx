import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import {
  CircleMarker, MapContainer, Marker, Polyline, Rectangle, TileLayer, Tooltip, useMap, useMapEvents, ZoomControl,
} from "react-leaflet";
import type { IncidentView, MapInfo, Road, Sensor, ZoneBoundary, ZoneState } from "../../types";
import { clockTime, num, pct } from "../../utils/format";
import { scatterInRect, type LatLon } from "../../utils/geo";
import { hotspots, parseRef, refOf, SIZE } from "../../utils/grid";
import { STATUS_META } from "../../utils/status";
import { HAZE, INCIDENT_KINDS, MAP_STATUS, MINOR_REPORT, RAIN, RAIN_LIGHT, SENSOR_COLORS, TRAFFIC_HOT, TRAFFIC_WARM } from "./mapColors";
import { airIcon, districtIcon, gridRefIcon, hotspotLabelIcon, incidentIcon, placeLabelIcon } from "./markers";

export interface MapLayers {
  rain: boolean;
  traffic: boolean;
  reports: boolean;
  air: boolean;
  sensors: boolean;
}

interface Props {
  boundaries: ZoneBoundary[];
  mapInfo: MapInfo | null;
  zones: ZoneState[];
  sensors: Sensor[];
  layers: MapLayers;
  selectedZone: string | null;
  panelOpen: boolean;
  onSelectZone: (id: string | null) => void;
}

type Bounds = [LatLon, LatLon];
type Grid = MapInfo["grid"];

const JAIPUR: LatLon = [26.895, 75.805];
const SMALL = typeof window !== "undefined" && window.innerWidth < 640;

function blockBounds(g: Grid, id: string): Bounds {
  const { row, col } = parseRef(id);
  const dLat = (g.north - g.south) / g.rows, dLon = (g.east - g.west) / g.cols;
  return [[g.north - (row + 1) * dLat, g.west + col * dLon], [g.north - row * dLat, g.west + (col + 1) * dLon]];
}

function blockAt(g: Grid, lat: number, lon: number): string | null {
  const row = Math.floor((g.north - lat) / ((g.north - g.south) / g.rows));
  const col = Math.floor((lon - g.west) / ((g.east - g.west) / g.cols));
  return row >= 0 && col >= 0 && row < SIZE && col < SIZE ? refOf(row, col) : null;
}

/** Keep the previous value while its content is unchanged, so memoised layers skip re-rendering on polls. */
function useStable<T>(value: T): T {
  const ref = useRef<{ key: string; value: T } | null>(null);
  const key = JSON.stringify(value);
  if (!ref.current || ref.current.key !== key) ref.current = { key, value };
  return ref.current.value;
}

/** Frame the whole city, or — when a block is selected — that block and its neighbours beside the panel. */
function Framing({ grid, selectedZone, panelOpen }: { grid: Grid; selectedZone: string | null; panelOpen: boolean }) {
  const map = useMap();
  useEffect(() => {
    const wide = map.getSize().x >= 900;
    if (selectedZone) {
      map.flyToBounds(L.latLngBounds(blockBounds(grid, selectedZone)).pad(1.3), {
        paddingTopLeft: [40, 80],
        paddingBottomRight: [wide && panelOpen ? 420 : 40, SMALL && panelOpen ? 300 : 40],
        maxZoom: 14.5,
        duration: 0.6,
      });
    } else {
      map.flyToBounds([[grid.south, grid.west], [grid.north, grid.east]], {
        paddingTopLeft: [36, 118],
        paddingBottomRight: [20, 24],
        duration: 0.6,
      });
    }
  }, [grid, selectedZone, panelOpen, map]);
  return null;
}

// ------------------------------------------------------------------ grid

/** District lines (5 × 5) are clear; block lines (3 × 3 inside each) are faint. Drawn once. */
const GridLines = memo(function GridLines({ grid }: { grid: Grid }) {
  const lines = useMemo(() => {
    const out: { path: LatLon[]; district: boolean }[] = [];
    const dLat = (grid.north - grid.south) / grid.rows, dLon = (grid.east - grid.west) / grid.cols;
    for (let i = 0; i <= grid.rows; i++) {
      const lat = grid.north - i * dLat;
      out.push({ path: [[lat, grid.west], [lat, grid.east]], district: i % grid.blocks === 0 });
    }
    for (let j = 0; j <= grid.cols; j++) {
      const lon = grid.west + j * dLon;
      out.push({ path: [[grid.north, lon], [grid.south, lon]], district: j % grid.blocks === 0 });
    }
    return out;
  }, [grid]);
  return (
    <>
      {lines.map((l, i) => (
        <Polyline key={i} positions={l.path} interactive={false}
          pathOptions={l.district ? { color: "#cbd5e1", weight: 1.3, opacity: 0.5 } : { color: "#a5b4c8", weight: 0.7, opacity: 0.26 }} />
      ))}
    </>
  );
});

/** Soft tint on unusual blocks only; normal blocks stay clear so the map shows through. */
const BlockTints = memo(function BlockTints({ grid, tints, selected }: {
  grid: Grid; tints: { id: string; status: "YELLOW" | "RED" }[]; selected: string | null;
}) {
  return (
    <>
      {tints.map(({ id, status }) => (
        <Rectangle key={id} bounds={blockBounds(grid, id)} interactive={false}
          pathOptions={status === "RED"
            ? { color: MAP_STATUS.RED, weight: 1.2, opacity: 0.75, fillColor: MAP_STATUS.RED, fillOpacity: 0.15 }
            : { color: MAP_STATUS.YELLOW, weight: 1, opacity: 0.5, fillColor: MAP_STATUS.YELLOW, fillOpacity: 0.08 }} />
      ))}
      {selected && (
        <Rectangle bounds={blockBounds(grid, selected)} interactive={false}
          pathOptions={{ color: "#e8eef5", weight: 2, opacity: 0.95, fill: false }} />
      )}
    </>
  );
});

/** Clicks and hover are resolved by grid arithmetic — no 225 interactive shapes. */
function GridEvents({ grid, zones, onSelectZone }: { grid: Grid; zones: ZoneState[]; onSelectZone: (id: string) => void }) {
  const [hover, setHover] = useState<string | null>(null);
  useMapEvents({
    click: (e) => {
      const id = blockAt(grid, e.latlng.lat, e.latlng.lng);
      if (id) onSelectZone(id);
    },
    mousemove: (e) => {
      if (SMALL) return;
      const id = blockAt(grid, e.latlng.lat, e.latlng.lng);
      setHover((cur) => (cur === id ? cur : id));
    },
    mouseout: () => setHover(null),
    zoomstart: () => setHover(null),
  });
  const z = hover ? zones.find((x) => x.id === hover) : null;
  if (!z) return null;
  return (
    <Rectangle bounds={blockBounds(grid, z.id)} interactive={false}
      pathOptions={{ color: "#e8eef5", weight: 1, opacity: 0.55, fill: false }}>
      <Tooltip className="cp-tooltip" permanent direction="top" offset={[0, -4]}>
        <strong>{z.short_name}</strong> <span style={{ color: "#94a3b8" }}>· {z.id}</span>
        <br />
        <span style={{ color: MAP_STATUS[z.status] }}>{STATUS_META[z.status].word}</span>
      </Tooltip>
    </Rectangle>
  );
}

/** Column letters and row numbers for the districts, like a paper map. */
const GridRefs = memo(function GridRefs({ grid }: { grid: Grid }) {
  const dLat = (grid.north - grid.south) / grid.districts, dLon = (grid.east - grid.west) / grid.districts;
  return (
    <>
      {[...grid.col_letters].map((ch, c) => (
        <Marker key={`c${ch}`} position={[grid.north + dLat * 0.1, grid.west + dLon * (c + 0.5)]} icon={gridRefIcon(ch)} interactive={false} keyboard={false} />
      ))}
      {Array.from({ length: grid.districts }, (_, r) => (
        <Marker key={`r${r}`} position={[grid.north - dLat * (r + 0.5), grid.west - dLon * 0.08]} icon={gridRefIcon(String(r + 1))} interactive={false} keyboard={false} />
      ))}
    </>
  );
});

/** District names, once the map is zoomed in enough for them not to crowd it. */
function DistrictNames({ grid, names }: { grid: Grid; names: [string, string][] }) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) });
  if (zoom < 12.5) return null;
  const dLat = (grid.north - grid.south) / grid.districts, dLon = (grid.east - grid.west) / grid.districts;
  return (
    <>
      {names.map(([ref, name]) => {
        const c = ref.charCodeAt(0) - 65, r = Number(ref[1]) - 1;
        return <Marker key={ref} position={[grid.north - dLat * r, grid.west + dLon * c]} icon={districtIcon(ref, name)} interactive={false} keyboard={false} />;
      })}
    </>
  );
}

// ------------------------------------------------------------------ layers

const RainLayer = memo(function RainLayer({ grid, rain }: { grid: Grid; rain: { id: string; mm: number }[] }) {
  return (
    <>
      {rain.map(({ id, mm }) => {
        const b = blockBounds(grid, id);
        const ring: LatLon[] = [b[0], [b[0][0], b[1][1]], b[1], [b[1][0], b[0][1]]];
        const { row, col } = parseRef(id);
        const drops = scatterInRect(ring, Math.max(2, Math.min(10, Math.round(mm * 0.4))), row * 97 + col * 13 + 11);
        return (
          <FragmentGroup key={id}>
            <Rectangle bounds={b} interactive={false}
              pathOptions={{ stroke: false, fillColor: RAIN, fillOpacity: Math.min(0.03 + mm / 300, 0.12) }} />
            {drops.map((p, i) => (
              <CircleMarker key={i} center={p} radius={1.8 + (i % 3) * 0.8} interactive={false}
                pathOptions={{ stroke: false, fillColor: i % 3 === 0 ? RAIN : RAIN_LIGHT, fillOpacity: 0.85 }} />
            ))}
          </FragmentGroup>
        );
      })}
    </>
  );
});

/** Congestion drawn on Jaipur's real main roads, coloured by each block's traffic vs normal. */
const TrafficLayer = memo(function TrafficLayer({ roads, traffic, names }: {
  roads: Road[]; traffic: { id: string; dev: number }[]; names: Record<string, string>;
}) {
  const byCell = useMemo(() => {
    const out: Record<string, Road[]> = {};
    for (const r of roads) (out[r.cell] ??= []).push(r);
    return out;
  }, [roads]);
  return (
    <>
      {traffic.flatMap(({ id, dev }) => {
        const hot = dev >= 30;
        const color = hot ? TRAFFIC_HOT : TRAFFIC_WARM;
        return (byCell[id] ?? []).flatMap((road, i) => {
          const w = road.kind === "major" ? (hot ? 4 : 3) : 2.5;
          return [
            // soft glow: a wide faint stroke under the line (canvas has no CSS filters)
            <Polyline key={`${id}-g${i}`} positions={road.path} interactive={false}
              pathOptions={{ color, weight: w + 5, opacity: 0.16, lineCap: "round", lineJoin: "round" }} />,
            <Polyline key={`${id}-r${i}`} positions={road.path}
              pathOptions={{ color, weight: w, opacity: hot ? 0.92 : 0.78, lineCap: "round", lineJoin: "round" }}>
              <Tooltip className="cp-tooltip" sticky>
                <strong>{hot ? "Heavy traffic" : "Traffic building"}</strong>{road.name ? ` · ${road.name}` : ""}
                <br />
                {names[id] ?? id}: {pct(dev)} vs normal for this time of day
              </Tooltip>
            </Polyline>,
          ];
        });
      })}
    </>
  );
});

interface Cluster { key: string; kind: string; color: string; label: string; count: number; latest: string; center: LatLon; zoneId: string }

const ReportsLayer = memo(function ReportsLayer({ clusters, minor, onSelectZone }: {
  clusters: Cluster[]; minor: IncidentView[]; onSelectZone: (id: string) => void;
}) {
  return (
    <>
      {minor.map((i) => (
        <CircleMarker key={i.id} center={[i.lat, i.lon]} radius={2}
          pathOptions={{ stroke: false, fillColor: MINOR_REPORT, fillOpacity: 0.45 }}>
          <Tooltip className="cp-tooltip">{i.label} · {clockTime(i.timestamp, false)} · anonymous report</Tooltip>
        </CircleMarker>
      ))}
      {clusters.map((c) => (
        <Marker key={c.key} position={c.center} icon={incidentIcon(c.kind, c.color, c.count)}
          eventHandlers={{ click: () => onSelectZone(c.zoneId) }} zIndexOffset={500} title={`${c.count} × ${c.label}`}>
          <Tooltip className="cp-tooltip" direction="top" offset={[0, -14]}>
            <strong>{c.count} × {c.label}</strong>
            <br />
            latest {clockTime(c.latest, false)} · anonymous reports
          </Tooltip>
        </Marker>
      ))}
    </>
  );
});

const AirLayer = memo(function AirLayer({ grid, air, badges }: {
  grid: Grid; air: string[]; badges: { id: string; aqi: number; at: LatLon }[];
}) {
  return (
    <>
      {air.map((id) => (
        <Rectangle key={id} bounds={blockBounds(grid, id)} interactive={false}
          pathOptions={{ stroke: false, fillColor: HAZE, fillOpacity: 0.14 }} />
      ))}
      {badges.map((b) => <Marker key={b.id} position={b.at} icon={airIcon(b.aqi)} interactive={false} />)}
    </>
  );
});

const SENSOR_LABEL: Record<string, string> = {
  traffic: "Traffic sensor", rain_gauge: "Rain gauge", air_quality: "Air monitor", water_level: "Water-level sensor",
};

function sensorHtml(s: Sensor): string {
  const rows = Object.entries(s.values)
    .filter(([k]) => ["congestion_pct", "rain_mm_h", "aqi", "water_level_cm"].includes(k))
    .map(([k, v]) => `<div>${k.replace(/_/g, " ")}: ${num(v.value)} ${v.unit}</div>`).join("");
  return `<strong>${SENSOR_LABEL[s.kind]}</strong> <span style="color:#94a3b8">${s.id}</span>${rows}`;
}

/** Up to ~1,100 sensor points; tooltips are created only when hovered. */
const SensorLayer = memo(function SensorLayer({ sensors }: { sensors: Sensor[] }) {
  return (
    <>
      {sensors.map((s) => (
        <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={2.2}
          pathOptions={{ color: SENSOR_COLORS[s.kind], weight: 1.1, fillColor: "#05080d", fillOpacity: 1, opacity: 0.75 }}
          eventHandlers={{ mouseover: (e) => e.target.bindTooltip(sensorHtml(s), { className: "cp-tooltip", direction: "top" }).openTooltip() }} />
      ))}
    </>
  );
});

interface Label { id: string; at: LatLon; lead: ZoneState; cells: number; red: boolean }

/** One label per hotspot (not per block), plus a small name tag for the selected block. */
const Labels = memo(function Labels({ labels, selected, selectedZone, onSelectZone }: {
  labels: Label[]; selected: ZoneState | null; selectedZone: string | null; onSelectZone: (id: string) => void;
}) {
  return (
    <>
      {labels.map((l) => (
        <Marker key={`label-${l.id}`} position={l.at} icon={hotspotLabelIcon(l.lead, l.cells, selectedZone === l.id, SMALL)}
          eventHandlers={{ click: () => onSelectZone(l.id) }} keyboard
          title={`${l.lead.name}: ${l.lead.status_label}. ${l.lead.headline}`} alt={`${l.lead.name}: ${l.lead.status_label}`}
          zIndexOffset={l.red ? 2000 : 1500} />
      ))}
      {selected && <Marker position={selected.anchor} icon={placeLabelIcon(selected)} interactive={false} zIndexOffset={1000} />}
    </>
  );
});

function FragmentGroup({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

// -------------------------------------------------------------------- map

export function CityMap({ boundaries, mapInfo, zones, sensors, layers, selectedZone, panelOpen, onSelectZone }: Props) {
  const grid = mapInfo?.grid ?? null;

  // Everything drawn is derived into small plain lists; each stays the same object while its
  // content is unchanged, so a 3-second poll that changes nothing visible redraws nothing.
  const tints = useStable(zones.filter((z) => z.status !== "GREEN").map((z) => ({ id: z.id, status: z.status as "YELLOW" | "RED" })));
  const rain = useStable(zones.filter((z) => (z.metrics.rain_mm_h?.current ?? 0) >= 1)
    .map((z) => ({ id: z.id, mm: Math.round(z.metrics.rain_mm_h.current ?? 0) })));
  const traffic = useStable(zones.filter((z) => z.metrics.congestion_pct?.available && (z.metrics.congestion_pct.deviation_pct ?? 0) >= 10)
    .map((z) => ({ id: z.id, dev: Math.round(z.metrics.congestion_pct.deviation_pct ?? 0) })));
  const names = useStable(Object.fromEntries(traffic.map((t) => [t.id, zones.find((z) => z.id === t.id)?.short_name ?? t.id])));
  const reportData = useMemo(() => {
    const groups = new Map<string, Cluster & { lat: number; lon: number }>();
    const minor: IncidentView[] = [];
    for (const z of zones) {
      for (const inc of z.recent_incidents) {
        const meta = INCIDENT_KINDS[inc.category];
        if (!meta || !z.metrics[meta.metric]?.is_anomaly) {
          minor.push(inc);
          continue;
        }
        const key = `${z.id}|${meta.kind}`;
        const g = groups.get(key) ?? { key, kind: meta.kind, color: meta.color, label: meta.label, count: 0, latest: inc.timestamp,
          center: [0, 0] as LatLon, zoneId: z.id, lat: 0, lon: 0 };
        g.count++;
        g.lat += inc.lat;
        g.lon += inc.lon;
        if (inc.timestamp > g.latest) g.latest = inc.timestamp;
        groups.set(key, g);
      }
    }
    const clusters: Cluster[] = [...groups.values()].map(({ lat, lon, ...g }) => ({
      ...g, center: [+(lat / g.count).toFixed(4), +(lon / g.count).toFixed(4)] as LatLon,
    }));
    return { clusters, minor };
  }, [zones]);
  const reports = useStable(reportData);
  const spots = useMemo(() => hotspots(zones), [zones]);
  const air = useStable(zones.filter((z) => z.metrics.aqi?.is_anomaly && z.metrics.aqi.current !== null).map((z) => z.id));
  const badges = useStable(spots.flatMap((h) => {
    const bad = h.cells.filter((z) => z.metrics.aqi?.is_anomaly && z.metrics.aqi.current !== null)
      .sort((a, b) => (b.metrics.aqi.current ?? 0) - (a.metrics.aqi.current ?? 0));
    return bad.slice(0, 1).map((z) => ({ id: z.id, aqi: Math.round(z.metrics.aqi.current ?? 0), at: [z.anchor[0] - 0.009, z.anchor[1]] as LatLon }));
  }));
  // Labels are ~3 blocks wide: when two hotspots are close, move the less important one down.
  const labelData = useMemo(() => {
    const placed: { row: number; col: number }[] = [];
    return spots.map((h) => {
      const { row, col } = parseRef(h.lead.id);
      const clash = placed.some((p) => Math.abs(p.row - row) <= 1 && Math.abs(p.col - col) <= 4);
      placed.push({ row: clash ? row + 2 : row, col });
      return {
        id: h.lead.id, at: (clash ? [h.lead.anchor[0] - 0.0135 * 1.5, h.lead.anchor[1]] : h.lead.anchor) as LatLon,
        lead: h.lead, cells: h.cells.length, red: h.status === "RED",
      };
    });
  }, [spots]);
  const labels = useStable(labelData.map((l) => ({ ...l, lead: { ...l.lead, metrics: {}, recent_incidents: [] } as unknown as ZoneState })));
  const leadIds = new Set(labels.map((l) => l.id));
  const selectedState = selectedZone && !leadIds.has(selectedZone) ? zones.find((z) => z.id === selectedZone) ?? null : null;
  const selected = useStable(selectedState ? ({ ...selectedState, metrics: {}, recent_incidents: [] } as unknown as ZoneState) : null);
  const districtNames = useMemo(() => {
    const seen = new Map<string, string>();
    for (const b of boundaries) if (!seen.has(b.district)) seen.set(b.district, b.district_name);
    return [...seen.entries()];
  }, [boundaries]);

  return (
    <MapContainer center={JAIPUR} zoom={12} zoomSnap={0.25} minZoom={10} maxZoom={16} zoomControl={false} preferCanvas
      className="h-full w-full" aria-label="Map of Jaipur: 5 by 5 districts, each split into 3 by 3 blocks">
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19} updateWhenZooming={false} keepBuffer={3}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
      <ZoomControl position="bottomleft" />
      {grid && (
        <>
          <Framing grid={grid} selectedZone={selectedZone} panelOpen={panelOpen} />
          {layers.air && <AirLayer grid={grid} air={air} badges={badges} />}
          {layers.rain && <RainLayer grid={grid} rain={rain} />}
          <BlockTints grid={grid} tints={tints} selected={selectedZone} />
          <GridLines grid={grid} />
          <GridRefs grid={grid} />
          <DistrictNames grid={grid} names={districtNames} />
          <GridEvents grid={grid} zones={zones} onSelectZone={onSelectZone} />
          {layers.traffic && mapInfo && <TrafficLayer roads={mapInfo.roads} traffic={traffic} names={names} />}
        </>
      )}
      {layers.sensors && <SensorLayer sensors={sensors} />}
      {layers.reports && <ReportsLayer clusters={reports.clusters} minor={reports.minor} onSelectZone={onSelectZone} />}
      <Labels labels={labels} selected={selected} selectedZone={selectedZone} onSelectZone={onSelectZone} />
    </MapContainer>
  );
}
