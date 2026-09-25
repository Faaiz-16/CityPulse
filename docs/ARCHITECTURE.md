# CityPulse — Architecture

This document explains how CityPulse turns disconnected civic feeds into one understandable
"pulse". It is written for someone new to the codebase; technical terms are explained the first
time they appear.

---

## 1. The pipeline in one picture

```
 CIVIC SOURCES (5 feeds, 5 different raw formats)
   weather · traffic/transit · 311-style reports · air quality · IoT water-level sensors
        │   (synthetic city model by default; Open-Meteo live API optional)
        ▼
 FEED MANAGER ── fallback chain + health status (LIVE / SIMULATED / FALLBACK / DELAYED / STALE / UNAVAILABLE)
        ▼
 NORMALIZATION ── field mapping · UTC timestamps · unit conversion · zone mapping · validation · PII removal
        ▼
 COMMON CIVIC DATA MODEL  (CivicReading / CivicIncident)
        ▼
 ROLLING STORE (in memory, last 40 min)  ──►  DATABASE (history, alerts, snapshots — best effort)
        ▼
 ANALYSIS ENGINE
   baselines (median/MAD by time of day) → anomaly detection → rolling-window correlation
   → possible-impact / risk insight → zone status GREEN / YELLOW / RED
        ▼
 STRUCTURED CIVIC STATE  (CityState — the single source of truth)
        ├──► MAP (React + Leaflet)             "What / where / how serious?"
        ├──► AI / NLP layer                     plain-language summary (template or validated LLM)
        └──► MONITORING AGENT                   opens / escalates / resolves alerts
                     ▼
              DETAILED DASHBOARD (zone panel)   "Why might this be happening?"
```

One **tick** of this pipeline runs every 3 seconds (`CITYPULSE_TICK_SECONDS`). The API never
computes anything on request — it serves the latest `CityState`, so it stays fast even when a
feed or the AI service is slow.

## 2. Technology choices

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic, SQLAlchemy, Uvicorn | Fast to build, automatic request validation, typed data models |
| Database | SQLite (WAL mode) | Zero setup for a 24-hour hackathon. All access goes through SQLAlchemy, so PostgreSQL is a one-line URL change |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4 | Component-based UI, type safety, instant dev reload |
| Map | Leaflet + react-leaflet, OpenStreetMap tiles | Free, no API key, reliable |
| Charts | Recharts | Lightweight React charts |
| Icons | lucide-react | Consistent, accessible SVG icons |
| AI | Anthropic Claude API (optional) | Rewrites structured facts into friendlier language; always validated, always optional |
| Live data | Open-Meteo weather + air-quality APIs (optional) | Free, no key, stable |

**Live updates use polling** (the browser asks for `/api/dashboard` every 3 s) rather than
WebSockets. Polling is simpler, survives network blips automatically and is plenty fast for a
civic dashboard.

## 3. Data sources and their raw formats

The brief says the hard part is fusing feeds that *disagree* about format, time and units. The
synthetic feeds deliberately reproduce real-world messiness:

| Feed | Raw format (vendor style) | Timestamp style | Units / identifiers to reconcile | Update interval |
|---|---|---|---|---|
| Weather | "CPMET" rain-gauge JSON | ISO-8601 with `+05:30` offset | rain in **mm per 15 min**, temperature in **°F**, wind in **m/s**; station IDs | 10 s |
| Weather (live, optional) | Open-Meteo JSON | ISO without zone (UTC) | precipitation per 15-min interval | 10 min |
| Traffic — roads | "TSN v2" JSON, camelCase | **epoch milliseconds** | raw **speed**; congestion must be derived from speed ÷ free-flow speed; sensor IDs | 5 s |
| Traffic — buses | **CSV text** | **day-first local** `24/09/2026 15:07` | delay in **seconds**; operator area codes `CEN/NTH/EST/…` instead of zone IDs | 5 s |
| Civic reports | Open311 GeoReport v2 JSON | ISO-8601 `Z` (UTC) | free-text service names ("Water Logging"); `long` not `lon`; **may contain personal fields** | 5 s |
| Air quality | OpenAQ-like JSON | nested `date.utc` | **PM2.5 only** — CityPulse computes the US AQI itself | 20 s |
| Air quality (live, optional) | Open-Meteo JSON | ISO without zone (UTC) | provides `us_aqi` + `pm2_5` | 10 min |
| IoT water level | MQTT-style messages | **epoch seconds** | sensor ID hidden in the topic; value in **mm** inside a JSON *string* | 10 s |

