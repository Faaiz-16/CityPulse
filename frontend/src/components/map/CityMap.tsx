import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { memo, useEffect, useMemo } from "react";
import { Circle, CircleMarker, MapContainer, Marker, Polygon, Polyline, TileLayer, Tooltip, useMap, ZoomControl } from "react-leaflet";
import type { IncidentView, Sensor, ZoneBoundary, ZoneState } from "../../types";
import { clockTime, num, pct } from "../../utils/format";
import { scatterInRing, type LatLon } from "../../utils/geo";
import { CORRIDORS } from "./corridors";
import { HAZE, INCIDENT_KINDS, MAP_STATUS, MINOR_REPORT, RAIN, RAIN_LIGHT, SENSOR_COLORS, TRAFFIC_HOT, TRAFFIC_WARM } from "./mapColors";
import { airIcon, incidentIcon, zoneLabelIcon } from "./markers";

export interface MapLayers {
  rain: boolean;
  traffic: boolean;
  reports: boolean;
  air: boolean;
  sensors: boolean;
}

interface Props {
  boundaries: ZoneBoundary[];
  zones: ZoneState[];
  sensors: Sensor[];
  layers: MapLayers;
  selectedZone: string | null;
  panelOpen: boolean;
  onSelectZone: (id: string | null) => void;
}

const ring = (b: ZoneBoundary): LatLon[] => b.boundary.coordinates[0].map(([lon, lat]) => [lat, lon]);
const SMALL = typeof window !== "undefined" && window.innerWidth < 640;

/** Frame the whole city, or — when a zone is selected — frame that zone beside the details panel. */
function Framing({ boundaries, selectedZone, panelOpen }: { boundaries: ZoneBoundary[]; selectedZone: string | null; panelOpen: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!boundaries.length) return;
    const selected = boundaries.find((b) => b.id === selectedZone);
    const wide = map.getSize().x >= 900;
    if (selected) {
      map.flyToBounds(L.latLngBounds(ring(selected)), {
        paddingTopLeft: [60, 90],
        paddingBottomRight: [wide && panelOpen ? 480 : 60, 60],
        maxZoom: 13,
        duration: 0.7,
      });
    } else {
      map.flyToBounds(L.latLngBounds(boundaries.flatMap(ring)), {
        paddingTopLeft: [20, 70],
        paddingBottomRight: [20, 20],
        duration: 0.7,
      });
    }
  }, [boundaries, selectedZone, panelOpen, map]);
  return null;
}

// ------------------------------------------------------------------ layers

const ZoneAreas = memo(function ZoneAreas({ boundaries, zones, selectedZone, onSelectZone }: {
  boundaries: ZoneBoundary[]; zones: ZoneState[]; selectedZone: string | null; onSelectZone: (id: string) => void;
}) {
  const byId = Object.fromEntries(zones.map((z) => [z.id, z]));
  return (
    <>
      {boundaries.map((b) => {
        const z = byId[b.id];
        if (!z) return null;
        const color = MAP_STATUS[z.status];
        const selected = selectedZone === b.id;
        // Normal zones are barely there; attention is visible; disruption dominates.
        const style = {
          GREEN: { weight: selected ? 2.5 : 1, opacity: selected ? 0.9 : 0.35, fillOpacity: 0.02, dashArray: "3 6" },
          YELLOW: { weight: selected ? 3 : 2, opacity: 0.85, fillOpacity: 0.07, dashArray: undefined },
          RED: { weight: selected ? 3.5 : 3, opacity: 1, fillOpacity: 0.22, dashArray: undefined },
        }[z.status];
        return (
          <Polygon
            key={`${b.id}-${z.status}`}
            positions={ring(b)}
            pathOptions={{ color: selected && z.status === "GREEN" ? "#e8eef5" : color, fillColor: color, ...style,
              className: z.status === "RED" ? "cp-zone-red cp-glow-red" : z.status === "YELLOW" ? "cp-glow-amber" : undefined }}
            eventHandlers={{ click: () => onSelectZone(b.id) }}
          />
        );
      })}
    </>
  );
});

