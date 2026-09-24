# CityPulse — File Guide

What every meaningful file does, why it exists and how it connects to the rest. Files are
grouped in the order data flows through the system.

---

## Root

| File | Purpose |
|---|---|
| `README.md` | Project overview, setup, demo, API summary |
| `.env.example` | Every configurable setting with safe defaults (copy to `backend/.env`) |
| `.gitignore` | Keeps secrets, virtual environments, `node_modules`, builds and local databases out of git |
| `docs/` | Setup, team guide, architecture, API, database, file guide, requirement matrix, demo, presentation, pitch script, judge Q&A, final checklist, `screenshots/` |

---

## Backend — `backend/`

### `requirements.txt`
Python dependencies: FastAPI, Uvicorn, SQLAlchemy, Pydantic (+ settings), httpx, anthropic, pytest.

### `app/main.py`
**Purpose:** creates the FastAPI app.
**Why:** one entry point for `uvicorn app.main:app`.
**Important contents:** `lifespan` (builds the pipeline, runs start-up, launches the background
tick loop), CORS, one-server mode (serves `frontend/dist` if it has been built), three error handlers (simulation errors → 400, validation → 422 with field
messages, everything else → generic 500 with no stack trace).
**Depends on:** `services/pipeline.py`, `api/routes.py`, `config.py`.

### `app/config.py`
**Purpose:** all settings in one place (`Settings`), overridable by `CITYPULSE_*` env vars.
**Important contents:** thresholds (traffic 30 %, heavy rain 7.6 mm/h, AQI 150, report
p-value 0.001…), windows (current 60 s, rolling 10 min), feed freshness rules, AI settings.
**Used by:** nearly every module.

### `app/schemas.py`
**Purpose:** the **common civic data model** and the **structured civic state**.
**Why:** a single, typed contract between normalization, analysis, AI, agent, API and UI.
**Important contents:** `CivicReading`, `CivicIncident` (normalized data); `MetricAssessment`,
`Anomaly`, `Relationship`, `RiskInsight`, `ZoneState`, `FeedHealth`, `Alert`, `Summary`,
`CityState` (analysis output); enums `DataStatus`, `FeedStatus`, `ZoneStatus`.

### `app/database.py`
**Purpose:** SQLAlchemy engine, session factory and ORM tables.
**Important contents:** tables `zones`, `civic_readings`, `incidents`, `alerts`,
`zone_snapshots`, `simulation_events`; composite indexes; SQLite WAL mode.
**Used by:** `services/persistence.py`.

### `app/geo/zones.py`
**Purpose:** the five demonstration zones, their sensors and point-in-polygon lookup.
**Important contents:** `ZONES`, `SENSOR_REGISTRY`, `zone_for_point()` (ray casting),
`label_point` (where each map label sits), `centroid` (used for live API queries).
**Used by:** data sources, normalizers, engine, API.

### Data sources — `app/data_sources/`

| File | Purpose | Important contents |
|---|---|---|
| `city_model.py` | Deterministic synthetic city ("ground truth") | Daily patterns per metric, zone character, `Effect` (ramp/hold/fade envelope), `EFFECT_IMPACTS` (what rain / traffic spike / outage cluster / poor air do, with lags), seeded noise, Poisson report generation |
| `weather.py` | Weather feed in two formats | Synthetic "CPMET" rain gauges (mm/15 min, °F, m/s, +05:30 time); Open-Meteo live client |
| `traffic.py` | Traffic + transit feed | Road sensors ("TSN v2", epoch ms, speed); bus operator CSV (day-first local time, area codes) |
| `incidents.py` | Open311-style civic reports | Service-name mapping; deliberately includes personal fields that must be stripped; malformed-record injection |
| `air_quality.py` | Air-quality feed | OpenAQ-like PM2.5 records; Open-Meteo air-quality client |
| `sensors.py` | IoT water-level sensors | MQTT-style messages (topic, epoch seconds, JSON string payload in mm) |

**Why separate files:** each simulates a different upstream vendor, so normalization has
genuinely different formats to reconcile.

### Normalization — `app/normalization/`

| File | Purpose | Important contents |
|---|---|---|
| `timestamps.py` | Any timestamp convention → aware UTC | ISO with/without zone, `Z`, epoch s/ms, day-first text, `IST` suffix; future-time rejection |
| `units.py` | Unit conversion + validation | °F→°C, m/s→km/h, per-interval→per-hour, mm→cm, PM2.5→US AQI (EPA breakpoints), plausible ranges |
| `normalizers.py` | One normalizer per raw format | `normalize_cpmet_weather`, `normalize_open_meteo_weather`, `normalize_tsn_traffic`, `normalize_transit_csv`, `normalize_open311` (field whitelist = PII removal), `normalize_openaq`, `normalize_open_meteo_aq`, `normalize_mqtt_water`; `NormalizationResult` with per-record rejection reasons |

