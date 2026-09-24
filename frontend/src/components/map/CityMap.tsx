import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { memo, useEffect, useMemo } from "react";
import { Circle, CircleMarker, MapContainer, Marker, Polygon, Polyline, TileLayer, Tooltip, useMap, ZoomControl } from "react-leaflet";
import type { IncidentView, MapInfo, Road, Sensor, ZoneBoundary, ZoneState } from "../../types";
import { clockTime, num, pct } from "../../utils/format";
import { scatterInRect, type LatLon } from "../../utils/geo";
import { hotspots, parseRef } from "../../utils/grid";
import { STATUS_META } from "../../utils/status";
import { HAZE, INCIDENT_KINDS, MAP_STATUS, MINOR_REPORT, RAIN, RAIN_LIGHT, SENSOR_COLORS, TRAFFIC_HOT, TRAFFIC_WARM } from "./mapColors";
import { airIcon, gridRefIcon, hotspotLabelIcon, incidentIcon, placeLabelIcon } from "./markers";

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

const JAIPUR: LatLon = [26.895, 75.805];
const ring = (b: ZoneBoundary): LatLon[] => b.boundary.coordinates[0].map(([lon, lat]) => [lat, lon]);
const SMALL = typeof window !== "undefined" && window.innerWidth < 640;

/** Frame the whole city, or — when an area is selected — that area and its neighbours beside the panel. */
function Framing({ boundaries, selectedZone, panelOpen }: { boundaries: ZoneBoundary[]; selectedZone: string | null; panelOpen: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!boundaries.length) return;
    const selected = boundaries.find((b) => b.id === selectedZone);
    const wide = map.getSize().x >= 900;
    if (selected) {
      // Show the neighbouring cells too, so a hotspot is seen in context.
      map.flyToBounds(L.latLngBounds(ring(selected)).pad(0.9), {
        paddingTopLeft: [40, 80],
        paddingBottomRight: [wide && panelOpen ? 420 : 40, SMALL && panelOpen ? 300 : 40],
        maxZoom: 14,
        duration: 0.7,
      });
    } else {
      map.flyToBounds(L.latLngBounds(boundaries.flatMap(ring)), {
        paddingTopLeft: [36, 118],
        paddingBottomRight: [20, 24],
        duration: 0.7,
      });
    }
  }, [boundaries, selectedZone, panelOpen, map]);
  return null;
}

// ------------------------------------------------------------------ layers

/** The 9 × 9 grid. Normal cells are just faint lines; only unusual cells get a soft tint. */
const GridCells = memo(function GridCells({ boundaries, zones, selectedZone, onSelectZone }: {
  boundaries: ZoneBoundary[]; zones: ZoneState[]; selectedZone: string | null; onSelectZone: (id: string) => void;
}) {
  const byId = useMemo(() => Object.fromEntries(zones.map((z) => [z.id, z])), [zones]);
  return (
    <>
      {boundaries.map((b) => {
        const z = byId[b.id];
        if (!z) return null;
        const color = MAP_STATUS[z.status];
        const selected = selectedZone === b.id;
        const style = {
          GREEN: { color: "#a5b4c8", weight: 0.8, opacity: 0.32, fillColor: color, fillOpacity: 0.001 },
          YELLOW: { color, weight: 1, opacity: 0.55, fillColor: color, fillOpacity: 0.07 },
          RED: { color, weight: 1.3, opacity: 0.75, fillColor: color, fillOpacity: 0.13 },
        }[z.status];
        return (
          <Polygon key={`${b.id}-${z.status}-${selected}`} positions={ring(b)}
            pathOptions={{ ...style, ...(selected ? { color: "#e8eef5", weight: 2, opacity: 0.9 } : {}),
              className: z.status === "RED" ? "cp-cell-red" : undefined }}
            eventHandlers={{ click: () => onSelectZone(b.id) }}>
            {!SMALL && (
              <Tooltip className="cp-tooltip" sticky>
                <strong>{z.short_name}</strong> <span style={{ color: "#94a3b8" }}>· {z.id}</span>
                <br />
                <span style={{ color }}>{STATUS_META[z.status].word}</span>
              </Tooltip>
            )}
          </Polygon>
        );
      })}
    </>
  );
});