const RainLayer = memo(function RainLayer({ boundaries, zones }: { boundaries: ZoneBoundary[]; zones: ZoneState[] }) {
  const drops = useMemo(() => {
    const out: Record<string, LatLon[]> = {};
    for (const b of boundaries) out[b.id] = scatterInRing(ring(b), b.anchor, 60, b.number * 97 + 11, 0.075);
    return out;
  }, [boundaries]);
  return (
    <>
      {zones.map((z) => {
        const rain = z.metrics.rain_mm_h?.current ?? 0;
        if (rain < 1) return null;
        const n = Math.max(6, Math.min(60, Math.round(rain * 2)));
        return (
          <FragmentGroup key={`rain-${z.id}`}>
            <Circle center={z.anchor} radius={3000 + Math.min(rain, 40) * 90} interactive={false}
              pathOptions={{ stroke: false, fillColor: RAIN, fillOpacity: Math.min(0.06 + rain / 160, 0.22), className: "cp-haze" }} />
            {(drops[z.id] ?? []).slice(0, n).map((p, i) => (
              <CircleMarker key={i} center={p} radius={3 + (i % 3) * 1.6} interactive={false}
                pathOptions={{ stroke: false, fillColor: i % 4 === 0 ? RAIN : RAIN_LIGHT, fillOpacity: 0.85, className: "cp-rain-drop" }} />
            ))}
          </FragmentGroup>
        );
      })}
    </>
  );
});

const TrafficLayer = memo(function TrafficLayer({ zones }: { zones: ZoneState[] }) {
  return (
    <>
      {zones.flatMap((z) => {
        const m = z.metrics.congestion_pct;
        const dev = m?.deviation_pct ?? 0;
        if (!m?.available || dev < 10) return []; // normal traffic stays in the background
        const hot = dev >= 30;
        return (CORRIDORS[z.id] ?? []).map((line, i) => (
          <Polyline key={`${z.id}-road-${i}`} positions={line}
            pathOptions={{ color: hot ? TRAFFIC_HOT : TRAFFIC_WARM, weight: hot ? 5 : 3.5, opacity: hot ? 0.95 : 0.75,
              lineCap: "round", className: hot ? "cp-traffic-hot" : "cp-traffic-warm" }}>
            <Tooltip className="cp-tooltip" sticky>
              <strong>{hot ? "Heavy traffic" : "Traffic building"}</strong> · {z.short_name}
              <br />
              {pct(dev)} vs normal for this time of day
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
        <CircleMarker key={i.id} center={[i.lat, i.lon]} radius={2.5}
          pathOptions={{ stroke: false, fillColor: MINOR_REPORT, fillOpacity: 0.45 }}>
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
  return (
    <>
      {zones.map((z) => {
        const m = z.metrics.aqi;
        if (!m?.is_anomaly || m.current === null) return null;
        return (
          <FragmentGroup key={`air-${z.id}`}>
            <Circle center={z.anchor} radius={4200} interactive={false}
              pathOptions={{ stroke: false, fillColor: HAZE, fillOpacity: 0.22, className: "cp-haze" }} />
            <Marker position={[z.anchor[0] - 0.018, z.anchor[1]]} icon={airIcon(m.current)} interactive={false} />
          </FragmentGroup>
        );
      })}
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
        <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={3.5}
          pathOptions={{ color: SENSOR_COLORS[s.kind], weight: 1.5, fillColor: "#05080d", fillOpacity: 1, opacity: 0.8 }}>
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

function FragmentGroup({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

// -------------------------------------------------------------------- map

export function CityMap({ boundaries, zones, sensors, layers, selectedZone, panelOpen, onSelectZone }: Props) {
  return (
    <MapContainer center={[28.615, 77.21]} zoom={12} zoomSnap={0.25} minZoom={10} maxZoom={16} zoomControl={false}
      className="h-full w-full" aria-label="Map of the city's demonstration zones">
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
      <ZoomControl position="bottomleft" />
      <Framing boundaries={boundaries} selectedZone={selectedZone} panelOpen={panelOpen} />

      <ZoneAreas boundaries={boundaries} zones={zones} selectedZone={selectedZone} onSelectZone={onSelectZone} />
      {layers.air && <AirLayer zones={zones} />}
      {layers.rain && <RainLayer boundaries={boundaries} zones={zones} />}
      {layers.traffic && <TrafficLayer zones={zones} />}
      {layers.sensors && <SensorLayer sensors={sensors} />}
      {layers.reports && <ReportsLayer zones={zones} onSelectZone={onSelectZone} />}

      {zones.map((z) => (
        <Marker key={`label-${z.id}`} position={z.anchor} icon={zoneLabelIcon(z, selectedZone === z.id, SMALL)}
          eventHandlers={{ click: () => onSelectZone(z.id) }} keyboard
          title={`${z.name}: ${z.status_label}. ${z.headline}`} alt={`${z.name}: ${z.status_label}`}
          zIndexOffset={z.status === "RED" ? 2000 : z.status === "YELLOW" ? 1500 : 1000} />
      ))}
    </MapContainer>
  );
}