### Analysis — `app/analysis/`

| File | Purpose | Important contents |
|---|---|---|
| `metrics.py` | Catalogue of metrics and how each is judged | `METRICS` (label, unit, source, mode relative/absolute/hybrid/info, icon), incident categories, derived report metrics |
| `baseline.py` | "What is normal here, now?" | `BaselineModel.fit()` — median + MAD per zone × metric × half-hour; report rates; default baselines |
| `anomaly.py` | Explainable anomaly detection | `assess_continuous`, `assess_incident_count` (with `poisson_tail`), severity rules, trend, `onset()` (when it started) |
| `correlation.py` | Rolling-window possible relationships | `RULES`, `evaluate_zone()` (same zone, same window, timing, co-movement, evidence score, hedged statement), insufficient-evidence and cannot-assess notes |
| `risk.py` | Possible-impact insights and zone status | Potential disruption, early warnings, `zone_status()` GREEN/YELLOW/RED |
| `engine.py` | Runs the whole analysis for every zone | `AnalysisEngine.analyze()` → `ZoneState` list + `PulseInfo`; binned series for co-movement |

### AI / NLP — `app/ai/`

| File | Purpose | Important contents |
|---|---|---|
| `facts.py` | Compact fact sheet from the civic state | `build_facts()`, `fingerprint()` (changes only when the situation changes) |
| `templates.py` | Deterministic plain-language summaries | `city_summary()`, `zone_explanation()` — "What's happening / Why it may matter / Possible connection" |
| `llm.py` | Optional Claude call | System prompt with grounding rules; `messages.parse` with `SummaryOut` schema; returns `None` on any failure |
| `validator.py` | Grounding checks | Rejects invented numbers, causal phrases, unflagged zones |
| `summarizer.py` | Chooses what is shown | Template every tick; background LLM request when the situation changes; AI text only if validated and still current |

### Agent — `app/agent/monitor.py`
**Purpose:** the monitoring agent.
**Important contents:** `MonitoringAgent.run()` (feeds → data quality → anomalies → related
signals → decision), alert reconciliation with hysteresis, folding of lower alerts into a zone's
critical alert, reasoning `trace`, best-effort persistence callback.
**Used by:** `services/pipeline.py`. **Depends on:** `schemas.py`.

### Simulation — `app/simulation/`

| File | Purpose | Important contents |
|---|---|---|
| `controller.py` | Demo events and the full scenario | `trigger()` with input validation, `start_full_scenario()`, `advance()` (timed steps), `storm_stages()` + `advance_stages()` (stages ticked from real analysis output, shared with replay), `status()` |
| `history.py` | Synthetic multi-day history | `generate_history()` every 5 min for 3 days, plus a 1-minute archive around a recorded storm (yesterday evening, Zones 3–4) with realistic minute-scale lags |
| `replay.py` | Historical replay | `ReplayService` finds the recorded event, loads the archive, runs the same `AnalysisEngine` + a fresh `MonitoringAgent` minute by minute, caches frames, key moments and zone details |

### Services — `app/services/`