### The synthetic city (`data_sources/city_model.py`)
A deterministic "ground truth" for every zone and moment:

```
value = daily pattern (rush hours, evening air-quality peak) × zone character
        + active simulation effects (rain, flooding, traffic, accident, outage, poor air)
        + small noise seeded from (seed, zone, metric, time)
```

Seeded noise means the same inputs always give the same outputs — demos and tests are
repeatable. Simulation **effects** change the city, not the analysis: a heavy-rain effect raises
rainfall immediately, then congestion (+20 s lag), water levels (+25 s), waterlogging reports
(+25 s) and bus delays (+30 s). The analysis has to *discover* those relationships.

## 4. Normalization → the common data model

Every record becomes one of two shapes (`app/schemas.py`):

**`CivicReading`** — a measurement
`source, source_type, provider, zone_id, timestamp (UTC), ingested_at, metric, value, unit,
confidence, data_status (live | simulated | fallback), sensor_id, lat, lon, metadata`

**`CivicIncident`** — an anonymous report
`id, source, zone_id, timestamp, ingested_at, category, severity, lat, lon, confidence,
data_status, metadata` — there is deliberately **no field that could hold personal data**.

Each normalizer (`normalization/normalizers.py`) does six things per record:
1. map vendor field names → common names,
2. parse the timestamp convention → timezone-aware UTC (`timestamps.py`),
3. convert units → canonical units (`units.py`: mm/h, °C, km/h, %, min, µg/m³, AQI, cm),
4. map the location/identifier → a zone (sensor registry, operator code table, or
   point-in-polygon test),
5. validate the value against a plausible range,
6. **reject bad records one by one** with a reason, so good records keep flowing.

Timestamps in the future (> 5 min skew) are rejected. For reports, only whitelisted fields
survive; account IDs and phone numbers are dropped and never stored.

## 5. Areas — Jaipur as districts and blocks

Jaipur is laid out on a two-level grid (`geo/zones.py`), like a paper map with an inset:

- **Districts** — **5 × 5**, about 4.5 km each. Columns **A–E** run west → east and rows **1–5**
  north → south. Each is named after its best-known locality (C2 = "Walled City").
- **Blocks** — every district is split into **3 × 3** blocks of about 1.5 km, numbered **1–9** like
  a phone keypad (1 = north-west, 5 = centre, 9 = south-east). A block ID is `C2-9`: block 9 of
  district C2. That makes **225 blocks**.

The **block is the unit of analysis**: each has five simulated sensors (2 traffic sensors placed
**on real main roads**, 1 rain gauge, 1 air monitor, 1 water-level sensor), its own baselines and
its own status. Districts are how people read the city — names, grid references and labels.
Blocks are named after a locality inside them ("Walled City (C2-9)", "Mansarovar (B4-5)") or
after their district and position ("Walled City · north-east"). They are *not* official wards
and the UI says so. Mapping a coordinate to a block is simple arithmetic on the grid.

Main-road shapes come from **OpenStreetMap** (© OpenStreetMap contributors, ODbL): downloaded
once, simplified and split at cell edges by `backend/scripts/build_jaipur_roads.py` into
`geo/jaipur_roads.json` (~95 KB), served at `/api/map`. The map colours each road stretch by its
block's traffic.

The synthetic city gives each block a character: busier near the Walled City and C-Scheme
(more traffic and reports), worse air around the VKI and Sitapura industrial areas, cleaner in
the Nahargarh hills. An event is centred on one block and reaches its neighbours with decreasing
strength (Gaussian falloff), so it shows up as a realistic **hotspot**: heavy rain ≈ 13 blocks (9
red) around the Walled City, a road accident exactly one block.

## 6. Baselines — "what is normal here, now?"

Traffic at 9 a.m. is not comparable with traffic at 3 a.m., so baselines are learned per
**zone × metric × half-hour of the day** from 3 days of stored history (`analysis/baseline.py`).

We use the **median** (middle value) and **MAD** (median absolute deviation) instead of mean and
standard deviation. They are *robust*: the recorded storm in the history barely moves them.
Neighbouring half-hours are pooled (±30 min) so each baseline has enough samples.

Report baselines are **rates** (reports per minute) for the same time-of-day slot, turned into
an "expected count" for the rolling window.

If no history is available (e.g. the database is down at start-up), documented default
baselines are used and the UI shows `baseline_history_days = 0`.