/** Column letters along the top edge and row numbers down the left edge, like a paper map. */
const GridRefs = memo(function GridRefs({ mapInfo }: { mapInfo: MapInfo }) {
  const g = mapInfo.grid;
  const dLat = (g.north - g.south) / g.rows, dLon = (g.east - g.west) / g.cols;
  return (
    <>
      {[...g.col_letters].map((ch, c) => (
        <Marker key={`c${ch}`} position={[g.north + dLat * 0.18, g.west + dLon * (c + 0.5)]} icon={gridRefIcon(ch)} interactive={false} keyboard={false} />
      ))}
      {Array.from({ length: g.rows }, (_, r) => (
        <Marker key={`r${r}`} position={[g.north - dLat * (r + 0.5), g.west - dLon * 0.16]} icon={gridRefIcon(String(r + 1))} interactive={false} keyboard={false} />
      ))}
    </>
  );
});

const RainLayer = memo(function RainLayer({ boundaries, zones }: { boundaries: ZoneBoundary[]; zones: ZoneState[] }) {
  const drops = useMemo(() => {
    const out: Record<string, LatLon[]> = {};
    for (const b of boundaries) out[b.id] = scatterInRect(ring(b), 26, b.number * 97 + 11);
    return out;
  }, [boundaries]);
  return (
    <>
      {zones.map((z) => {
        const rain = z.metrics.rain_mm_h?.current ?? 0;
        if (rain < 1) return null;
        const n = Math.max(3, Math.min(26, Math.round(rain * 0.9)));
        return (
          <FragmentGroup key={`rain-${z.id}`}>
            <Circle center={z.anchor} radius={1500} interactive={false}
              pathOptions={{ stroke: false, fillColor: RAIN, fillOpacity: Math.min(0.04 + rain / 220, 0.16), className: "cp-haze" }} />
            {(drops[z.id] ?? []).slice(0, n).map((p, i) => (
              <CircleMarker key={i} center={p} radius={2 + (i % 3)} interactive={false}
                pathOptions={{ stroke: false, fillColor: i % 4 === 0 ? RAIN : RAIN_LIGHT, fillOpacity: 0.8, className: "cp-rain-drop" }} />
            ))}
          </FragmentGroup>
        );
      })}
    </>
  );
});

/** Congestion is drawn on Jaipur's real main roads, coloured by each area's traffic vs normal. */
const TrafficLayer = memo(function TrafficLayer({ roads, zones }: { roads: Road[]; zones: ZoneState[] }) {
  const byCell = useMemo(() => {
    const out: Record<string, Road[]> = {};
    for (const r of roads) (out[r.cell] ??= []).push(r);
    return out;
  }, [roads]);
  return (
    <>
      {zones.flatMap((z) => {
        const m = z.metrics.congestion_pct;
        const dev = m?.deviation_pct ?? 0;
        if (!m?.available || dev < 10) return []; // normal traffic stays in the background
        const hot = dev >= 30;
        return (byCell[z.id] ?? []).map((road, i) => (
          <Polyline key={`${z.id}-road-${i}`} positions={road.path}
            pathOptions={{ color: hot ? TRAFFIC_HOT : TRAFFIC_WARM, weight: road.kind === "major" ? (hot ? 4 : 3) : 2.5,
              opacity: hot ? 0.9 : 0.75, lineCap: "round", lineJoin: "round", className: hot ? "cp-traffic-hot" : "cp-traffic-warm" }}>
            <Tooltip className="cp-tooltip" sticky>
              <strong>{hot ? "Heavy traffic" : "Traffic building"}</strong>{road.name ? ` · ${road.name}` : ""}
              <br />
              {z.short_name}: {pct(dev)} vs normal for this time of day
            </Tooltip>
          </Polyline>
        ));
      })}
    </>
  );
});

