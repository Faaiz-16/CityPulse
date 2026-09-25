# CityPulse: Judge Q&A

36 likely questions. Each has a **short answer** (say this first), a **detailed answer** (if they
want more) and, where useful, the **technical** backing (file, algorithm, number).

---

## Problem and users

### 1. What problem are you solving?
**Short:** Civic information is scattered across disconnected feeds; nobody fuses it into one
view a resident can understand in seconds.
**Detailed:** Weather, traffic, transit, complaints and air quality each live in their own app,
format and timing. People discover problems after they're affected, and staff notice patterns
late. CityPulse fuses the feeds, detects what's unusual, surfaces *possible* relationships and
explains them in plain language on a map.

### 2. Who is it for?
**Short:** Residents first; city staff, journalists, responders and small businesses second.
**Detailed:** The default view is designed for a non-technical resident (10-second read). The
zone panel gives staff and journalists the evidence behind every flag.

### 3. How do you meet the "understandable in 10 seconds" requirement?
**Short:** A map-first screen: normal blocks draw nothing at all, only unusual blocks get
colour + icon + one word, and at most 4 grouped alerts; details are one click away.
**Detailed:** Status is always colour + icon + word (never colour alone). Of Jaipur's 225 blocks
(5 × 5 districts of 3 × 3 blocks), only unusual ones are tinted amber or red, with one short label
per hotspot, and alerts are grouped per hotspot. Clicking a block opens the area panel: status,
what you'd notice and what to do; raw numbers and evidence sit behind *Explain in detail*.