## 7. Anomaly detection (`analysis/anomaly.py`)

For every metric CityPulse computes: **current value** (mean over the current window),
**baseline**, **% deviation**, a **robust z-score**, the **threshold rule**, **anomaly yes/no**,
**severity** and **trend** (rising / falling / steady over the last 3 minutes).

| Metric | Rule | Default threshold (`config.py`) | Severity |
|---|---|---|---|
| Traffic congestion | relative | ≥ **+30 %** vs baseline | low · moderate ≥ 1.4× · high ≥ 2× threshold |
| Bus delays | relative | ≥ **+50 %** | same scaling |
| Rainfall | absolute | ≥ **7.6 mm/h** (meteorological "heavy rain") | high ≥ 15.2 mm/h |
| Street water level | absolute | ≥ **15 cm** | high ≥ 30 cm |
| Air quality (US AQI) | hybrid | AQI ≥ **150** *or* ≥ **+25 %** vs baseline | high ≥ 200 |
| Report counts (all / waterlogging / outages) | count + statistics | ≥ **3** reports, ≥ **+40 %** and **Poisson p < 0.001** | by count and size |

Why an absolute rule for rain: normal rainfall is ~0, so "+900 %" is meaningless.

Why a Poisson test for reports: reports arrive randomly. Seeing 4 when ~2 are expected happens
all the time. The Poisson tail probability says how likely a count is *by pure chance*; because
we check 225 blocks × 4 report types every 3 seconds, a strict level (0.1 %) avoids false alarms
from multiple comparisons (measured: over two simulated rush hours, one area was briefly amber and
none turned red).

Example from the brief: traffic 147 vs baseline 100 → +47 % ≥ 30 % → **anomaly (moderate)**.

## 8. Rolling-window correlation (`analysis/correlation.py`)

A relationship is only *considered* when all of these hold:

1. a **logical rule** says the signals can plausibly be connected,
2. the "driver" **and** at least one "response" signal are **anomalous**,
3. they are in the **same zone**,
4. they are inside the same **rolling window** (default **10 min**),
5. the **timing fits** (the response did not clearly start before the driver).

| Rule | Driver | Response(s) | Supporting |
|---|---|---|---|
| `rain_traffic` | rainfall | traffic congestion | bus delays |
| `rain_flooding` | rainfall | waterlogging reports, street water level | — |
| `outage_traffic` | power/signal outage reports | traffic congestion | bus delays |
| `accident_traffic` | road-accident reports | traffic congestion | bus delays |
| `traffic_transit` | traffic congestion | bus delays | — (dropped when another link already explains the bus delays) |
| `traffic_air` | traffic congestion | air quality | — |

**Evidence score** (0–1): 0.40 base + up to 0.15 each for driver and response severity + 0.15
if timing fits (−0.10 if not) + up to 0.10 for **co-movement** (Pearson correlation of the two
series in 20-second bins over the window) + up to 0.10 for extra/supporting signals.
**Strong ≥ 0.8 · Moderate ≥ 0.6 · Weak** otherwise.

Wording is fixed: *"…are occurring in the same zone and time window. These signals may be
related."* Every relationship carries the caveat *"a possible link … not a confirmed cause."*
Weak relationships are shown as **insufficient evidence**.

What CityPulse says when there is **no** relationship:
- a driver alone (rain, nothing else unusual) → *"no disruption link detected"*,
- a response alone (traffic up, nothing related) → *"insufficient evidence to suggest any
  explanation"*,
- a feed is down → *"Weather data is unavailable, so CityPulse cannot check whether heavy
  rainfall is linked to …"*.

## 9. Possible impact / risk insight (`analysis/risk.py`)

| Insight | Condition | Example headline |
|---|---|---|
| **Potential disruption** (high) | ≥ 1 moderate/strong relationship **and** ≥ 2 anomalies of moderate+ severity in the zone | "Elevated traffic disruption risk in Walled City (C2-9)" |
| **Early warning** (elevated) — traffic | rain anomalous, congestion ≥ +10 % and **rising**, but below the 30 % threshold | "Traffic may slow in Walled City (C2-9)" |
| **Early warning** — water | rain anomalous, water level ≥ half the flag level and rising | "Water may collect on streets in Walled City (C2-9)" |

Early warnings address the brief's pain point "alerts are reactive, not predictive": they fire
*before* the second signal crosses its threshold, and they say so.

