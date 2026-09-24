# CityPulse — Presentation

**Format:** 14 slides, about **8 minutes** including a ~3.5-minute live demo (slide 5).
A **5-minute cut** is marked ✂ (skip those slides and shorten the demo to the 2-minute version in
[DEMO.md](DEMO.md)). Speaker notes are in [PITCH_SCRIPT.md](PITCH_SCRIPT.md).

Design guidance: dark background to match the app, one idea per slide, big text, a screenshot or
diagram on most slides. Use the app's colours for status: green `#34d399`, amber `#fbbf24`,
red `#f87171`, "possible link" purple `#c084fc`.

---

## Slide 1 — CityPulse

**Understand what's happening in your city — at a glance.**

- Visual: full-screen screenshot of the map with Zone 3 red
- Footer: team name · AmiHacks Track B

## Slide 2 — The problem: civic information is fragmented

- Weather app · transit app · 311 portal · air-quality site · utility outage map
- Residents learn about the flooded underpass **after** they're stuck in it
- City staff spot patterns only after someone escalates a complaint
- Existing dashboards are built for analysts, not the public

Visual: five disconnected app icons, each saying something different.

## Slide 3 — Why data fusion is hard ✂

| Feed | Time format | Units | Location |
|---|---|---|---|
| Rain gauges | `+05:30` offset | mm per 15 min, °F | station ID |
| Road sensors | epoch milliseconds | raw speed | sensor ID |
| Bus operator | `24/09/2026 15:07` | seconds late | "EST" area code |
| 311 reports | UTC `Z` | free-text category | lat/long + personal data |
| Water sensors | epoch seconds | mm inside a JSON string | MQTT topic |

**And the real challenge:** a genuine link vs a coincidence — and saying which, honestly.

## Slide 4 — Our solution: one honest pulse, map first

```
5 feeds → normalize → one data model → detect → possible links → explain → map
```

- **Map** answers *where · what · how serious* in 10 seconds
- **Zone panel** answers *why might this be happening*
- **Plain language** · **monitoring agent** · **survives feed failures**

Visual: screenshot, normal state, with callouts: status word, pulse strip, feed chips.

## Slide 5 — Live demo

Switch to the browser. Follow [DEMO.md](DEMO.md): normal → scenario → early warning → red →
"Why this flag?" → unrelated spike → weather outage → replay.

## Slide 6 — Architecture

```
CIVIC SOURCES → FEED MANAGER (fallbacks, health) → NORMALIZATION → COMMON DATA MODEL
  → ROLLING STORE → ANALYSIS ENGINE → STRUCTURED CIVIC STATE
                                       ├─ MAP / DASHBOARD
                                       ├─ PLAIN-LANGUAGE SUMMARY (templates + checked AI)
                                       └─ MONITORING AGENT
```

- One pipeline tick every 3 s; the API only serves the latest state
- FastAPI · SQLite · React · Leaflet — runs on a laptop, no paid services

## Slide 7 — Normalization: five formats → one model ✂

- Every record → `CivicReading` or `CivicIncident`
- Timestamps → UTC · units → standard · IDs → zones · values validated
- Bad records rejected **one by one**; good ones keep flowing
- Personal fields dropped at ingestion — never stored

Visual: one messy raw record on the left, the clean normalized record on the right.

## Slide 8 — Detection: normal → unusual → possibly related

1. **Baseline:** what's normal for *this zone at this time of day* (median, robust to past storms)
2. **Anomaly:** current vs baseline vs threshold — e.g. traffic 147 vs 100 = **+47 % → flagged**
3. **Report spikes:** must be statistically unlikely by chance (Poisson test)
4. **Possible relationship:** logical rule + same zone + same 10-min window + timing fits
5. **Possible impact:** early warning *before* the threshold · potential disruption after

## Slide 9 — Honest by design

| Observed | Possible relationship | Not claimed |
|---|---|---|
| "Rainfall 26 mm/h" | "may be related" + evidence + strength | "rain caused traffic" |

- Unrelated spike → *"insufficient evidence to suggest any explanation"*
- Missing feed → *"cannot check whether rain is involved"*
- AI text is rejected if it invents a number or uses causal language

## Slide 10 — Built to survive failures ✂

- LIVE · SIMULATED · FALLBACK · DELAYED · STALE · UNAVAILABLE — always visible
- Live API down → labelled fallback estimate, never shown as live
- Missing data → "not assessed", never zero
- Database down → live pulse keeps running
- AI down → rule-based summary (always generated first)

## Slide 11 — Innovation layer

| From the brief | CityPulse |
|---|---|
| AI/ML anomaly & correlation | Robust baselines, Poisson test, co-movement + lead/lag |
| NLP | Grounded plain-language summaries with a fact-checker |
| Agentic AI | Monitoring agent: checks → decides → alerts → resolves |
| Creative pulse | Heartbeat strip, heat-map timeline, live signal stream |
| Geospatial / IoT | Traffic, rain, air and water-level sensors on the map |
| Historical replay | Yesterday's storm, minute by minute, same engine |

## Slide 12 — Impact and path to a real city

- **Residents:** know before you go · **city staff:** see patterns early · **journalists:**
  evidence, not rumour · **responders:** where to look first
- Real deployment: swap synthetic feeds for real ones (311 portals, GTFS-Realtime transit,
  weather and air-quality APIs, city sensors) — the normalizers, engine, agent and map stay
- Scale: one pipeline per city district, PostgreSQL, the same API

## Slide 13 — What we built in 24 hours ✂

- 5 feeds · 8 normalizers · anomaly + correlation + risk engine · monitoring agent · replay
- Map-first React UI with investigation panel, demo controls and replay
- 104 automated tests · full documentation
- Stack: Python, FastAPI, SQLAlchemy/SQLite, React, TypeScript, Tailwind, Leaflet, Recharts

**Next:** real feeds, subscriptions for residents, relationship discovery reviewed by humans,
optional 3D view.

## Slide 14 — CityPulse

**Disconnected signals → one honest pulse.**
Where. What. How serious. And only *possibly* why.

Thank you — questions?