| File | Purpose | Important contents |
|---|---|---|
| `pipeline.py` | The orchestrator (`CityPulse`) | `startup()`, `warm_up()`, `tick()` (whole pipeline, never raises after start-up), simulation actions, `zone_detail()`, ticker and heat-map timeline |
| `feed_manager.py` | Polling, fallback chain, feed health | `FEEDS` registry (incl. each live source's publishing cadence), fault modes, live→synthetic fallback with back-off, status rules LIVE…UNAVAILABLE, friendly error messages |
| `ticker.py` | Live civic signal stream | `Ticker.update()` turns changes between ticks (new reports, anomalies, links, status, alerts, feed health) into narrative events; shared by live and replay |
| `views.py` | Zone-detail view | `zone_detail()` builds chart series, baselines and report counts; shared by live and replay |
| `store.py` | In-memory rolling store | Time-ordered series per zone × metric, de-duplicated incidents, latest value per sensor, pruning |
| `persistence.py` | Best-effort database access | History load/generation, saving readings, incidents, alerts, snapshots, simulation log; never raises into the pipeline |

### API — `app/api/routes.py`
**Purpose:** all HTTP endpoints under `/api`.
**Important contents:** read endpoints serve the pre-computed `CityState`; simulation endpoints
validate input with Pydantic (`EventRequest`, `FaultRequest`); 404/400 with helpful messages.

### Tests — `backend/tests/`

| File | Covers |
|---|---|
| `conftest.py` | Isolated temp database, background loop off, fixed test clock |
| `test_normalization.py` | Every timestamp format, unit conversions, per-feed normalizers, PII removal, malformed records |
| `test_analysis.py` | Anomaly rules (incl. the brief's 147 vs 100 example), Poisson test, correlation rules, timing, insufficient evidence, cannot-assess, risk insights, zone status |
| `test_resilience.py` | Weather/traffic outages, delay→stale, recovery, malformed data, live API timeout / 429 / bad JSON / success, database outage |
| `test_ai_agent_simulation.py` | Validator, AI fallback, validated AI text, agent alerts + hysteresis, invalid simulation input, full scenario stages, unrelated spike not linked, reset, determinism |
| `test_replay.py` | Replay finds the event, calm → disruption → recovery, key-moment order, same engine/agent, ARCHIVE labelling, baselines not distorted, replay API |
| `test_api.py` | Every endpoint, safe error responses, simulation endpoints |
| `test_config.py` | Every variable in `.env.example` is a real setting; no secret values committed |

---

## Frontend — `frontend/`

| File | Purpose |
|---|---|
| `package.json` | Dependencies and scripts (`dev`, `build`, `typecheck`) |
| `vite.config.ts` | React + Tailwind plugins; `/api` proxy to the backend in development |
| `tsconfig.json` | Strict TypeScript settings |
| `index.html` | Page shell, fonts, favicon |
| `public/favicon.svg` | Pulse-line icon |

### `src/`

| File | Purpose | Used by |
|---|---|---|
| `main.tsx` | Mounts `<App/>` | — |
| `App.tsx` | Page layout: top bar, left column, map with overlays, zone panel; polling; live vs replay state; deep links (`?zone=Z3`, `?replay=1&frame=40`) | `main.tsx` |
| `index.css` | Design tokens (colours), Tailwind import, map styling, dark basemap filter, animations (with reduced-motion support) | all components |
| `types/index.ts` | TypeScript mirror of `backend/app/schemas.py` | everything |
| `services/api.ts` | Typed API client with timeouts and readable error messages | `App`, `ZonePanel`, `DemoPanel` |
| `hooks/usePolling.ts` | `usePolling` (keeps last good data on failure), `useNow` | `App`, `ZonePanel` |
| `hooks/useReplay.ts` | Replay playhead: start/exit, play/pause, speed, frame cache + prefetch | `App` |
| `utils/status.ts` | Status / feed / severity / strength colours, words and icons | most components |
| `utils/format.ts` | Local time, "x s ago", numbers, percentages, units | most components |

### `src/components/`

| File | Purpose |
|---|---|
| `TopBar.tsx` | Brand, pulse strip, feed chips, live clock / replay clock ("Recorded … — not live") |
| `PulseStrip.tsx` | Animated heartbeat: colour = worst zone status, speed = backend-computed bpm |
| `FeedHealthBar.tsx` | One chip per feed with status word; click for message, age, accepted/rejected counts |
| `SummaryPanel.tsx` | "Right now" headline + three-part explanation; `SourceTag` (Rule-based / AI-assisted) |
| `AlertsList.tsx` | Monitoring-agent alerts: observed · possible link · causation note |
| `EventTicker.tsx` | Live civic signal stream (reports, anomalies, links, alerts, feed changes) |
| `PulseTimeline.tsx` | Zone × time heat-map of statuses over the last 30 minutes |
| `DemoPanel.tsx` | Run scenario, reset, replay, trigger events per zone, inject feed faults, scenario stage checklist |
| `ReplayBar.tsx` | Replay controls: play/pause/step/speed, zone × time scrubber, key-moment chips, back to live |
| `ui/StatusBadge.tsx` | Status pill with colour + icon + word |
| `map/CityMap.tsx` | Leaflet map: OSM tiles, zone polygons, rain cells, report dots, IoT sensors, zone labels, auto-framing of selected zone |
| `map/zoneLabel.tsx` | Builds the zone label (name, status word, issue icons, "possible link") as a Leaflet `divIcon` |
| `map/MapOverlays.tsx` | `MapLegend` and `LayerToggles` |
| `map/mapColors.ts` | Concrete colours for Leaflet SVG (CSS variables don't work there) |
| `zone/ZonePanel.tsx` | Investigation layer for one zone (risk, explanation, metrics, relationships, chart, reports, agent trace, data sources) |
| `zone/MetricCard.tsx` | One signal: current, normal, deviation, severity, trend, sparkline, rule |
| `zone/InsightCards.tsx` | `RiskCard` (possible impact / early warning) and `RelationshipCard` (strength meter + "Why this flag?") |
| `zone/SignalChart.tsx` | 15-minute chart: rain bars + traffic / bus / AQI indexed to 100 = normal |