### Zone status
- **RED — Possible disruption:** a potential-disruption insight, or ≥ 2 high-severity anomalies.
- **YELLOW — Attention:** any anomaly, relationship or early warning.
- **GREEN — Normal:** nothing unusual.

Status is always shown as **colour + icon + word**, never colour alone.

### Predictive impact — what may happen next (`analysis/forecast.py`)

After every block is analysed, well-known knock-on effects turn what is unusual *now* into
possible impacts *next*, in the same block and (more weakly) the 8 neighbouring blocks:

| Observed | Possible next — here | Possible next — neighbouring blocks |
|---|---|---|
| Heavy rain | flash flooding, power cuts, slower traffic, bus delays | flash flooding, power cuts, slower traffic |
| Rising street water | flash flooding, slower traffic, power cuts, bus delays | flash flooding, slower traffic |
| Waterlogging reports | slower traffic, bus delays, power cuts | flash flooding, slower traffic |
| Heavy traffic | bus delays, worse air | slower traffic |
| Road-accident reports | slower traffic, bus delays | slower traffic |
| Power / signal outages | slower traffic (dark signals), bus delays | power cuts, slower traffic |
| Poor air | — | worse air |

Each prediction's score is the driver's strength (e.g. rain intensity, anomaly severity) × the
rule's weight; it is shown as a **low / medium / high chance** with a rough time horizon and the
observed conditions it is based on. Impacts already being measured in a block are not predicted
there, and worse air is not predicted where it is raining (rain washes particles out). Every
block's panel and hover card list "What may happen next" (the map's dashed violet "Outlook" layer
is switched off for now, `SHOW_OUTLOOK` in `CityMap.tsx`). Predictions are labelled as
possibilities, never as causes or certainties.

## 10. Feed resilience (`services/feed_manager.py`)

```
Feed with a live public API (weather, air quality):
   live API ──ok──► LIVE
      │ timeout / HTTP error / 429 rate limit / malformed JSON / no usable records
      ▼
   synthetic estimate labelled FALLBACK ("not live data")  + 60 s back-off before retrying live

Feed whose upstream is the synthetic city (traffic, reports, sensors):
   OK ──► SIMULATED
   failing ──► FALLBACK (last known values, age shown) ──► UNAVAILABLE after the cache TTL
   silent  ──► DELAYED (> 3 intervals late) ──► STALE (> 8 intervals) ──► UNAVAILABLE (> 10 min)
```

Rules that keep the system honest:
- Nothing is ever labelled LIVE unless it came from a real API.
- Live values stay "current" for the upstream's own publishing cadence (Open-Meteo weather
  15 min, air quality 60 min), not our polling rate; the in-memory store keeps 3 hours for this.
- Stale/cached data is displayed with its age but **ages out of the analysis window** — it is
  not treated as current.
- Missing data makes a metric `available: false` ("not assessed"), never zero.
- Every feed is polled inside its own `try/except`; one broken feed cannot stop the others.
- Report feeds catch up after an outage (they ask for everything since the last success).

**Database resilience:** analysis reads only the in-memory store. Every database call is
best-effort (`services/persistence.py`); on failure the pulse keeps running,
`/api/health` reports `storage: degraded`, and default baselines are used if history can't load.

**API errors:** validation problems return `422` with field messages; unknown zones `404`;
unexpected errors return a generic `500` message — stack traces stay in the server log.

## 11. AI / NLP layer (`app/ai/`)

```
CityState ──► facts.py (compact fact sheet) ──► templates.py ──► always-available summary
                                   │
                                   └──► llm.py (Claude, structured output) ──► validator.py ──► shown only if it passes
```

- The **template** summary is built every tick and is the default.
- If `ANTHROPIC_API_KEY` is set and the *situation* changes (fingerprint of statuses,
  anomalies, relationships and feed health), an LLM rewrite is requested **in a background
  thread** — the pipeline never waits for it; at most one call per 20 s.
- The model sees only the fact sheet, never raw feeds, and must return a fixed JSON shape
  (`messages.parse` with a Pydantic schema).
- The **validator** rejects the text if it contains any number not present in the facts, any
  causal phrase ("caused", "due to", "led to", "because of", …) or a zone that isn't flagged.
- Any failure (no key, network, timeout, rate limit, refusal, validation) → the template stays.
  The UI labels which one is shown: *Rule-based* or *AI-assisted*.

## 12. Monitoring agent (`agent/monitor.py`)

Runs after every analysis tick:

