import type { CityState, MapInfo, ReplayMeta, Sensor, TimelineEntry, ZoneBoundary, ZoneDetail } from "../types";

// In development Vite proxies /api to the backend. For a deployed build, set VITE_API_BASE.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      signal: init?.signal ?? AbortSignal.timeout(8000),
    });
  } catch {
    throw new ApiError("Cannot reach the CityPulse server.");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status}).`;
    try {
      const body = await res.json();
      detail = Array.isArray(body.detail) ? body.detail.join("; ") : (body.detail ?? detail);
    } catch {
      /* non-JSON error body: keep the generic message */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<CityState>("/api/dashboard"),
  zones: () => request<ZoneBoundary[]>("/api/zones"),
  map: () => request<MapInfo>("/api/map", { signal: AbortSignal.timeout(20000) }),
  zone: (id: string) => request<ZoneDetail>(`/api/zones/${id}`),
  sensors: () => request<Sensor[]>("/api/sensors"),
  timeline: () => request<TimelineEntry[]>("/api/timeline"),

  replayMeta: () => request<ReplayMeta>("/api/replay", { signal: AbortSignal.timeout(30000) }),
  replayFrame: (i: number) => request<CityState>(`/api/replay/frames/${i}`),
  replayZone: (i: number, zoneId: string) => request<ZoneDetail>(`/api/replay/frames/${i}/zones/${zoneId}`),

  triggerEvent: (event: string, zone_id: string) =>
    request<{ message: string }>("/api/simulation/event", {
      method: "POST",
      body: JSON.stringify({ event, zone_id }),
    }),
  // Instant (default): the backend fast-forwards the scenario, so this takes a few seconds.
  runScenario: (name: string, instant = true) =>
    request<{ message: string }>("/api/simulation/scenario", {
      method: "POST", body: JSON.stringify({ name, instant }), signal: AbortSignal.timeout(30000),
    }),
  playback: (action: "pause" | "resume" | "speed", speed?: number) =>
    request<{ message: string }>("/api/simulation/playback", { method: "POST", body: JSON.stringify({ action, speed }) }),
  custom: (zone_id: string, values: Record<string, number>, duration_s: number) =>
    request<{ message: string }>("/api/simulation/custom", {
      method: "POST",
      body: JSON.stringify({ zone_id, values, duration_s }),
    }),
  reset: () => request<{ message: string }>("/api/simulation/reset", { method: "POST" }),
  setFault: (feed_id: string, mode: string) =>
    request<{ message: string }>("/api/simulation/feed-fault", {
      method: "POST",
      body: JSON.stringify({ feed_id, mode }),
    }),
};
