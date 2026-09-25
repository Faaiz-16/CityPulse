# CityPulse — Final Validation Checklist

The brief's final validation list, with the **evidence** for each item: an automated test, a
real-time drill against the running server, or a manual check in the browser. Last run on
**24 Sep 2026**.

Legend: ✅ verified · ⚠️ verified with a caveat · ❌ not done

---

## Core expected solution

| Item | Status | Evidence |
|---|---|---|
| At least 3 civic feeds | ✅ | 5 feeds in 5 raw formats; all SIMULATED/LIVE in `/api/health` |
| Normalization | ✅ | `test_normalization.py` (units, formats, zone mapping, PII removal) |
| Timestamping | ✅ | `test_every_timestamp_format_maps_to_same_utc_instant` (7 conventions) |
| Zone mapping | ✅ | sensor registry, operator codes, point-in-polygon — `test_normalization.py` |
| Anomaly detection | ✅ | `test_analysis.py` incl. the brief's 147 vs 100 → +47 % example |
| Rolling-window correlation | ✅ | `test_rain_and_traffic_same_zone_produce_hedged_relationship`, timing and "insufficient evidence" tests |
| Live / glanceable map | ✅ | Browser check at 1440×900 and 375×812; screenshots in `docs/screenshots/` |
| Detailed dashboard | ✅ | Zone panel: metrics vs normal, relationships + evidence, chart, reports, agent trace |
| Plain-language summary | ✅ | Template summary every tick; `test_no_api_key_uses_template` |
| Possible-impact / risk insight | ✅ | Early warning at 54 s and disruption at 72 s in the real-time scenario run |
| Graceful degradation | ✅ | Real-time drill: every feed outage → FALLBACK → UNAVAILABLE → recovery; dashboard kept serving |
| Public / synthetic data | ✅ | Synthetic by default; real Open-Meteo weather + AQI verified live (labelled LIVE) |
| Privacy respected | ✅ | `test_incident_personal_fields_are_dropped`; no personal columns in the schema |
| Correlation vs causation distinguished | ✅ | Validator tests; scan of the full live state found no causal wording; unrelated Vaishali Nagar jam not linked to the Walled City rain |
| 10-second comprehension | ⚠️ | Designed for it (status word + icon + colour, one headline); not yet tested with real non-technical users |

## Innovation

| Item | Status | Evidence |
|---|---|---|
| AI/NLP explanation | ⚠️ | Template path verified; LLM path covered by mocked tests (valid, invalid, failing) — **not yet run against the real Claude API** (no key configured) |
| Monitoring / agentic layer | ✅ | `test_agent_*`; critical alert opened at 72 s in the scenario run |
| Creative pulse visualization | ✅ | Heartbeat strip (colour + bpm from data), heat-map timeline, live ticker |
| Geospatial / IoT sensor layer | ✅ | 25 simulated sensors on the map, feeding the same normalizers |
| Advanced analysis | ✅ | Robust median/MAD baselines, Poisson significance test, Pearson co-movement with lead/lag |
| Historical replay | ✅ | `test_replay.py`; browser check of play, scrub and key moments |
| Threshold alerting | ✅ | Agent alerts with hysteresis; data-quality alerts during the outage drill |
| Optional 3D view | ❌ | Not built (optional per brief) |

## Reliability

| Item | Status | Evidence |
|---|---|---|
| Weather API failure | ✅ | `test_weather_outage_keeps_everything_else_running`; real-time drill |
| Traffic API failure | ✅ | `test_traffic_outage_does_not_break_dashboard`; real-time drill |
| Incident feed failure | ✅ | `test_feed_recovers_after_fault_cleared`; real-time drill |
| AQI feed failure | ✅ | Real-time drill incl. its 160 s last-known-values window |
| AI API failure | ✅ | `test_ai_service_failure_returns_none`, `test_summarizer_keeps_template_when_ai_fails` |
| Malformed data | ✅ | `test_malformed_*`; real-time drill rejected bad records on all 5 feeds while staying healthy |
| Timeout | ✅ | `test_live_api_timeout_falls_back_to_labelled_synthetic` |
| Rate limit / bad JSON | ✅ | `test_live_api_rate_limit_and_malformed_json_fall_back` |
| Stale data | ✅ | `test_delayed_feed_becomes_delayed_then_stale`; real-time drill checked each status against the feed's age |
| Fallback mode | ✅ | Live→synthetic labelled FALLBACK ("not live data"); simulated → last known values with age |
| Database failure handled | ✅ | `test_database_outage_keeps_live_pulse_running` |
| Demo scenario deterministic | ✅ | `test_simulation_is_deterministic`; real-time run: amber 48 s, red 72 s, all stages reached |
| Fresh install works | ✅ | Clean clone → `pip install` on Python 3.12 → 102/102 tests at that point; `npm ci && npm run build` |

## Project cleanliness

| Item | Status | Evidence |
|---|---|---|
| No `CLAUDE.md` | ✅ | `git ls-files` |
| No `.claude/` directory | ✅ | `git ls-files`; ignored in `.gitignore` |
| No tool-specific configuration | ✅ | `git ls-files` shows only project source, docs and config |
| No unnecessary AI-tool files | ✅ | "Claude" appears only as the optional summary provider (config, `ai/llm.py`, docs) |
| No API keys / secrets | ✅ | secret scan clean; `test_env_example_contains_no_secret_values` |
| No unnecessary generated artifacts | ✅ | `dist/`, `node_modules/`, `.venv/`, `*.db`, caches all ignored |
| Clean `.gitignore` | ✅ | secrets, envs, builds, databases, OS/editor files |
| `.env.example` accurate | ✅ | `test_every_env_example_variable_is_a_real_setting` |

## Map-first UI (redesign acceptance)

| Item | Status | Evidence |
|---|---|---|
| Default screen far cleaner; map dominates | ✅ | `docs/screenshots/normal.jpg` — header, legend, alerts only |
| No permanent demo/control panel | ✅ | Demo and Insights are closed-by-default drawers |
| Important incidents visible immediately; hierarchy | ✅ | Red disruption area + label; icons only when a report type is unusual |
| Compact legend; ≤ 4 alerts | ✅ | `MapControls.tsx`, `AlertsCard.tsx` (2 on phones) |
| Zone details on interaction | ✅ | Zone story drawer; data behind it on demand |
| Demo button, drawer, multiple realistic scenarios | ✅ | 8 presets + custom sliders + feed failures |
| Scenarios change the real feeds and produce anomalies/links/impact | ✅ | `test_every_preset_propagates_through_the_pipeline` (8 presets) |
| Pause / speed / reset | ✅ | `test_pause_*`, `test_speed_*`; browser check |
| Correlation never presented as causation | ✅ | Tests scan statements; UI tags "Not a confirmed cause" |
| Replay and feed failures still work | ✅ | `test_replay.py`, `test_resilience.py`; browser check |
| No console errors; no TypeScript/build errors | ✅ | Fresh-tab console check across views; `tsc` + `vite build` clean |
| Responsive | ✅ | Checked at 375 × 812: compact header, capped alerts, drawers full-width |

## Before the judging slot

- [ ] Start both servers (or one-server mode) 5 minutes early; open `/api/health`
- [ ] Demo → **Normal city**
- [ ] Rehearse [DEMO.md](DEMO.md) once with a timer
- [ ] Fill in the team table in `README.md` and the team name in the pitch
- [ ] Optional: set `ANTHROPIC_API_KEY` and confirm the "AI-assisted" badge appears; if anything
      looks off, remove the key — the rule-based summary is complete on its own
