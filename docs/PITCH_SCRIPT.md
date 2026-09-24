# CityPulse — Pitch Script

Natural, speakable text for each slide in [PRESENTATION.md](PRESENTATION.md).
**Total ≈ 8 minutes** (≈ 4.5 min talking + ≈ 3.5 min demo). For a 5-minute slot, skip the ✂
slides and use the 2-minute demo.

Tips: speak to the map, not the laptop. Pause when a zone changes colour — let judges see it.
Say "possible link" and "may be related" every time; it's our strongest message.

---

## Slide 1 — Title · 15 s
**Show:** the map with Zone 3 red.
**Say:** "Hi, we're [team]. This is CityPulse. The idea is simple: one glance should tell you
what's really happening in your city — and why it might matter."
**Key point:** memorable one-line promise.

## Slide 2 — The problem · 30 s
**Show:** the five disconnected apps.
**Say:** "Today the information exists, but it's scattered. Rain is in a weather app, bus delays
in a transit app, flooding complaints in a 311 portal. So you find out about the flooded
underpass after you're stuck in it. And the dashboards that do exist are built for analysts, not
for the people who live there."
**Key point:** the data exists; the *fusion* and the *public view* don't.

## Slide 3 — Why it's hard ✂ · 30 s
**Show:** the formats table.
**Say:** "Fusing it is genuinely hard. Every feed disagrees — time zones, epoch milliseconds,
day-first dates, Fahrenheit, speed instead of congestion, area codes instead of locations,
even personal data that shouldn't be there. And the hardest part: telling a real link from a
coincidence, and saying so honestly."
**Key point:** we solved real messiness, not a clean toy.

## Slide 4 — Our solution · 30 s
**Show:** annotated screenshot.
**Say:** "CityPulse normalizes five feeds into one model, detects what's unusual, finds possible
relationships, and explains them in plain language — on a map first. The map answers where,
what and how serious in ten seconds. Click a zone and you get the why. Let me show you."
**Key point:** map for the 10-second read; panel for the investigation.

## Slide 5 — Live demo · 3 min 30 s
**Show:** the browser. Follow [DEMO.md](DEMO.md) steps 1–7.
**Must-say lines:**
- "Status is colour plus an icon plus a word — never colour alone."
- "We change the simulated city, not the analysis. CityPulse has to detect it."
- "The storyline only ticks when the analysis actually detects each beat."
- "Same zone, same ten-minute window, rain came first — so *these signals may be related*.
  Not a confirmed cause."
- "Weather API down: everything else keeps running, and we say what we can't check."
- "Replay: yesterday's storm through the exact same engine."
**Key point:** it works end to end, honestly, even when things fail.

## Slide 6 — Architecture · 30 s
**Show:** the pipeline diagram.
**Say:** "Under the hood it's one pipeline that runs every three seconds: feeds with fallbacks,
normalization, one common data model, then the analysis engine. Its output is a single
structured state that feeds the map, the plain-language summary and the monitoring agent. It
runs on a laptop with free, open tools."
**Key point:** one source of truth; AI is downstream, not in charge.

## Slide 7 — Normalization ✂ · 20 s
**Show:** raw record → clean record.
**Say:** "Every record becomes a reading or a report with UTC time, standard units and a zone.
Broken records are rejected one at a time so good data keeps flowing, and personal fields are
dropped before anything is stored."
**Key point:** privacy and robustness start at ingestion.

## Slide 8 — Detection · 40 s
**Show:** the five-step list.
**Say:** "First, what's normal — for this zone, at this time of day, using the median so an old
storm doesn't redefine normal. Then anomalies: traffic 147 against a normal 100 is plus 47
percent, over our 30 percent threshold, so it's flagged. Report spikes must also be
statistically unlikely by chance. A relationship needs a logical rule, the same zone, the same
ten-minute window and timing that fits. That's how we get early warnings and disruption flags."
**Key point:** explainable, conservative, every number traceable.

## Slide 9 — Honest by design · 30 s
**Show:** Observed / Possible / Not claimed table.
**Say:** "We keep three things apart: what we observed, what may be related, and what we never
claim — causation. If evidence is weak we say so. If a feed is missing we say we can't check.
And if our optional AI writer ever invents a number or says 'caused', its text is thrown away
and the rule-based summary stays."
**Key point:** epistemic honesty is enforced in code, not just in wording.

## Slide 10 — Resilience ✂ · 20 s
**Show:** the status list.
**Say:** "Every feed shows its health. A failed API gets a labelled fallback, never fake live
data. Missing data is 'not assessed', never zero. Even the database and the AI can fail and the
pulse keeps going."
**Key point:** degrade gracefully and visibly.

## Slide 11 — Innovation · 30 s
**Show:** the innovation table.
**Say:** "We covered every innovation path in the brief as one system: statistical anomaly and
correlation analysis, grounded language generation, a monitoring agent that opens and resolves
alerts, a literal city heartbeat and heat-map timeline, an IoT sensor layer, and historical
replay."
**Key point:** innovations are integrated, not bolted on.

## Slide 12 — Impact and scale · 30 s
**Show:** audiences + path to a real city.
**Say:** "Residents know before they go. City staff see patterns before complaints escalate.
Journalists get evidence instead of rumours. And to deploy in a real city, you swap our
synthetic feeds for real ones — the normalizers, engine, agent and map stay exactly the same."
**Key point:** realistic path from hackathon to city.

## Slide 13 — What we built ✂ · 20 s
**Show:** the list.
**Say:** "In 24 hours: five feeds, eight normalizers, the analysis engine, the agent, replay, the
map-first interface, 119 automated tests and full documentation."
**Key point:** substance and reliability.

## Slide 14 — Close · 15 s
**Show:** closing slide.
**Say:** "CityPulse turns disconnected signals into one honest pulse: where, what, how serious —
and only *possibly* why. Thank you — we'd love your questions."
**Key point:** end on the honesty message.