```
CHECK FEEDS → CHECK DATA QUALITY → CHECK ANOMALIES → CHECK RELATED SIGNALS
  → CHECK ROLLING WINDOW → DECIDE → OPEN / ESCALATE / RESOLVE ALERTS → EXPLAIN (trace)
```

- Alert types: potential disruption (critical), early warning, possible link, highly unusual
  single signal, feed data-quality problem.
- Each alert stores **observed** facts, the **possible relationship** and a fixed **causation
  note** separately.
- **Hysteresis:** an alert resolves only after its condition is absent for 3 consecutive checks,
  so noise doesn't make it flicker. Lower alerts for a zone are folded into its critical alert.
- The last reasoning trace is shown in the zone panel ("Monitoring agent — last check").
- It is rule-driven: it can only raise alerts about facts present in the civic state.

## 13. Simulation and demo (`app/simulation/`)

- **Scenario presets** (`scenarios.py`), each at a real Jaipur place: Heavy rainfall (Walled City,
  C2-9), Flash flood (Mansarovar, B4-5), Major congestion (C-Scheme, C3-2), Road accident (Ajmer Road near
  Heerapura, A3-9), Power outage (Malviya Nagar, C4-6), Poor air quality (VKI Industrial Area, B1-3),
  Severe storm (Jagatpura, D5-3) and Multi-event evening (Walled City + an unrelated jam in Vaishali
  Nagar, B3-1, that must *not* be linked to rain). Each is a
  timed list of effects plus a **storyline** of beats (e.g. rain begins → traffic builds → water
  rises → reports → possible relationship → possible disruption).
- Beats are ticked off from the **actual analysis output** (value, deviation, anomaly flag, link
  or status checks), never a timer — the storyline proves what the system detected and when.
- **Instant start (default).** Choosing a scenario shows the developed situation straight away:
  the scenario is started ~2 minutes in the past and the pipeline is **fast-forwarded** through
  that time in 5-second ticks — the same feeds, normalization, analysis and agent as live, just
  computed at once (~2 s). Storyline beats keep their real detection times ("after 95 s").
  `instant=False` starts it now to watch it unfold, with pause and 2×/4×.
- **Scenario clock** (`SimClock` in `city_model.py`): effects are evaluated in scenario time,
  which can **pause** or run at **1×/2×/4×**. Analysis windows stay on the real clock, so at 2×/4×
  the same story unfolds in less real time.
- Effects ramp in with realistic lags (rain first, traffic minutes later). Event-driven reports use
  a deterministic accumulator so the report surge is reliable; background reports stay Poisson.
- **Custom:** sliders for rain, flooding, traffic, accident, outage and air pollution in any zone
  (`set_custom()`), each mapped to the same effects the presets use.
- **Single events** and **feed faults** (outage, delay, malformed — any feed) remain available.
- **Replay recorded storm:** see section 14.
- **Warm-up:** on start and reset, the last 10 minutes are back-filled so rolling windows are
  meaningful immediately.

## 14. Historical replay (`simulation/replay.py`)

Replay answers the brief's optional "historical replay to demonstrate pattern detection working
over past data" — using **stored data**, not the live simulation.

```
stored history ─► find the recorded event (first/last heavy-rain reading in the archive)
   ─► load the 1-minute archive around it ─► rolling store
   ─► step a virtual clock one minute at a time:
        AnalysisEngine (same code as live) ─► MonitoringAgent (fresh instance) ─► templates ─► ticker
   ─► frames (cached)  ─► /api/replay, /api/replay/frames/{i}, /api/replay/frames/{i}/zones/{id}
```

- **The recorded storm** is part of the synthetic history: yesterday evening over Tonk Phatak
  (block `C3-8`, C-Scheme district) and, 15 minutes later and weaker, Malviya Nagar (`C4-6`).
  Recorded events unfold over minutes, so downstream lags are stretched ×15 compared with the
  snappy live demo (`Effect.lag_scale`): rain 18:18 → traffic 18:23 → link 18:25 → disruption 18:26.
- **1-minute archive.** Normal history is every 5 minutes; around the storm it is stored every
  minute (provider `recorded archive (1-min)`) so a 10-minute rolling window has enough points.
  Those extra rows are **excluded from baselines**, and report baselines use the **median across
  days**, so the storm never redefines "normal" (tested).
- **Honest labelling.** Replay frames have `mode = "replay"`, every feed shows **ARCHIVE**, the top
  bar says "Recorded … — not live", and summaries are rule-based.
