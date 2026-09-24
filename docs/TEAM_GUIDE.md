# CityPulse — Team Guide

A plain-language guide for every team member. Read this once and you should be able to explain
any part of CityPulse to a judge, run it, and change it safely. Deeper detail lives in
[ARCHITECTURE.md](ARCHITECTURE.md); file-by-file notes in [FILE_GUIDE.md](FILE_GUIDE.md).

---

## 1. Project overview

CityPulse is a website that shows how a city is doing *right now*. It combines five kinds of
civic data, spots anything unusual, notices when unusual things might be connected, and explains
it all in plain words on a map. Tagline: **"Understand what's happening in your city — at a
glance."**

## 2. The problem statement (AmiHacks Track B)

Civic data — weather, traffic, transit, complaints, air quality — exists but is scattered across
disconnected feeds with different formats, clocks and update rates. The brief asks for a system
that fuses at least three feeds into a common model, detects anomalies or correlations, shows a
live glanceable map/dashboard, and writes a plain-language summary — while working with public
or synthetic data, degrading gracefully when feeds fail, protecting privacy, being readable in
~10 seconds, and **never presenting a possible link as a confirmed cause**.

## 3. Target users

- **Primary:** residents. They get the map and the one-line headline.
- **Secondary:** city staff, journalists, emergency responders, small-business owners. They use
  the zone panel for evidence.

## 4. Our solution in one paragraph

Five feeds (weather, traffic + buses, 311-style reports, air quality, street water sensors)
arrive in five messy formats. CityPulse converts them into one common format, learns what
"normal" looks like for each zone at each time of day, flags values that are far from normal,
links unusual signals only when a sensible rule, the same zone and the same 10-minute window all
agree, and turns the result into a map, plain-language summary and alerts. If a feed breaks, it
says so and carries on.

## 5. Architecture (the big picture)

```
feeds → feed manager → normalization → common data model → rolling store
      → analysis engine → civic state → { map + dashboard, summary, monitoring agent }
```

Think of it as an assembly line that runs every **3 seconds** (one run = one "tick"). The
website only ever reads the finished product of the latest tick.

## 6. The frontend (what users see)

Built with **React** (a library for building UIs out of reusable components) and **TypeScript**
(JavaScript with types, which catches mistakes early), bundled by **Vite**, styled with
**Tailwind CSS** (utility classes like `p-3` for padding).

- **Top bar:** logo, the *pulse strip* (a heartbeat line — colour = worst zone, speed = how much
  is unusual), feed-health chips, live clock.
- **Left column:** "Right now" summary, monitoring-agent alerts, live signal stream (and demo
  controls when opened).
- **Map (the hero):** zones coloured green/amber/red with a status word and icons; rain circles;
  report dots; optional IoT sensors; legend; status heat-map.
- **Zone panel:** click a zone to investigate — signals vs normal, possible relationships with
  "Why this flag?", a 15-minute chart, recent reports, the agent's reasoning.
- **Replay bar:** in replay mode, controls to play back a recorded storm.

Data arrives by **polling**: the browser asks `/api/dashboard` every 3 seconds.
Main file: `frontend/src/App.tsx`.

## 7. The backend (the brains)

Written in **Python** with **FastAPI** (a web framework that turns Python functions into HTTP
endpoints and validates inputs automatically using **Pydantic** models).

| Folder | Job |
|---|---|
| `data_sources/` | the synthetic city + each feed's raw format + live API clients |
| `normalization/` | convert raw formats to the common model |
| `analysis/` | baselines, anomalies, correlation, risk, zone status |
| `ai/` | plain-language summaries (templates + optional AI) |
| `agent/` | the monitoring agent |
| `simulation/` | demo events, full scenario, history, replay |
| `services/` | the pipeline that ties it together, feed manager, storage |
| `api/` | the HTTP endpoints |

Entry point: `backend/app/main.py`. The orchestrator: `backend/app/services/pipeline.py`.

## 8. The database

**SQLite** — a database stored in one file (`backend/data/citypulse.db`), no server needed. We
talk to it through **SQLAlchemy** so we could switch to PostgreSQL by changing one setting. It
stores 3 days of history (to learn "normal"), the recorded storm for replay, live readings,
alerts and status snapshots. The live analysis doesn't depend on it — if the database breaks,
the map keeps working. Details: [DATABASE.md](DATABASE.md).

## 9. Data flow — one tick, step by step

1. **Simulation step:** if a scenario is running, apply any due event (e.g. start rain).
2. **Poll feeds:** each feed that is due fetches its raw data (with fallbacks if it fails).
3. **Normalize:** raw → common records; bad records rejected with reasons.
4. **Store:** add to the in-memory rolling store (last 40 min); save to the database.
5. **Analyse:** for every zone and metric — current vs baseline, anomaly? related signals?
   risk? status?
6. **Agent:** decide which alerts to open, update or resolve.
7. **Summarize:** write the plain-language summary.
8. **Ticker/timeline:** record what changed.
9. **Publish:** the new civic state replaces the old one; the API serves it.

## 10. Normalization

"Normalization" means making different things comparable. Examples from our feeds:

