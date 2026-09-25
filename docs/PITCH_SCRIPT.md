# CityPulse — Pitch Script

What to say for each slide in [PRESENTATION.md](PRESENTATION.md), timed for the 7-minute slot in
[DEMO.md](DEMO.md): about 3 minutes of slides around a 3.5-minute live demo.

Tips: speak to the map, not the laptop. Pause when an area changes colour so judges can see it.
Say "possible link" and "may be related" every time; it's our strongest message.

---

## Brief introduction (0:00–0:30)

**Slide 1: Title · 10 s**
"Hi, we're [team name]. This is CityPulse, a live civic health dashboard for Jaipur, built for
Track B. It fuses five city data feeds into one map anyone can read in about ten seconds."

**Slide 2: Problem statement · 20 s**
"Cities already collect weather, traffic and bus data, citizen reports, air quality and water
levels. But every feed has its own format: Fahrenheit, rain per fifteen minutes, the bus
operator's own area codes, and complaints that even carry personal data. So the data is
scattered, related problems look unrelated, and people find out too late. The real challenge is
fusing messy feeds into one picture people can trust."

## Presentation (0:30–1:45)

**Slide 3: Proposed solution · 20 s**
"Five messy feeds go in. CityPulse fuses them, checks them against what's normal for each place
and time, links related signals, and explains them. Out comes one live map: 225 blocks, updated
every three seconds, readable in about ten seconds."

**Slide 4: System architecture · 30 s**
"Left to right: five feeds in five raw formats. The Python FastAPI backend runs one pipeline
every three seconds: the feed manager with fallbacks, normalization into one data model, the
store, and the analysis engine. The result is one pre-computed city state. The summary and the
monitoring agent work from that state, and demo and replay drive the very same engine. The API
only serves that snapshot, and the React app polls it every three seconds."

**Slide 5: Key features · 25 s**
"Six things it does. A live map where only unusual blocks light up. It spots what's unusual
against the normal for that time of day. It shows possible links, never causes. It shows what
may happen next nearby. It gives a plain-language summary. And it keeps working when feeds
fail. Let me show you."

## Live demo (1:45–5:15)

Switch to the browser and follow the [live demo timeline](DEMO.md#live-demo-timeline-about-35-minutes).
Use **slides 6 and 7** (real screenshots of the same journey) only if the live app can't run.

**Slide 6 (backup): The working product**
"The header shows the city's status. The problem is a local hotspot around the Walled City.
Dashed violet blocks show where flooding or power cuts may happen next. Alerts are few and
grouped. It runs live, as eight instant demo situations, and as a replay of a recorded storm."

**Slide 7 (backup): End-to-end journey**
"Pick Heavy rainfall; it appears in about 1.4 seconds. The map flies to the hotspot. Click the
block: possible disruption, what you'd notice, what to do. Insights gives the plain-language
summary, marked 'not a confirmed cause'."

## Technical walkthrough (5:15–6:30)

**Slide 8: Technical implementation · 60 s**
"Five engineering decisions. One: a pre-computed state every three seconds, so the API never
computes on request. Two: one validated data model with UTC time, standard units, our block IDs,
and no personal data. Three: robust statistics. Normal is the median and MAD for each block and
half-hour, and report spikes must pass a Poisson test. Four: correlation, never causation. Six
link rules, same block, same ten minutes, an evidence score, and tests check the wording. Five:
it fails gracefully, and AI text is rejected if it adds numbers or cause words.
What we measured: all 225 blocks analysed in under a tenth of a second, a situation on screen in
about 1.4 seconds, and in heavy rain, rain detected at 20 seconds and a possible disruption at 100.
No red blocks in two quiet rush hours, and 128 automated tests pass."

## Close (6:30–7:00)

**Slide 9: Future scope · 20 s**
"What's next is planned, not built: real city feeds through the same normalizers, alerts for
residents, relationships learned from history and reviewed by people, a city-scale cloud
deployment, deeper replay, and a 3D view."

**Slide 10: Thank you · 10 s**
"Everything is on GitHub: code, README and architecture docs. It runs locally today, with no
public deployment yet. Thank you, we're happy to take questions."

## Q&A (3 minutes)

Short answers to likely questions: [JUDGE_QA.md](JUDGE_QA.md).