interface Cluster { key: string; kind: string; color: string; label: string; items: IncidentView[]; center: LatLon; zoneId: string }

const ReportsLayer = memo(function ReportsLayer({ zones, onSelectZone }: { zones: ZoneState[]; onSelectZone: (id: string) => void }) {
  const { clusters, minor } = useMemo(() => {
    const groups = new Map<string, Cluster>();
    const minorDots: IncidentView[] = [];
    for (const z of zones) {
      for (const inc of z.recent_incidents) {
        const meta = INCIDENT_KINDS[inc.category];
        if (!meta || !z.metrics[meta.metric]?.is_anomaly) {
          minorDots.push(inc);
          continue;
        }
        const key = `${z.id}|${meta.kind}`;
        const g = groups.get(key) ?? { key, kind: meta.kind, color: meta.color, label: meta.label, items: [], center: [0, 0] as LatLon, zoneId: z.id };
        g.items.push(inc);
        groups.set(key, g);
      }
    }
    for (const g of groups.values()) {
      g.center = [g.items.reduce((s, i) => s + i.lat, 0) / g.items.length, g.items.reduce((s, i) => s + i.lon, 0) / g.items.length];
    }
    return { clusters: [...groups.values()], minor: minorDots };
  }, [zones]);

  return (
    <>
      {minor.map((i) => (
        <CircleMarker key={i.id} center={[i.lat, i.lon]} radius={2}
          pathOptions={{ stroke: false, fillColor: MINOR_REPORT, fillOpacity: 0.4 }}>
          <Tooltip className="cp-tooltip">{i.label} · {clockTime(i.timestamp, false)} · anonymous report</Tooltip>
        </CircleMarker>
      ))}
      {clusters.map((c) => (
        <Marker key={c.key} position={c.center} icon={incidentIcon(c.kind, c.color, c.items.length)}
          eventHandlers={{ click: () => onSelectZone(c.zoneId) }} zIndexOffset={500}
          title={`${c.items.length} × ${c.label}`}>
          <Tooltip className="cp-tooltip" direction="top" offset={[0, -14]}>
            <strong>{c.items.length} × {c.label}</strong>
            <br />
            latest {clockTime(c.items[0].timestamp, false)} · anonymous reports
          </Tooltip>
        </Marker>
      ))}
    </>
  );
});

const AirLayer = memo(function AirLayer({ zones }: { zones: ZoneState[] }) {
  // Every unusual area gets a soft haze; one AQI badge per hotspot, on its worst area.
  const badges = useMemo(() => hotspots(zones).flatMap((h) => {
    const bad = h.cells.filter((z) => z.metrics.aqi?.is_anomaly && z.metrics.aqi.current !== null);
    bad.sort((a, b) => (b.metrics.aqi.current ?? 0) - (a.metrics.aqi.current ?? 0));
    return bad.slice(0, 1);
  }), [zones]);
  return (
    <>
      {zones.map((z) => {
        const m = z.metrics.aqi;
        if (!m?.is_anomaly || m.current === null) return null;
        return <Circle key={`air-${z.id}`} center={z.anchor} radius={1700} interactive={false}
          pathOptions={{ stroke: false, fillColor: HAZE, fillOpacity: 0.18, className: "cp-haze" }} />;
      })}
      {badges.map((z) => (
        <Marker key={`aqi-${z.id}`} position={[z.anchor[0] - 0.0135, z.anchor[1]]} icon={airIcon(z.metrics.aqi.current ?? 0)} interactive={false} />
      ))}
    </>
  );
});

const SENSOR_LABEL: Record<string, string> = {
  traffic: "Traffic sensor", rain_gauge: "Rain gauge", air_quality: "Air monitor", water_level: "Water-level sensor",
};