| Raw | Normalized |
|---|---|
| `"temp_f": 86.1` | `temperature_c = 30.1 °C` |
| `"precip_mm_15min": 2.0` | `rain_mm_h = 8.0 mm/h` |
| `"speedKph": 22.5, "freeFlowKph": 45` | `congestion_pct = 50 %` |
| `"R-312,EST,420,24/09/2026 15:07"` (CSV) | Zone 3, `transit_delay_min = 7`, UTC time |
| `"epochMs": 1790242200000` | `2026-09-24T09:30:00Z` |
| Open311 report with `account_id`, `contact_phone` | anonymous report — personal fields dropped |

Every normalized record has the same fields: source, zone, UTC timestamp, metric, value, unit,
data status (live / simulated / fallback). Code: `backend/app/normalization/`.

## 11. Baseline calculation

A **baseline** is "what's normal". Normal depends on place and time, so we learn one baseline per
**zone × metric × half-hour of the day** from three days of history.

We use the **median** (the middle value when sorted) rather than the average, because one
extreme event (like a storm) pulls an average but barely moves a median. For report counts we
take the median rate across days for the same reason.

Code: `backend/app/analysis/baseline.py`.

## 12. Anomaly detection

For each signal: **current value** (average over the last minute or so), **baseline**,
**% deviation** = (current − baseline) ÷ baseline × 100, and a **rule**:

- Traffic: ≥ 30 % above normal · bus delays: ≥ 50 %
- Rain: ≥ 7.6 mm/h (the meteorological definition of heavy rain — % change makes no sense when
  normal is zero)
- Street water: ≥ 15 cm · air quality: AQI ≥ 150 or ≥ 25 % above normal
- Report counts: at least 3, ≥ 40 % above normal, **and** unlikely by chance (a **Poisson test**
  — the maths of random arrivals — with a strict 0.1 % level)

**Severity** grows with how far past the threshold it is. Example: traffic 147 vs normal 100 =
+47 % → anomaly (moderate). All thresholds live in `backend/app/config.py`.

## 13. Rolling-window correlation

A **rolling window** is "the last N minutes", always moving forward (ours: 10 minutes).

