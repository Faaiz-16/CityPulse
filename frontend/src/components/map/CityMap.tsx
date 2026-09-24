import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo } from "react";
import { Circle, CircleMarker, MapContainer, Marker, Polygon, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { Sensor, ZoneBoundary, ZoneState } from "../../types";
import { clockTime, num } from "../../utils/format";
import { INCIDENT_COLORS, INCIDENT_DEFAULT, MAP_STATUS, RAIN, SENSOR_COLORS } from "./mapColors";
import { zoneLabelIcon } from "./zoneLabel";

export interface MapLayers {
  rain: boolean;
  reports: boolean;
  sensors: boolean;
}

interface Props {
  boundaries: ZoneBoundary[];
  zones: ZoneState[];
  sensors: Sensor[];
  layers: MapLayers;
  selectedZone: string | null;
  onSelectZone: (id: string | null) => void;
}

const SENSOR_LABEL: Record<string, string> = {
  traffic: "Traffic sensor",
  rain_gauge: "Rain gauge",
  air_quality: "Air monitor",
  water_level: "Water-level sensor",
};

const ring = (b: ZoneBoundary) => b.boundary.coordinates[0].map(([lon, lat]) => [lat, lon] as [number, number]);

/** Frame the whole city, or — when a zone is selected — frame that zone beside the details panel. */
function FitToZones({ boundaries, selectedZone }: { boundaries: ZoneBoundary[]; selectedZone: string | null }) {
  const map = useMap();
  useEffect(() => {
    if (!boundaries.length) return;
    const selected = boundaries.find((b) => b.id === selectedZone);
    const wide = map.getSize().x >= 900; // the details panel only overlays the map on wide screens
    if (selected) {
      map.flyToBounds(L.latLngBounds(ring(selected)), {
        paddingTopLeft: [40, 70],
        paddingBottomRight: [wide ? 500 : 40, 40],
        maxZoom: 13,
        duration: 0.6,
      });
    } else {
      map.flyToBounds(L.latLngBounds(boundaries.flatMap(ring)), {
        paddingTopLeft: [10, 50],
        paddingBottomRight: [10, 10],
        duration: 0.6,
      });
    }
  }, [boundaries, selectedZone, map]);
  return null;
}

export function CityMap({ boundaries, zones, sensors, layers, selectedZone, onSelectZone }: Props) {
  const byId = useMemo(() => Object.fromEntries(zones.map((z) => [z.id, z])), [zones]);
  const small = typeof window !== "undefined" && window.innerWidth < 640;

  return (
    <MapContainer
      center={[28.615, 77.21]}
      zoom={12}
      zoomSnap={0.25}
      minZoom={10}
      maxZoom={16}
      zoomControl={false}
      className="h-full w-full"
      aria-label="Map of the demonstration city zones"
    >
      {/* Standard OpenStreetMap tiles (free, no key), darkened with a CSS filter in index.css */}
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={19}
      />
      <FitToZones boundaries={boundaries} selectedZone={selectedZone} />

      {/* Zone areas, coloured by status */}
      {boundaries.map((b) => {
        const z = byId[b.id];
        if (!z) return null;
        const color = MAP_STATUS[z.status];
        const selected = selectedZone === b.id;
        return (
          <Polygon
            key={b.id}
            positions={ring(b)}
            pathOptions={{
              color: selected ? "#e8eef5" : color,
              weight: selected ? 3 : 2,
              fillColor: color,
              fillOpacity: z.status === "GREEN" ? 0.07 : z.status === "YELLOW" ? 0.16 : 0.24,
              dashArray: z.status === "GREEN" ? "4 6" : undefined,
            }}
            eventHandlers={{ click: () => onSelectZone(b.id) }}
          />
        );
      })}

      {/* Rain cells: size and opacity scale with measured rainfall */}
      {layers.rain &&
        zones.map((z) => {
          const rain = z.metrics.rain_mm_h?.current ?? 0;
          if (rain < 0.5) return null;
          return (
            <Circle
              key={`rain-${z.id}`}
              center={z.anchor}
              radius={1800 + Math.min(rain, 40) * 110}
              pathOptions={{ color: RAIN, weight: 1, dashArray: "2 5", fillColor: RAIN, fillOpacity: Math.min(0.08 + rain / 80, 0.35) }}
              interactive={false}
            />
          );
        })}

      {/* Anonymous civic reports inside the rolling window */}
      {layers.reports &&
        zones.flatMap((z) =>
          z.recent_incidents.map((i) => (
            <CircleMarker
              key={i.id}
              center={[i.lat, i.lon]}
              radius={i.severity === "high" ? 6 : 4.5}
              pathOptions={{ color: "#0a0f15", weight: 1, fillColor: INCIDENT_COLORS[i.category] ?? INCIDENT_DEFAULT, fillOpacity: 0.95 }}
            >
              <Tooltip className="cp-tooltip" direction="top" offset={[0, -4]}>
                <strong>{i.label}</strong>
                <br />
                {clockTime(i.timestamp)} · anonymous report
              </Tooltip>
            </CircleMarker>
          )),
        )}

      {/* IoT sensor layer — the same readings that feed the normalized pipeline */}
      {layers.sensors &&
        sensors.map((s) => (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.lon]}
            radius={5}
            pathOptions={{ color: SENSOR_COLORS[s.kind], weight: 2, fillColor: "#0a0f15", fillOpacity: 1 }}
          >
            <Tooltip className="cp-tooltip" direction="top" offset={[0, -4]}>
              <strong>{SENSOR_LABEL[s.kind]}</strong> <span style={{ color: "#93a1b2" }}>{s.id}</span>
              {Object.entries(s.values)
                .filter(([k]) => ["congestion_pct", "rain_mm_h", "aqi", "water_level_cm", "avg_speed_kmh"].includes(k))
                .map(([k, v]) => (
                  <div key={k}>
                    {k.replace(/_/g, " ")}: {num(v.value)} {v.unit} · {clockTime(v.ts)}
                  </div>
                ))}
            </Tooltip>
          </CircleMarker>
        ))}

      {/* Zone labels on top */}
      {zones.map((z) => (
        <Marker
          key={`label-${z.id}-${z.status}-${selectedZone === z.id}-${z.issue_types.join()}-${z.relationships.length}-${small}`}
          position={z.anchor}
          icon={zoneLabelIcon(z, selectedZone === z.id, small)}
          eventHandlers={{ click: () => onSelectZone(z.id) }}
          keyboard
          title={`${z.name}: ${z.status_label}. ${z.headline}`}
          alt={`${z.name}: ${z.status_label}`}
          zIndexOffset={z.status === "RED" ? 1000 : z.status === "YELLOW" ? 500 : 0}
        />
      ))}
    </MapContainer>
  );
}