const SensorLayer = memo(function SensorLayer({ sensors }: { sensors: Sensor[] }) {
  return (
    <>
      {sensors.map((s) => (
        <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={2.5}
          pathOptions={{ color: SENSOR_COLORS[s.kind], weight: 1.2, fillColor: "#05080d", fillOpacity: 1, opacity: 0.75 }}>
          <Tooltip className="cp-tooltip" direction="top">
            <strong>{SENSOR_LABEL[s.kind]}</strong> <span style={{ color: "#94a3b8" }}>{s.id}</span>
            {Object.entries(s.values)
              .filter(([k]) => ["congestion_pct", "rain_mm_h", "aqi", "water_level_cm"].includes(k))
              .map(([k, v]) => (
                <div key={k}>{k.replace(/_/g, " ")}: {num(v.value)} {v.unit}</div>
              ))}
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  );
});

/** One label per hotspot (not per cell), plus a small name tag for the selected area. */
const Labels = memo(function Labels({ zones, selectedZone, onSelectZone }: {
  zones: ZoneState[]; selectedZone: string | null; onSelectZone: (id: string) => void;
}) {
  const spots = useMemo(() => hotspots(zones), [zones]);
  const leads = new Set(spots.map((h) => h.lead.id));
  // Labels are ~2 cells wide: when two hotspots are close, move the less important label below its area.
  const positions = useMemo(() => {
    const placed: { row: number; col: number }[] = [];
    return spots.map((h) => {
      const { row, col } = parseRef(h.lead.id);
      const clash = placed.some((p) => Math.abs(p.row - row) <= 1 && Math.abs(p.col - col) <= 2);
      const at = clash ? { row: row + 0.75, col } : { row, col };
      placed.push({ row: Math.round(at.row), col });
      return (clash ? [h.lead.anchor[0] - 0.0225 * 0.75, h.lead.anchor[1]] : h.lead.anchor) as LatLon;
    });
  }, [spots]);
  const selected = selectedZone && !leads.has(selectedZone) ? zones.find((z) => z.id === selectedZone) : null;
  return (
    <>
      {spots.map((h, i) => (
        <Marker key={`label-${h.lead.id}`} position={positions[i]}
          icon={hotspotLabelIcon(h.lead, h.cells.length, selectedZone === h.lead.id, SMALL)}
          eventHandlers={{ click: () => onSelectZone(h.lead.id) }} keyboard
          title={`${h.lead.name}: ${h.lead.status_label}. ${h.lead.headline}`} alt={`${h.lead.name}: ${h.lead.status_label}`}
          zIndexOffset={h.status === "RED" ? 2000 : 1500} />
      ))}
      {selected && (
        <Marker key={`sel-${selected.id}`} position={selected.anchor} icon={placeLabelIcon(selected)} interactive={false} zIndexOffset={1000} />
      )}
    </>
  );
});

function FragmentGroup({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

// -------------------------------------------------------------------- map

export function CityMap({ boundaries, mapInfo, zones, sensors, layers, selectedZone, panelOpen, onSelectZone }: Props) {
  return (
    <MapContainer center={JAIPUR} zoom={12} zoomSnap={0.25} minZoom={10} maxZoom={16} zoomControl={false}
      className="h-full w-full" aria-label="Map of Jaipur divided into a 9 by 9 grid of areas">
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
      <ZoomControl position="bottomleft" />
      <Framing boundaries={boundaries} selectedZone={selectedZone} panelOpen={panelOpen} />

      <GridCells boundaries={boundaries} zones={zones} selectedZone={selectedZone} onSelectZone={onSelectZone} />
      {mapInfo && <GridRefs mapInfo={mapInfo} />}
      {layers.air && <AirLayer zones={zones} />}
      {layers.rain && <RainLayer boundaries={boundaries} zones={zones} />}
      {layers.traffic && mapInfo && <TrafficLayer roads={mapInfo.roads} zones={zones} />}
      {layers.sensors && <SensorLayer sensors={sensors} />}
      {layers.reports && <ReportsLayer zones={zones} onSelectZone={onSelectZone} />}
      <Labels zones={zones} selectedZone={selectedZone} onSelectZone={onSelectZone} />
    </MapContainer>
  );
}
