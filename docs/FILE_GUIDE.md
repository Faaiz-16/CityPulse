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
**Purpose:** Jaipur as 5 × 5 districts (A1–E5) of 3 × 3 blocks each — 225 demonstration blocks
(`C2-9` = block 9 of district C2) — their names, sensors and lookups. `jaipur_roads.json` beside it
holds the main-road shapes (OpenStreetMap, ODbL) per block.
**Important contents:** grid constants, `LOCALITIES` (names), `district_ref()`, `cell_ref()`, `ZONES`, `SENSOR_REGISTRY`
(traffic sensors sit on real roads), `zone_for_point()` (grid arithmetic), `cell_distance()`,
`load_roads()`.
**Used by:** data sources, normalizers, engine, API.

### `scripts/build_jaipur_roads.py`
**Purpose:** one-off builder for `app/geo/jaipur_roads.json`: takes an OpenStreetMap Overpass export
of Jaipur's main roads, simplifies each road (~8 m), splits it at grid-cell edges and tags each
piece with its cell. The download command is in the file's docstring.

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
| `scenarios.py` | Scenario presets | `PRESETS` (8 scenarios: timed effect steps + storyline `Beat`s with real-analysis checks), `CUSTOM_CONTROLS` (slider → effect) |
| `controller.py` | Demo controls | `trigger()` with input validation, `start_scenario()`, `advance()` (timed steps in scenario time), `observe()` (ticks beats from analysis output), `pause()` / `resume()` / `set_speed()`, `set_custom()`, `storm_stages()` + `advance_stages()` (shared with replay), `status()` |
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
| `test_scenarios.py` | Every preset reaches its outcome through the real pipeline; poor air claims no cause; pause/resume/speed; custom sliders; scenario API |
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
| `App.tsx` | Map-first layout: full-bleed map, floating header, legend, alerts, drawers, zone panel; polling; LIVE/DEMO/REPLAY mode; deep links (`?zone=C2-9`, `?replay=1&frame=40`, `?demo=1`, `?insights=1`) | `main.tsx` |
| `index.css` | Design tokens (colours), Tailwind import, map styling, dark basemap filter, animations (with reduced-motion support) | all components |
| `types/index.ts` | TypeScript mirror of `backend/app/schemas.py` | everything |
| `services/api.ts` | Typed API client with timeouts and readable error messages | `App`, `ZonePanel`, `DemoDrawer` |
| `hooks/usePolling.ts` | `usePolling` (keeps last good data on failure), `useNow` | `App`, `ZonePanel` |
| `hooks/useReplay.ts` | Replay playhead: start/exit, play/pause, speed, frame cache + prefetch | `App` |
| `utils/status.ts` | Status / feed / severity / strength colours, words and icons | most components |
| `utils/format.ts` | Local time, "x s ago", numbers, percentages, units | most components |
| `utils/alerts.ts` | `deriveAlerts()`: the few alerts worth showing (agent alerts, zone status, feed problems), most severe first | `AlertsCard`, `DemoPill` |
| `utils/geo.ts` | Seeded scatter inside a cell (stable rain-cell positions) | `CityMap` |
| `utils/grid.ts` | Block IDs ↔ grid position, **hotspots** (touching unusual blocks grouped into one story), place names | `CityMap`, `alerts.ts` |

### `src/components/`

| File | Purpose |
|---|---|
| `Header.tsx` | Slim header: logo, pulse heart (colour = worst zone, speed = bpm), LIVE/DEMO/REPLAY + clock, data-health chip (feed details on click), Insights / Replay / Demo |
| `AlertsCard.tsx` | Compact "Active alerts" card, capped at 4 (2 on phones); click an alert to open its zone |
| `DemoPill.tsx` | Floating scenario progress + playback when the Demo drawer is closed |
| `drawers/Drawer.tsx` | Shared glass drawer shell (title, close, Esc) |
| `drawers/DemoDrawer.tsx` | Scenarios (preset cards, storyline beats, pause/speed/reset), Custom sliders, Feed failures |
| `drawers/InsightsDrawer.tsx` | Summary, agent alerts, status heat-map timeline and live signal stream |
| `SummaryPanel.tsx` | "Right now" headline + three-part explanation; `SourceTag` (Rule-based / AI-assisted) |
| `AlertsList.tsx` | Monitoring-agent alerts: observed · possible link · causation note |
| `EventTicker.tsx` | Live civic signal stream (reports, anomalies, links, alerts, feed changes) |
| `PulseTimeline.tsx` | Zone × time heat-map of statuses over the last 30 minutes |
| `ReplayBar.tsx` | Replay controls: play/pause/step/speed, zone × time scrubber, key-moment chips, back to live |
| `ui/StatusBadge.tsx` | Status pill with colour + icon + word |
| `map/CityMap.tsx` | Leaflet map of Jaipur on a canvas: district lines (5 × 5) and faint block lines (3 × 3), A–E/1–5 references, district names when zoomed in, tint only on unusual blocks, one label per hotspot, rain, congestion on real roads, incident clusters, air, sensors; click/hover by grid arithmetic; layers redraw only when their content changes |
| `map/markers.tsx` | Cached Leaflet `divIcon`s: hotspot labels, grid references, selected-area tag, incident clusters, air-quality marker |
| `map/MapControls.tsx` | `LayerToggles` and the collapsible `PulseLegend` |
| `map/mapColors.ts` | Concrete colours for Leaflet SVG (CSS variables don't work there) |
| `zone/ZonePanel.tsx` | Area panel: a simple 10-second view (status, "What you'd notice", "What to do") and, behind **Explain in detail**, the full story (what's happening, evidence, possible relationship, advice) + "Show the data behind this" |
| `zone/MetricCard.tsx` | One signal: current, normal, deviation, severity, trend, sparkline, rule |
| `zone/InsightCards.tsx` | `RelationshipCard` (strength meter + "Why this flag?") |
| `zone/SignalChart.tsx` | 15-minute chart: rain bars + traffic / bus / AQI indexed to 100 = normal |