Two unusual signals are called a **possible relationship** only if:
1. a rule says they can plausibly be connected (e.g. rain → traffic),
2. both are anomalous,
3. same zone,
4. both inside the 10-minute window,
5. the timing fits (traffic didn't start rising well before the rain).

We then score the evidence (weak / moderate / strong), including **co-movement** — a
correlation number (−1 to 1) showing whether the two signals rose and fell together. The wording
is always "may be related" + "not a confirmed cause". If a signal is unusual with nothing
related, we say "insufficient evidence". Code: `backend/app/analysis/correlation.py`.

## 14. Possible-impact prediction

- **Early warning:** rain is heavy and traffic is already rising (≥ +10 %) but hasn't hit the
  30 % threshold → "Traffic may slow in Zone 3". Similar for rising street water.
- **Potential disruption:** a moderate/strong relationship **and** two or more serious anomalies
  → "Elevated traffic disruption risk in Zone 3" + advice for residents.

Zone colour: **red** for potential disruption, **amber** for any anomaly/link/warning, **green**
otherwise. Code: `backend/app/analysis/risk.py`.

## 15. AI explanation

The **analysis engine is the source of truth; the AI only rephrases.**

1. A **template** (fixed sentences filled with numbers) always writes the summary first.
2. If an Anthropic API key is set, the facts are sent to Claude, which returns a friendlier
   version in a fixed JSON shape.
3. A **validator** throws that text away if it contains a number not in the facts, causal words
   ("caused", "due to"…) or a zone that isn't flagged.
4. If anything fails, the template stays. The UI shows "Rule-based" or "AI-assisted".

Code: `backend/app/ai/`.

## 16. Monitoring agent

A small program that runs after every tick and acts like a duty officer: checks feeds, data
quality, anomalies, related signals and the time window, then decides whether to **open**,
**escalate** or **resolve** an alert. It waits for 3 clean checks before resolving (so alerts
don't flicker) and records its reasoning ("Checked 5 feeds: all healthy…"). Each alert keeps
*observed facts*, *possible relationship* and *"not a confirmed cause"* separate.
Code: `backend/app/agent/monitor.py`.

## 17. Simulation and replay

- **Demo events:** heavy rain, traffic spike, outage cluster, poor air — in any zone. They change
  the simulated *city*; CityPulse must detect them like it would real events.
- **Full scenario:** rain over Zone 3, then an unrelated traffic build-up in Zone 1 (to show we
  don't blame the rain). Stages tick only when the analysis actually detects them. ~90 s to red.
- **Feed faults:** outage, delay, malformed — for any feed.
- **Historical replay:** yesterday's recorded storm, replayed minute by minute through the same
  engine and agent, labelled "ARCHIVE / not live".

Code: `backend/app/simulation/`. Script: [DEMO.md](DEMO.md).

## 18. The map

**Leaflet** draws the map; the background tiles come from **OpenStreetMap** (free, no key),
darkened with a CSS filter. Zones are **demonstration zones** over central Delhi — not official
boundaries (the legend says so). Each zone label shows: name, status word, icons for what's
unusual, and "⟷ possible link" if one exists. Clicking a zone zooms to it and opens the panel.
Code: `frontend/src/components/map/`.

## 19. Error handling

- One feed failing can't stop the others (each is polled inside its own try/except).
- A failed tick keeps serving the previous state instead of crashing.
- The API returns friendly errors: 404 unknown zone, 422 invalid input (with field messages),
  generic 500 with no stack trace or secrets.
- The frontend keeps the last good data and shows a "connection lost" banner if the server goes
  away, reconnecting automatically.

## 20. Feed fallback

| Situation | What CityPulse does |
|---|---|
| Live API fails (timeout, error, rate limit, garbage) | Labelled FALLBACK estimate — never shown as live; retries after 60 s |
| Simulated feed fails | Last known values with age (FALLBACK), then UNAVAILABLE |
| Feed goes quiet | DELAYED → STALE → UNAVAILABLE |
| Data missing for a metric | "Not assessed" (not zero); relationships say what can't be checked |
| Some records broken | Rejected one by one; the rest used |

Code: `backend/app/services/feed_manager.py`.

## 21. Security

- Secrets (API keys) only in `backend/.env`, which git ignores; `.env.example` shows the names.
- All inputs validated (Pydantic); zone and feed IDs checked against fixed lists.
- CORS limited to our frontend's address.
- Error responses never include stack traces.
- No accounts or logins — the data is public information and contains no personal data. In a
  real deployment the demo (`/api/simulation/*`) endpoints should be protected or turned off.

## 22. Why these technologies

| Choice | Why |
|---|---|
| Python + FastAPI | great for data work; automatic validation and API docs |
| SQLite + SQLAlchemy | zero setup now, PostgreSQL later with one setting |
| React + TypeScript + Vite | reusable components, type safety, instant reload |
| Tailwind | consistent styling quickly |
| Leaflet + OpenStreetMap | free, reliable maps, no API key |
| Recharts, lucide icons | lightweight charts and accessible icons |
| Rules + statistics, not heavy ML | explainable, works without training data, easy to defend |
| Claude (optional) | only rephrases verified facts; always checked; never required |

## 23. How to run

Backend (terminal 1):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Tests: `cd backend && python -m pytest -q` (99 should pass).
Full guide: [SETUP.md](SETUP.md).

## 24. How to modify common things

**Change a threshold** — edit `backend/app/config.py` or set an environment variable, e.g.
`CITYPULSE_TRAFFIC_THRESHOLD_PCT=25`. Restart the backend.

**Change the rolling window** — `CITYPULSE_ROLLING_WINDOW_MINUTES=15`.

**Add a relationship rule** — add a `Rule(...)` to `RULES` in `analysis/correlation.py`, then
add a headline and resident advice for its `id` to `_DISRUPTION_HEADLINES` and `_ADVICE` in
`analysis/risk.py` (both are required). Add a test in `tests/test_analysis.py`.

**Add a new metric / feed:**
1. `data_sources/<feed>.py` — produce the raw payload (or call the real API).
2. `normalization/normalizers.py` — a normalizer returning `CivicReading`s; add a valid range
   in `normalization/units.py`.
3. `services/feed_manager.py` — add a `FeedSpec` to `FEEDS` with its interval.
4. `analysis/metrics.py` — describe the metric (label, unit, mode, icon); add a rule in
   `analysis/anomaly.py` if it isn't "info only".
5. Frontend — add an icon in `utils/status.ts` (`METRIC_ICONS`) and the key to `CARD_ORDER`
   in `components/zone/ZonePanel.tsx`.
6. Tests in `tests/test_normalization.py`.

**Add a zone** — add a `Zone(...)` in `geo/zones.py`, its character in `ZONE_CHARACTER`
(`data_sources/city_model.py`), a bus area code and route in `data_sources/traffic.py`, and widen
the `zone_id` pattern in `api/routes.py` (`^Z[1-5]$`). Delete the database so history is
regenerated.

**Change the look** — colours are CSS variables at the top of `frontend/src/index.css`; map
colours in `components/map/mapColors.ts`.

## 25. Common errors

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: No module named 'app'` | Run commands from inside `backend/` (or `python -m pytest` there). |
| "Connecting to CityPulse…" forever | Backend isn't running on port 8000. |
| `Address already in use` | Something else uses the port — stop it or pick another `--port`. |
| Map has no streets | No internet for map tiles; everything else works. |
| All zones flicker amber after editing thresholds | Thresholds too tight for the noise — revert or loosen; run the tests. |
| `KeyError` in `risk.py` after adding a rule | Add the rule's headline and advice to `_DISRUPTION_HEADLINES` and `_ADVICE`. |
| Replay says "No recorded event found" | History wasn't generated — restart the backend once (or delete the database file). |
| Tests fail after changing the city model | Some tests rely on its timing (e.g. red within ~90 s) — check `test_ai_agent_simulation.py`. |
| Stuck in a weird demo state | Demo controls → **Normal state**. |
