# CityPulse — API Reference

Base URL (local): `http://127.0.0.1:8000`. Interactive docs with "Try it out":
`http://127.0.0.1:8000/docs`.

All responses are JSON. Times are ISO-8601 **UTC** (the UI converts them to local time).
No authentication — this is a public-information demo (see *Security* at the end).

**Design rule:** read endpoints never compute anything. The pipeline runs every 3 seconds and
the API serves its latest result (`CityState`), so a slow feed or AI call can't slow a request.

---

## Contents

| Method | Path | Purpose |
|---|---|---|
| GET | [`/api/health`](#get-apihealth) | Is everything working? |
| GET | [`/api/dashboard`](#get-apidashboard) | The complete civic state (what the UI polls) |
| GET | [`/api/zones`](#get-apizones) | The 81 grid areas (A1–I9) + current status |
| GET | [`/api/map`](#get-apimap) | Grid edges + Jaipur main roads (OpenStreetMap) per cell |
| GET | [`/api/zones/{zone_id}`](#get-apizoneszone_id) | Detail for one area (e.g. `F4`) |
| GET | [`/api/readings`](#get-apireadings) | Recent normalized readings |
| GET | [`/api/incidents`](#get-apiincidents) | Recent anonymous civic reports |
| GET | [`/api/anomalies`](#get-apianomalies) | Active anomalies |
| GET | [`/api/correlations`](#get-apicorrelations) | Possible relationships |
| GET | [`/api/risks`](#get-apirisks) | Possible-impact / early-warning insights |
| GET | [`/api/summary`](#get-apisummary) | Plain-language summaries |
| GET | [`/api/sources/status`](#get-apisourcesstatus) | Feed health |
| GET | [`/api/alerts`](#get-apialerts) | Monitoring-agent alerts |
| GET | [`/api/agent`](#get-apiagent) | Agent reasoning trace |
| GET | [`/api/sensors`](#get-apisensors) | IoT sensor layer |
| GET | [`/api/timeline`](#get-apitimeline) | Area-status history (heat-map) |
| GET | [`/api/simulation/status`](#get-apisimulationstatus) | Demo state |
| GET | [`/api/simulation/scenarios`](#get-apisimulationscenarios) | Scenario presets and custom controls |
| POST | [`/api/simulation/scenario`](#post-apisimulationscenario) | Run a scenario preset (instant by default) |
| POST | [`/api/simulation/playback`](#post-apisimulationplayback) | Pause / resume / speed |
| POST | [`/api/simulation/custom`](#post-apisimulationcustom) | Custom scenario from sliders |
| POST | [`/api/simulation/event`](#post-apisimulationevent) | Trigger a single civic event |
| POST | [`/api/simulation/reset`](#post-apisimulationreset) | Back to normal |
| POST | [`/api/simulation/feed-fault`](#post-apisimulationfeed-fault) | Simulate a feed failure |
| GET | [`/api/replay`](#get-apireplay) | Replay metadata |
| GET | [`/api/replay/frames/{i}`](#get-apireplayframesi) | Civic state at replay minute *i* |
| GET | [`/api/replay/frames/{i}/zones/{zone_id}`](#get-apireplayframesizoneszone_id) | Zone detail at replay minute *i* |

---

## Health and state

### GET `/api/health`

```json
{
  "status": "ok",
  "pipeline": { "ok": true, "last_update_seconds_ago": 2.1, "ticks": 133 },
  "storage":  { "ok": true, "detail": "ok" },
  "feeds": { "weather": "SIMULATED", "traffic": "SIMULATED", "incidents": "SIMULATED",
             "air_quality": "SIMULATED", "iot_sensors": "SIMULATED" },
  "ai": "disabled (no API key) — using templates"
}
```

`status` is `ok`, `degraded` (a feed is not healthy, storage failed, or the pipeline is late) or
`starting`. It is always HTTP 200 so monitoring tools can read the details.

### GET `/api/dashboard`

The single structured civic state — the source of truth for the map, dashboard, AI and agent.

| Field | Meaning |
|---|---|
| `generated_at` | When this state was computed |
| `mode` | `live` (or `replay` for replay frames) |
| `pulse` | `{city_status, bpm, active_anomalies, active_relationships, zones_by_status}` |
| `zones[]` | One `ZoneState` per zone (below) |
| `feeds[]` | Feed health (see `/api/sources/status`) |
| `alerts[]` | Active alerts first, then up to 6 recently resolved |
| `summary` | `{headline, sections: {whats_happening, why_it_matters, possible_connection}, generated_by: "template" \| "ai", generated_at, note}` |
| `ticker[]` | Latest 40 stream events `{at, zone_id, kind, text, severity}` |
| `simulation` | Demo state (see `/api/simulation/status`) |
| `config` | Windows, thresholds, AI status, baseline history length |

**`ZoneState`** fields: `id, number, name, short_name, status (GREEN|YELLOW|RED), status_label,
headline, issue_types[], metrics{}, anomalies[], relationships[], risks[],
insufficient_evidence[], cannot_assess[], incident_counts{}, recent_incidents[], anchor`.

**`metrics[key]`** (one per signal) — everything needed to explain "how unusual":

```json
{
  "metric": "congestion_pct", "label": "Traffic congestion", "unit": "%", "source": "traffic",
  "current": 55.2, "baseline": 56.3, "deviation_pct": -2.0, "robust_z": -0.2,
  "threshold": "≥ 30% above normal", "is_anomaly": false, "severity": "none",
  "trend": "steady", "samples": 20, "last_updated": "2026-09-24T11:06:07.685Z",
  "data_status": "simulated", "available": true
}
```

`available: false` with `current: null` means the feed is missing — the value is **not assessed**,
never assumed to be zero.

**`relationships[]`** — possible links, never causes:

```json
{
  "id": "F4:rain_traffic", "rule_id": "rain_traffic", "title": "Rain and traffic congestion",
  "signals": ["rain_mm_h", "congestion_pct", "transit_delay_min"],
  "strength": "strong", "score": 0.99, "co_movement_r": 0.94,
  "lead_lag": "Rainfall became unusual first (15:07:12); traffic congestion followed about 1 min later.",
  "window_minutes": 10,
  "evidence": ["Rainfall: 26.5 mm/h (anomaly rule: ≥ 7.6 mm/h (heavy rain))", "…"],
  "statement": "Heavy rainfall and higher-than-usual traffic congestion are occurring in the same zone and time window. These signals may be related.",
  "caveat": "This is a possible link based on location and timing, not a confirmed cause. Other factors may be involved."
}
```

### GET `/api/zones`

The 81 areas (Jaipur's 9 × 9 grid, A1–I9) with GeoJSON squares (for drawing the map) and
current status.

```json
[{ "id": "F4", "number": 32, "name": "Walled City (F4)", "short_name": "Walled City", "row": 3, "col": 5,
   "status": "GREEN", "status_label": "Normal", "headline": "Conditions normal",
   "centroid": [26.92225, 75.8306], "anchor": [26.92225, 75.8306],
   "boundary": { "type": "Polygon", "coordinates": [[[75.818, 26.9335], "…"]] } }]
```

`row`/`col` are 0-based (row 0 = north, col 0 = west). `centroid` is also used for live API queries.

### GET `/api/map`

Static map furniture: the grid edges and Jaipur's main roads split per cell, used to draw
congestion on real roads.

```json
{ "city": "Jaipur",
  "grid": { "north": 26.996, "south": 26.7935, "west": 75.692, "east": 75.9188, "rows": 9, "cols": 9, "col_letters": "ABCDEFGHI" },
  "roads": [{ "cell": "F4", "kind": "major", "name": "Mirza Ismail Road", "path": [[26.915, 75.80], "…"] }],
  "roads_attribution": "Road shapes © OpenStreetMap contributors (ODbL)" }
```

### GET `/api/zones/{zone_id}`

Everything the area panel needs for one area (e.g. `/api/zones/F4`).

| Field | Meaning |
|---|---|
| `zone` | The `ZoneState` |
| `explanation` | `{whats_happening, why_it_matters, possible_connection}` for this zone |
| `explanation_by` | `template` or `ai` |
| `series{metric}` | Last 15 min in 20-second bins: `[{t, v}]` (`v` is `null` for gaps) |
| `baselines{metric}` | Normal value for this time of day |
| `reports_per_minute[]` | `{minute, count}` |
| `sensors[]` | Sensors in this zone with latest values |
| `alerts[]` | Active alerts for this zone |
| `agent_trace[]` | The agent's last reasoning steps |

Errors: `404` `{"detail": "Unknown area 'Z9'. Areas are grid cells A1–I9."}`

---

## Data

### GET `/api/readings`

| Query | Required | Default | Notes |
|---|---|---|---|
| `zone_id` | yes | — | `A1`–`I9` |
| `metric` | yes | — | e.g. `rain_mm_h`, `congestion_pct`, `aqi`, `water_level_cm` |
| `minutes` | no | 15 | 1–40 |

```json
[{ "ts": "2026-09-24T11:05:16+00:00", "value": 0.0, "data_status": "simulated", "sensor_id": "RG-E-01" }]
```

### GET `/api/incidents`

Query: `zone_id` (optional), `minutes` (1–40, default 10). Returns normalized, anonymous reports:

```json
[{ "id": "SR-5BC70D3E6D", "source": "incidents", "zone_id": "F7",
   "timestamp": "2026-09-24T10:56:22Z", "ingested_at": "2026-09-24T10:56:24Z",
   "category": "streetlight", "severity": "low", "lat": 28.5432, "lon": 77.1976,
   "confidence": 1.0, "data_status": "simulated",
   "metadata": { "personal_fields_dropped": 2 } }]
```

`personal_fields_dropped` shows that the upstream record carried personal data that CityPulse
discarded; the values themselves are never stored.

### GET `/api/anomalies` · `/api/correlations` · `/api/risks`

Flattened lists across all zones of `Anomaly`, `Relationship` and `RiskInsight` objects (same
shapes as inside `/api/dashboard`).

**Anomaly:** `{id, zone_id, metric, label, severity, current, baseline, deviation_pct, unit, since, description}`
**RiskInsight:** `{id, zone_id, kind: "potential_disruption" | "early_warning", level, headline, evidence[], resident_advice}`

### GET `/api/summary`

```json
{ "city": { "headline": "…", "sections": { "…": "…" }, "generated_by": "template", "generated_at": "…", "note": null },
  "zones": { "F4": { "whats_happening": "…", "why_it_matters": "…", "possible_connection": "…" } } }
```

### GET `/api/sources/status`

One entry per feed:

```json
{ "id": "weather", "label": "Weather", "source_type": "weather", "status": "SIMULATED",
  "provider": "synthetic city model", "last_success_at": "2026-09-24T11:06:04Z", "age_seconds": 3.0,
  "expected_interval_seconds": 10.0, "message": "Receiving simulated data (demo city).",
  "fault_mode": "none", "records_accepted": 510, "records_rejected": 0 }
```

| `status` | Meaning |
|---|---|
| `LIVE` | Fresh data from a real public API |
| `SIMULATED` | Fresh data from the demo-city simulation |
| `FALLBACK` | Primary source failing — substitute estimate or last known values (message says which) |
| `DELAYED` | No update for > 3 expected intervals |
| `STALE` | No update for > 8 intervals — not used as current |
| `UNAVAILABLE` | No usable data |
| `ARCHIVE` | Recorded data in replay mode |

### GET `/api/alerts`

`{"active": [Alert], "recently_resolved": [Alert]}`

**Alert:** `{id, zone_id, level: info|warning|critical, kind, title, observed[], possible_relationship, causation_note, opened_at, updated_at, resolved_at, active}`.
`kind` is `potential_disruption`, `early_warning`, `possible_relationship`, `anomaly` or `data_quality`.

### GET `/api/agent`

```json
{ "runs": 133,
  "last_trace": ["Checked 5 feeds: all healthy", "Data quality: 0 malformed record(s) rejected so far",
                 "Checked anomalies: 0 active across 81 zones",
                 "Decision: 0 active alert(s); 0 opened, 0 resolved this run"],
  "active_alerts": [] }
```

### GET `/api/sensors`

```json
[{ "id": "TS-F4-1", "zone_id": "F4", "kind": "traffic", "lat": 26.9246, "lon": 75.8231,
   "values": { "congestion_pct": { "value": 55.4, "unit": "%", "ts": "…", "data_status": "simulated" } } }]
```

`kind` is `traffic`, `rain_gauge`, `air_quality` or `water_level`.

### GET `/api/timeline`

Area statuses every 15 seconds over the last 30 minutes:
`[{ "at": "…", "zones": { "E4": "RED", "F4": "RED", "F5": "YELLOW", "…": "…" } }]`

---

## Simulation (demo controls)

Events change the **synthetic city**, not the analysis — CityPulse has to detect them itself.

### GET `/api/simulation/status`

```
{ active_events: [{event, label, zone_id, started_at, ends_at, level}],
  scenario: { id, name, focus_zone, expected, started_at, elapsed_s, complete,
              stages: [{key, label, reached_at, t_plus_s, expected_at_s}] } | null,
  clock: { speed, paused },
  custom: { zone_id, values } | null,
  presets: [...], custom_controls: [...], available_events: [...] }
```

`elapsed_s` and `t_plus_s` are in **scenario time** (they stop while paused and run faster at 2×/4×).

### GET `/api/simulation/scenarios`

The presets: `[{id, name, tagline, zone_id, severity, duration_s, feeds, expected, icon, beats: [{key, label, expected_at_s}]}]`
and the custom slider list.

### POST `/api/simulation/scenario`

```json
{ "name": "heavy_rain", "instant": true }
```

`name`: `heavy_rain`, `flash_flood`, `traffic`, `accident`, `power_outage`, `poor_air`, `storm`,
`multi_event` (alias `full`). Resets the city, then plays the preset's timed effects. Storyline
beats are ticked only when the analysis output shows them. Unknown name → `400` listing valid ids.

`instant` (default `true`): the situation is shown straight away — the scenario starts ~2 minutes
in the past and the pipeline is fast-forwarded through that time with the same feeds and analysis
as live (the request takes ~2 s). `false` starts it now, to watch it unfold with pause and 2×/4×.

### POST `/api/simulation/playback`

```json
{ "action": "speed", "speed": 2 }
```

`action`: `pause`, `resume`, `speed` (with `speed` 1, 2 or 4). Scenario time is paused or
accelerated; analysis keeps running on the real clock.

### POST `/api/simulation/custom`

```json
{ "zone_id": "F4", "values": { "rain": 1.0, "traffic": 0.6 }, "duration_s": 900 }
```

`values` keys: `rain`, `flooding`, `traffic`, `accident`, `outage`, `air`, each 0–1.5 (0 removes it).
Replaces any previous custom scenario.

### POST `/api/simulation/event`

```json
{ "event": "heavy_rain", "zone_id": "F4", "intensity": 1.0, "duration_s": 600 }
```

| Field | Rules |
|---|---|
| `event` | `heavy_rain`, `flooding`, `traffic_spike`, `road_accident`, `incident_cluster`, `poor_air` |
| `zone_id` | `A1`–`I9` (the event is centred there and reaches neighbouring areas more weakly) |
| `intensity` | 0.2–1.5 (optional, default 1.0) |
| `duration_s` | 60–3600 (optional, default 600) |

Response: `{"ok": true, "message": "Heavy rain in Walled City (F4) started. …"}`
Invalid input → `422`:
`{"error": "invalid_request", "detail": ["event: Input should be 'heavy_rain', 'flooding', …"]}`

### POST `/api/simulation/reset`

Clears events, feed faults, alerts and live data; back-fills 10 minutes of normal data.

### POST `/api/simulation/feed-fault`

```json
{ "feed_id": "weather", "mode": "outage" }
```

`feed_id`: `weather`, `traffic`, `incidents`, `air_quality`, `iot_sensors`.
`mode`: `none`, `outage` (requests fail), `delay` (upstream silently stops), `malformed` (some
records broken).
Unknown feed or mode → `400` with the list of valid values.

---

## Historical replay

The browser owns the playhead and asks for frame *i*. Frames are computed once and cached.

### GET `/api/replay`

```json
{ "available": true, "name": "Recorded storm — 23 Sep, 18:18 (local time)",
  "description": "Recorded data from the archive, replayed through the same analysis engine and monitoring agent that run live. Nothing here is live.",
  "focus_zone": "E6", "start": "2026-09-23T12:28:00+00:00", "end": "2026-09-23T14:10:00+00:00",
  "step_seconds": 60,
  "frames": [{ "i": 0, "t": "…", "city_status": "GREEN", "statuses": { "A1": "GREEN", "…": "…" } }],
  "key_moments": [{ "i": 20, "t": "…", "label": "Rain begins" }, { "i": 25, "t": "…", "label": "Traffic increases" }] }
```

`404` if no recorded event exists in the history.

### GET `/api/replay/frames/{i}`

A full `CityState` (same shape as `/api/dashboard`) with `mode: "replay"` and every feed
`ARCHIVE`. `404` if *i* is out of range.

### GET `/api/replay/frames/{i}/zones/{zone_id}`

Same shape as `/api/zones/{zone_id}`, at that recorded minute (series in 60-second bins).

---

## Errors

| Status | When | Body |
|---|---|---|
| 400 | Unknown feed / fault mode, invalid simulation request | `{"detail": "…"}` or `{"error": "invalid_simulation", "detail": "…"}` |
| 404 | Unknown zone, replay unavailable, frame out of range | `{"detail": "…"}` |
| 422 | Request body/query failed validation | `{"error": "invalid_request", "detail": ["field: message"]}` |
| 500 | Unexpected server error | `{"error": "internal_error", "detail": "Something went wrong on our side. The rest of CityPulse keeps running."}` |
| 503 | Pipeline still starting | `{"detail": "CityPulse is starting up — try again in a few seconds."}` |

Stack traces, file paths and secrets never appear in responses; details go to the server log only.

## Security notes

- No authentication: the data is public-information by design and the demo contains no
  personal data. Before a real deployment, protect the `POST /api/simulation/*` endpoints
  (or disable them) — they exist for demos.
- CORS allows only the origins in `CITYPULSE_CORS_ORIGINS` and only `GET`/`POST`.
- All input is validated by Pydantic models; zone and feed IDs are checked against fixed lists.
- API keys (e.g. `ANTHROPIC_API_KEY`) are read from the environment and never returned.