### 4. How is this different from existing city dashboards?
**Short:** They show data; we show *fused meaning* (what's unusual, what may be related, and
what we can't tell) for the public.
**Detailed:** Typical dashboards put every feed on a chart for analysts. CityPulse normalizes
feeds into one model, compares against time-of-day baselines, links signals only under strict
rules, labels uncertainty explicitly, keeps working when feeds fail, and explains in plain
language.

## Data

### 5. Which data sources do you use?
**Short:** Five: weather, traffic and buses, 311-style reports, air quality, and IoT water-level
sensors.
**Detailed:** By default they come from a deterministic synthetic city, each in a different
realistic vendor format. Weather and air quality can also come live from Open-Meteo (free, no
key) by setting `CITYPULSE_LIVE_APIS=true`.

### 6. Why synthetic data?
**Short:** The brief allows it, it makes the demo reliable and repeatable, and it lets us show
events on demand.
**Detailed:** Real city feeds need access agreements and rarely contain a storm during a
24-hour hackathon. The synthetic city reproduces real messiness (formats, units, timestamps,
noise, personal fields) and is clearly labelled SIMULATED, never presented as live or official.
**Technical:** `data_sources/city_model.py`: daily patterns × zone character + event effects +
seeded noise, so the same inputs always give the same outputs.

### 7. Is the synthetic data realistic?
**Short:** Realistic in shape (rush hours, evening air-quality peaks, random reports) but not
calibrated on a real city, and we say so.
**Detailed:** Rain uses meteorological thresholds (7.6 mm/h = heavy), AQI uses the US EPA
breakpoints, reports arrive as a Poisson process. Events ripple into related signals with lags.

### 8. How would you get real data for a real city?
**Short:** Plug real feeds into the same normalizers: 311/Open311 portals, GTFS-Realtime transit,
traffic APIs, weather and air-quality APIs, municipal sensors.
**Detailed:** Our raw formats deliberately mirror common standards (Open311, OpenAQ-style,
MQTT-style sensors). A new source needs one normalizer function; the engine, agent, API and UI
don't change.

## Normalization and time

### 9. What does "normalization" mean here?
**Short:** Converting every feed into one common record: same field names, UTC time, standard
units, zone ID, validated values.
**Detailed:** Each normalizer maps fields, parses the timestamp, converts units (°F→°C, mm per
15 min→mm/h, speed→congestion, PM2.5→AQI, mm→cm), maps IDs or coordinates to a zone, validates
ranges and rejects bad records individually.
**Technical:** `normalization/normalizers.py` (8 normalizers) → `CivicReading` / `CivicIncident`
in `schemas.py`.

### 10. How do you handle different timestamps and update rates?
**Short:** Everything is converted to UTC, and analysis uses time windows instead of "latest
value", so fast and slow feeds line up.
**Detailed:** We parse ISO with offsets, UTC "Z", local times without zones, epoch seconds and
milliseconds, and day-first local text. Current values are averaged over a window sized to each
feed's update rate; relationships are evaluated over a shared 10-minute rolling window.
**Technical:** `normalization/timestamps.py`; window = max(60 s, 2.5 × feed interval).

### 11. What happens to malformed data?
**Short:** Bad records are rejected one by one with a reason; the good records in the same batch
still flow.
**Detailed:** Missing values, impossible values (negative speed), bad timestamps, unknown
categories, locations outside the city, all rejected and counted. The feed chip shows the
rejected count. You can inject malformed data live from the demo panel.

## Analysis

### 12. How do you calculate the baseline?
**Short:** For each zone, metric and half-hour of the day, the median of three days of history.
**Detailed:** Traffic at 9 a.m. isn't comparable with 3 a.m., so baselines are time-of-day
specific. We use the median and the median absolute deviation because a past storm barely moves
them. For report counts we take the median rate across days, so one bad evening doesn't redefine
normal.
**Technical:** `analysis/baseline.py`, 48 half-hour slots, pooled ±30 min.

### 13. How do you detect anomalies?
**Short:** Current value vs baseline vs a documented threshold: for example traffic ≥ 30 % above
normal.
**Detailed:** Relative rules for traffic (+30 %) and bus delays (+50 %); absolute rules where
"normal" is ~0: rain ≥ 7.6 mm/h, street water ≥ 15 cm; AQI ≥ 150 or +25 %. Severity scales with
how far past the threshold it is. Example: 147 vs 100 → +47 % → anomaly, moderate.
**Technical:** `analysis/anomaly.py`; thresholds in `config.py`.

### 14. Why a statistical test for report counts?
**Short:** Reports arrive randomly; a few extra is normal. We only flag a spike if it's very
unlikely by chance.
**Detailed:** We compute the Poisson probability of seeing that many reports given the normal
rate. Because we check 225 blocks × 4 report types every 3 seconds, we use a strict 0.1 % level to
avoid false alarms from multiple comparisons. We tuned this after seeing false alarms in testing.

### 15. What is the rolling window?
**Short:** The last 10 minutes: signals must overlap inside it to be considered related.
**Detailed:** Instead of treating all data as one snapshot, we continuously look at recent
observations. The window is configurable (`CITYPULSE_ROLLING_WINDOW_MINUTES`); 10 minutes suits
our feed rates.

### 16. How do you avoid fake correlations?
**Short:** A relationship needs a logical rule, both signals anomalous, the same zone, the same
window and timing that fits; co-occurrence alone is never enough.
**Detailed:** Only six plausible rules exist (rain→traffic, rain→flooding, outages→traffic,
accident→traffic, traffic→bus delays, traffic→air quality). Evidence is scored for severity, timing, co-movement and supporting
signals; weak evidence is labelled "insufficient". In the demo, an unrelated traffic jam in
Vaishali Nagar (B3-1) is *not* linked to the rain over the Walled City (C2-9).
**Technical:** `analysis/correlation.py`; score ≥ 0.8 strong, ≥ 0.6 moderate.

### 17. How do you distinguish correlation from causation?
**Short:** We never claim causation. The system can only say signals "may be related", and
every link carries "not a confirmed cause".
**Detailed:** The wording is fixed in code; alerts store observed facts, possible relationship
and a causation note in separate fields; the AI validator rejects causal phrases ("caused",
"due to", "led to"…). Missing data produces "cannot check", not a guess.

### 18. What's the "co-movement r"?
**Short:** A Pearson correlation of the two signals over the window: did they rise and fall
together?
**Detailed:** It adds up to 0.1 to the evidence score. When both signals plateau at unusual
levels, r is near zero and we say it adds no extra evidence rather than pretending.

### 19. How does the prediction / early-warning work?
**Short:** If rain is heavy and traffic is rising but hasn't crossed its threshold yet, we warn
"traffic may slow" before it happens.
**Detailed:** Early warnings use the trend (rising over recent minutes) and a partial deviation
(≥ +10 %). A "potential disruption" needs a moderate/strong relationship and at least two
serious anomalies. Both are grounded in observed data, and labelled as risk, not certainty.
**Technical:** `analysis/risk.py`.

### 20. Why not use machine learning everywhere?
**Short:** Transparent statistics are more trustworthy and explainable for a public tool, and
work without training data.
**Detailed:** We use robust statistics (median/MAD, z-scores), a Poisson significance test and
correlation: every flag can be explained with numbers and a rule. ML would need labelled
history we don't have and would be harder to audit. The engine is modular, so an ML detector
could be added alongside, not instead.

## AI, NLP and the agent

### 21. What does the AI do?
**Short:** It only rewrites structured findings into friendlier language: it never decides
what's happening.
**Detailed:** The analysis engine produces the facts. A rule-based template always writes the
summary first. If an API key is configured, an LLM rewrites the facts in plain language; the
text is shown only if it passes checks.

### 22. How do you prevent AI hallucinations?
**Short:** The model only sees a structured fact sheet, must return a fixed JSON shape, and its
text is rejected if any number isn't in the facts or it uses causal language.
**Detailed:** Also rejected if it describes a zone that isn't flagged. Rejection → the template
stays; the UI labels which one is shown (Rule-based / AI-assisted).
**Technical:** `ai/llm.py` (structured output via `messages.parse`), `ai/validator.py`.

### 23. What if the AI service is down?
**Short:** Nothing visible breaks: the rule-based summary is always generated first.
**Detailed:** Calls run in a background thread with a timeout, at most one per 20 s, only when
the situation changes. Tested with a mocked failing client.

### 24. Why call it an agent?
**Short:** It continuously monitors the civic state, decides whether something deserves an
alert, and opens, escalates or resolves alerts on its own.
**Detailed:** Every tick it checks feeds, data quality, anomalies, related signals and the window,
then decides. It uses hysteresis (3 clean checks before resolving) so alerts don't flicker, and
shows its reasoning trace in the zone panel. It's rule-driven, so it can't invent events.
**Technical:** `agent/monitor.py`.

## Reliability and privacy

### 25. What happens when a feed fails?
**Short:** Everything else keeps running; the feed shows FALLBACK, then UNAVAILABLE, and
analysis says what it can't check.
**Detailed:** Live APIs fall back to a clearly labelled estimate; simulated feeds show last-known
values with their age. Silent feeds become DELAYED then STALE. Missing values are "not assessed",
never zero. Demonstrable live from the demo panel.
**Technical:** `services/feed_manager.py`; tests in `test_resilience.py`.

### 26. Do you ever show old data as live?
**Short:** No. Only real API data is ever labelled LIVE, and stale data is shown with its age
and excluded from current analysis.

### 27. What if the database fails?
**Short:** The live pulse keeps running from memory; health reports storage as degraded.
**Detailed:** Analysis reads an in-memory rolling store; every database call is best-effort.
Tested by simulating a database that fails on every call.

### 28. How do you protect privacy?
**Short:** Reports are anonymous; personal fields are dropped at ingestion and never stored.
**Detailed:** Only whitelisted fields survive (category, time, location rounded to ~10 m). The
data model has no field that could hold a name or phone number. No person identification, no
facial recognition, no tracking of complainants.

## Architecture and tech

### 29. Why this tech stack?
**Short:** Fast to build, easy to run on a laptop, free: Python/FastAPI for data work,
React/Leaflet for the map.
**Detailed:** FastAPI + Pydantic give validated, typed APIs; SQLAlchemy keeps the database
swappable; Leaflet + OpenStreetMap need no API key; Tailwind for consistent UI; no paid
services, no microservices.

### 30. Why SQLite and not PostgreSQL?
**Short:** Zero setup for a hackathon; switching is one environment variable because we use
SQLAlchemy.

### 31. Why polling instead of WebSockets?
**Short:** Simpler and more robust; a 3-second refresh is plenty for civic data, and it survives
network blips automatically.

### 32. How would it scale to a real city?
**Short:** Run the same pipeline per district, move to PostgreSQL, and put real feeds behind the
same normalizers.
**Detailed:** Each 3-second tick already analyses all 225 Jaipur blocks (~1,125 sensors) in about
80 ms; the design is per-area, so larger grids parallelize naturally. For a large city: a message queue for ingestion, a time-series database
(e.g. TimescaleDB), a cache in front of the read API.

## Scope and honesty about the project

### 33. What did you build during the hackathon?
**Short:** Everything in the repo: feeds, normalizers, analysis engine, agent, AI layer,
replay, the React map UI, 121 tests and the documentation.

### 34. What's the historical replay?
**Short:** Yesterday's recorded storm replayed minute by minute through the exact same engine
and agent: proof the detection works on past data, not just a scripted demo.
**Detailed:** The replay finds the event in the stored history itself and is clearly labelled
ARCHIVE / not live. Detection unfolds: rain 18:18 → traffic 18:23 → possible link 18:25 →
disruption 18:26.
**Technical:** `simulation/replay.py`.

### 34b. Aren't the demo scenarios just scripted results?
**Short:** No: a scenario only changes the simulated *city*; everything you see is detected by the
normal pipeline, and the storyline ticks a beat only when the analysis output shows it.
**Detailed:** "Heavy rainfall" raises rainfall around the Walled City; the feeds report it in their own
formats, normalization, baselines, anomaly rules, correlation, risk and the agent do the rest.
There is no hard-coded text for the result. A test runs every preset through the pipeline and
checks it reaches its outcome; the poor-air preset deliberately ends with *no cause claimed*.
**Technical:** `simulation/scenarios.py`, `tests/test_scenarios.py`; scenario time can pause or
run at 2×/4× (`SimClock`) while analysis windows stay on the real clock.

### 35. What are the limitations?
**Short:** Synthetic data and a demonstration grid of districts and blocks, not official wards;
hand-written relationship rules; we can show
overlap, never cause.
**Detailed:** Thresholds aren't calibrated on real data; the AI path depends on an API key;
replay covers one recorded event; no 3D view yet.

### 36. What would you build with more time?
**Short:** Real city feeds, alerts residents can subscribe to per area, and learned relationship
discovery reviewed by humans before it's shown.
**Detailed:** Also: calibrating thresholds on real history, replay of any time range, a
multilingual summary, and an optional 3D view of buildings and sensor density.
