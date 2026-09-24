# CityPulse — Requirement Compliance Matrix

Source of truth: *AmiHacks Problem Statement-2 — "CityPulse: The Live Civic Health Dashboard"* (Track B).

This matrix traces every official requirement to the feature that satisfies it, where it is
implemented, how it is tested and when it appears in the demo. A row is marked **✅ Done** only
when the feature has been built and verified (automated tests + manual run in the browser);
**🟡 Partial** means part of it works; **⏳ Planned** means not built yet.

## 1. Expected Solution Capabilities (PDF §5)

| # | PDF requirement | CityPulse feature | Module / code | Test | Demo step | Status |
|---|---|---|---|---|---|---|
| 1 | Ingest 3+ distinct data types | Weather, traffic/transit, 311-style incidents, air quality, plus simulated IoT water-level sensors — each with its **own raw format** | M2 `backend/app/data_sources/` | `test_normalization.py` | Feed-health chips in the top bar | ✅ Done |
| 2 | Normalize + timestamp mismatched feeds into a common model | Per-feed normalizers → `CivicReading` / `CivicIncident` (UTC timestamps, SI units, zone IDs) | M3 `backend/app/normalization/` | `test_normalization.py` | Zone panel shows unit-consistent values + "as of" times | ✅ Done |
| 3 | Detect basic anomalies or correlations | Robust baselines (median/MAD by time of day) → deviation, threshold, severity; rule-based rolling-window correlation with co-movement statistic | M4 `backend/app/analysis/` | `test_analysis.py` | Trigger heavy rain → anomalies, then a "possible link" | ✅ Done |
| 4 | Live, glanceable dashboard or map | Map-first UI: zones coloured GREEN/YELLOW/RED **with icons + words**, pulse strip, ticker; 3-second polling | M8–M11 `frontend/` | Manual + build check | Opening screen | ✅ Done |
| 5 | Plain-language summary — what's happening and why it matters | Template summary (always available) + optional grounded LLM rewrite with numeric grounding validator | M6 `backend/app/ai/` | `test_ai_agent_simulation.py` | "Right now" panel | ✅ Done |
| 6 | *Optional:* threshold alerting | Monitoring agent opens/resolves alerts with observed vs possible-link wording | M12 `backend/app/agent/` | `test_ai_agent_simulation.py` | Alert appears when Zone 3 goes RED | ✅ Done |
| 7 | *Optional:* historical replay | Replays a recorded storm from the stored archive minute by minute through the same analysis engine and agent; scrubber + key moments | M13 `backend/app/simulation/replay.py`, `frontend/src/components/ReplayBar.tsx` | `test_replay.py` | "Replay storm" → play / jump to "Possible relationship found" | ✅ Done |

## 2. Constraints & Considerations (PDF §7)

| PDF constraint | CityPulse feature | Module / code | Test | Demo step | Status |
|---|---|---|---|---|---|
| Public or synthetic data | Deterministic synthetic city model (default); optional Open-Meteo weather/air-quality (free, no key) | M2, M5 | `test_resilience.py` | Feed chips show SIMULATED / LIVE honestly | ✅ Done |
| Degrade gracefully if a feed is missing or delayed | Per-feed status (LIVE, SIMULATED, FALLBACK, DELAYED, STALE, UNAVAILABLE); live→synthetic fallback; analysis says "cannot assess" instead of guessing | M5 `backend/app/services/feed_manager.py` | `test_resilience.py` | Demo panel → Weather → Outage | ✅ Done |
| Privacy — no identifying individuals | Incidents carry only category, coarse location, time; no names/phones; normalizer drops unknown fields | M3 | `test_normalization.py::test_incident_personal_fields_are_dropped` | FILE_GUIDE / Q&A | ✅ Done |
| Understandable in ~10 seconds | Default view = map with 5 zones, one status word each, one-line city summary | M9 | Manual 10-second check | Opening screen | ✅ Done |
| Epistemic honesty — possible links, not causes | Fixed vocabulary ("may be related", "possible link"); banned causal phrases enforced in templates **and** LLM validator; UI labels OBSERVED vs POSSIBLE LINK vs NOT CONFIRMED CAUSE | M4, M6, M10 | `test_ai_agent_simulation.py::test_causal_language_rejected` | "Why this flag?" panel | ✅ Done |

## 3. Hackathon Scope (PDF §8)

| PDF scope item | CityPulse feature | Status |
|---|---|---|
| ≥3 simulated/public feeds normalized into one schema | 5 feeds → `CivicReading` | ✅ Done |
| Simple anomaly/correlation rule on a rolling window | Relationship rules evaluated over a configurable 10-minute window | ✅ Done |
| Live map a non-technical person reads at a glance | Map-first UI | ✅ Done |
| Short plain-language summary grounded strictly in the data | Template + validated LLM | ✅ Done |
| Advanced: ML anomaly detection, agentic monitoring, alerting, historical replay | Robust-z + Poisson statistics, co-movement (Pearson), monitoring agent, threshold alerts, historical replay | ✅ Done |

## 4. Innovation Opportunities (PDF §6)

| Innovation | Implementation | Demo visibility | Fallback if incomplete |
|---|---|---|---|
| AI/ML — anomaly detection & time-series correlation | Robust z-score (median/MAD) alongside % deviation; Pearson co-movement over the rolling window with lead/lag check | "How unusual?" column; "co-movement r=0.9" in evidence | Rule thresholds alone still flag anomalies |
| NLP — plain-language narrative | Claude API (`messages.parse`, Pydantic schema) rewrites structured facts; validator rejects invented numbers or causal claims | "Right now" panel badge: *AI-assisted* vs *Rule-based* | Deterministic template text (always generated first) |
| Agentic AI — continuous monitoring, proactive flags | Monitoring agent runs every tick: checks feed quality → anomalies → related signals → window → opens/updates/resolves alerts; exposes its step trace | Alerts list + "Monitoring agent — last check" trace | Zone status colours still show the same information |
| Creative pulse visualization | Heartbeat strip whose rhythm/colour reflects city state; zone × time heat-map timeline; live narrative ticker | Top bar + bottom timeline | Static status chips |
| Geospatial / IoT | Simulated traffic sensors, rain gauges, air monitors, drain water-level sensors on the map; they feed the **same** normalizer | "Sensors" map layer | Zone-level aggregates only |

## 5. Beyond-the-PDF additions (kept only because they support a PDF requirement)

| Addition | Supports |
|---|---|
| Demo control panel (scenarios, feed-failure toggles) | Reliable judging of anomalies, correlation, graceful degradation |
| "Early warning" risk insight (rain heavy + traffic trending up before it crosses threshold) | PDF §3 pain point "alerts are reactive, not predictive" |
| Power-outage ↔ traffic-signal rule | PDF §3 example: "power outage" and "traffic light down" nearby |