- **Client-owned playhead.** The browser asks for frame *i* (play, pause, step, 1×/2×/4×, scrub, jump
  to a key moment). Frames are computed once (~0.2 s) and cached, so every viewer sees the same thing.
- **Key moments** use the same stage checks as the live scenario (`storm_stages`), gated so later
  stages only count after rain is detected.
- The monitoring agent returns **snapshots** of its alerts so a stored frame never changes after
  the fact.

## 15. Frontend structure

```
App.tsx  (full-bleed map; everything else floats over it)
├── CityMap ── (canvas) district lines (5 × 5, clear) + block lines (3 × 3, faint) · A–E / 1–5 refs
│             · district names when zoomed in · soft amber/red tint only on unusual blocks
│             · one label per hotspot · rain cells · congestion on real OSM roads
│             · incident clusters (only when unusual) · air haze · IoT sensors
├── Header ── logo · PulseChip (heart: colour = worst zone, speed = bpm) · LIVE/DEMO/REPLAY + clock
│             · DataHealth (one chip, details on click) · Insights · Replay · Demo
├── LayerToggles · PulseLegend (collapsible)
├── AlertsCard ── at most 4 alerts (2 on phones), grouped per hotspot ("Walled City + 12 nearby blocks")
├── DemoPill ── scenario progress + playback while the Demo drawer is closed
├── Left drawers (closed by default)
│   ├── DemoDrawer ── Situations (one click → shown instantly; step-by-step option) · Custom · Feed failures
│   └── InsightsDrawer ── SummaryPanel · AlertsList (agent) · PulseTimeline · EventTicker
├── ZonePanel (right) ── simple view: big status · "What you'd notice" (≤ 3 plain phrases) · "What to do"
│             └── "Explain in detail": what's happening · evidence · possible relationship · residents
│                 └── "Show the data behind this": metrics · "Why these flags?" · chart · reports · agent
└── ReplayBar (replay mode) ── play/pause/step/speed · zone × time scrubber · key moments
```

In replay mode (`useReplay`), every panel reads the current recorded frame instead of the live
state — the same components render both. `usePolling` keeps the last good data when a request fails and shows a "connection lost" banner
instead of blanking the screen.

**Smooth map with 225 blocks.** All map shapes are drawn on a **canvas** (`preferCanvas`) rather
than as SVG elements; the grid is 32 lines, not 225 shapes, and clicks/hover are resolved by grid
arithmetic. Glows are a wide faint stroke under a line instead of CSS filters, floating panels
have no `backdrop-filter` blur (re-blurring on every animation frame was the main source of
zoom lag), tiles are not reloaded mid-zoom, and each layer only redraws when what it shows
changes (derived lists are kept stable across 3-second polls). Measured: 60 fps (worst frame
18 ms) while zooming in and out.

**10-second read:** the default view is the map, a slim header and a few alerts. Normal zones are
faint; attention zones amber; possible disruptions are highlighted red areas with a two-line
label. Everything else is progressive disclosure — one click away.

## 16. Database schema (summary)

| Table | Purpose | Key index |
|---|---|---|
| `zones` | zone names + GeoJSON boundary | PK |
| `civic_readings` | normalized readings (history + live, `is_history` flag; `provider` marks the 1-min replay archive) | `(zone_id, metric, ts)` |
| `incidents` | anonymous reports | `(zone_id, ts)` |
| `alerts` | agent alerts with observed / possible link / causation note | `key` |
| `zone_snapshots` | status every 15 s (heat-map timeline, audit) | `ts` |
| `simulation_events` | log of demo actions | PK |

Anomalies and relationships are **recomputed** from readings every tick (they are derived
data), and recorded per snapshot, so no separate tables are needed. Schema is created with
`Base.metadata.create_all`; for a production deployment, add Alembic migrations.

## 17. Known limitations

- Zones and most data are synthetic; the analysis is designed for real feeds but has not been
  calibrated on them.
- Relationship rules are hand-written from domain knowledge; they can miss unexpected links.
- Correlation ≠ causation: CityPulse can show that signals overlap, never why.
- In live mode the AQI baseline is still learned from synthetic history, so live AQI is judged
  only against the absolute health threshold and shown without a "normal" or % change.
- The LLM path is covered by unit tests with a mocked client; it depends on a valid API key.
- Replay covers one recorded event (the storm in the synthetic archive); it isn't a general
  "pick any time range" explorer.
