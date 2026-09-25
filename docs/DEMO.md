# CityPulse: Demo Guide (7-minute judging slot)

A reliable, rehearsable walkthrough for judges. Everything runs locally; the only internet
dependency is the map background (the demo still works without it).

The interface is **map-first**: Jaipur fills the screen in **5 × 5 districts** (columns A-E, rows
1-5; the Walled City is **C2**), each split into **3 × 3 blocks** of ~1.5 km (block `C2-9`). Around it: a slim header, a compact legend and
at most four alerts. Everything else opens on demand, **Demo** and **Insights** drawers on the
left, the **area panel** on the right, **Replay** at the bottom.

Situations appear **instantly**: when you pick one, the backend starts it a couple of minutes in
the past and fast-forwards the real pipeline through that time (~2 seconds). No waiting, no
refreshing between situations.

---

## The 7-minute slot

Each team gets **7 minutes for the presentation and live demo, then 3 minutes of Q&A**. Spend most
of the time on the working product. The slides only support it.

| Time | Part | What to do | Slides |
|---|---|---|---|
| 0:00-0:30 | Brief introduction | Who we are, and the problem in one breath | 1-2 |
| 0:30-1:45 | Presentation | Proposed solution, system architecture, key features. Point, don't read | 3-5 |
| 1:45-5:15 | **Live demo** | Switch to the browser and run the [live demo timeline](#live-demo-timeline-about-35-minutes) below: the end-to-end user journey and key features | 6-7 only as a backup |
| 5:15-6:30 | Technical walkthrough | Engineering decisions and measured numbers. Optionally open `http://localhost:8000/api/readings?zone_id=C2-9&metric=rain_mm_h` to show normalized records, or `http://localhost:8000/docs` for the API | 8 |
| 6:30-7:00 | Future scope and close | Planned next steps, thank you, GitHub QR code | 9-10 |
| 7:00-10:00 | Q&A | Likely questions and answers: [JUDGE_QA.md](JUDGE_QA.md) | - |

Have the deck open in presenter view on one screen and the app full-screen in a browser tab, so
switching takes one keystroke. If the live demo fails, slides 6 and 7 are real screenshots of the
same journey.

## Before you present (5 minutes earlier)

1. Start the backend and frontend (see [SETUP.md](SETUP.md)), or one-server mode. The very first
   start builds history for the 225 blocks (~25 s); later starts are quick.
2. Open <http://localhost:5173> full-screen (1440 × 900 or larger looks best on a projector).
3. Header → **Demo** → **Normal city**.
4. Check: header says **City normal · All 25 districts normal**, mode **LIVE**, alerts say **All clear**.

Pre-flight checklist:

- [ ] Just the map of Jaipur; no blocks tinted or glowing
- [ ] Active alerts: *All clear, nothing unusual right now.*
- [ ] Laptop won't sleep; notifications off

## Live demo timeline (about 3.5 minutes)

Times are from the start of the demo. If you are running long, skip step 5 (multi-event).

| Time | What you do | What judges see |
|---|---|---|
| 0:00 | Open on the map | A clean map of Jaipur, green heart, "All clear" |
| 0:20 | **Demo → Heavy rainfall** | ~2 s later: the map flies to the Walled City; a red hotspot of 9 blocks, rain cells, congestion on real roads, waterlogging icons; the simple area panel opens |
| 0:40 | Read the panel aloud | "Possible disruption · Heavy rain · Traffic much heavier than usual · Buses running late · Allow extra travel time" |
| 1:10 | **Explain in detail** | What's happening, measured evidence, possible relationship (*not a confirmed cause*) |
| 1:50 | **Demo → Multi-event evening** | Rain over the Walled City **and** a separate amber jam in Vaishali Nagar that is not blamed on the rain |
| 2:30 | **Demo → Feed failures → Weather: Outage** | Data chip turns amber; an info alert; "cannot check" wording |
| 3:10 | **Replay** (header) → key moments | Yesterday's recorded storm through the same engine |
| 3:50 | **Back to live**, close | One sentence on scale |

## Step by step

### 1. The 10-second read (0:00-0:20)
**Show:** the opening screen.
**Say:** "This is CityPulse for Jaipur. The city is 25 districts, each split into 9 blocks: 225 small areas, each watched on its own. A
resident opens it and in ten seconds knows: is the city OK, where is the problem, what kind, how
serious. Right now the heart is green and every area is normal, so the map stays clear."

### 2. Create an incident (0:20-0:40)
**Click:** header **Demo** → **Heavy rainfall** (Walled City).
**Say while it loads:** "We're not faking the result. The scenario changes the simulated *city*:
rain gauges, road sensors, bus feeds, 311 reports and water sensors, each in its own messy format.
CityPulse normalizes, detects and connects it on its own. We fast-forward the last two minutes so
you don't have to wait."
**Show:** the red hotspot over the Walled City and its neighbours, blue rain cells, orange/red
congestion along Jaipur's real main roads, waterlogging icons.

### 3. The simple answer (0:40-1:10)
**Show:** the area panel: **Possible disruption**, three plain things you'd notice, one thing to do.
**Say:** "This is all a resident needs: what's happening and what to do. No jargon, no numbers."

### 4. Ask why (1:10-1:50)
**Click:** **Explain in detail**.
**Say:** "Now the evidence: rain 26 mm/h, traffic 80 % above normal for this time of day, bus
delays, water on the streets, same area, same ten minutes. Look at the wording: these signals
*may be related*: a possible link, not a confirmed cause."
**Optional:** *Show the data behind this* → a metric card and *Why these flags?*

### 5. Not everything is connected (1:50-2:30)
**Click:** Demo → **Multi-event evening**.
**Say:** "Two things at once: rain over the Walled City, and a traffic jam in Vaishali Nagar. CityPulse
flags the jam but does not blame it on the rain; they're in different areas with nothing linking them."
Open the Demo drawer → **How CityPulse detected it** to show each step with its detection time.

### 6. Break something (2:30-3:10)
**Click:** Demo → **Feed failures** → Weather → **Outage**. Close the drawer.
**Show:** the header data chip turns amber; an info alert appears; the area detail later says
CityPulse *cannot check* whether rain is involved.
**Say:** "One feed fails: everything else keeps running, and we say exactly what we can no
longer check instead of guessing." Set Weather back to **Healthy**.

### 7. Past data (3:10-3:50)
**Click:** header **Replay**. Click the key-moment chips: *Rain begins → Traffic increases →
Possible relationship found → Potential disruption flagged*.
**Say:** "Yesterday's recorded storm over Tonk Phatak and Durgapura, replayed minute by minute
through the exact same engine and agent, clearly labelled, not live."
**Click:** **Back to live**.

### 8. Close (3:50)
**Say:** "Disconnected signals, one honest pulse: where, what, how serious, and only possibly
why. For a real city you swap the simulated feeds for real ones; everything else stays."

## Other situations worth showing

| Situation | Where | What it demonstrates |
|---|---|---|
| Flash flood | Mansarovar (B4-5) | Rain + street flooding + waterlogging surge |
| Major congestion | C-Scheme (C3-2) | Traffic → bus delays → air quality, **no weather link claimed** |
| Road accident | Ajmer Road, Heerapura (A3-9) | A single red block: accident reports → queue → possible disruption |
| Power outage | Malviya Nagar (C4-6) | Outage + signal reports → traffic at dark junctions |
| Poor air quality | VKI Industrial Area (B1-3) | Flagged, but *"no related signal, no cause claimed"* |
| Severe storm | Jagatpura (D5-3) | Rain + flooding + power cuts, several linked signals |

Tick **Play step by step** in the Demo drawer to watch a situation build up live instead (~2 minutes,
with pause and 2×/4×). The **Custom** tab sets rain, flooding, traffic, accident, outage and air
pollution with sliders around any area.

## If something goes wrong

| Problem | Recovery |
|---|---|
| A situation takes a few seconds | Normal: it is fast-forwarding two minutes of the real pipeline. |
| Map background doesn't load (no internet) | Say "map tiles need internet; the data doesn't". The labels and panels still work. |
| Screen shows "Connecting…" | Backend stopped: restart it; the page reconnects by itself. |
| Something looks stuck after the demo | Demo → **Normal city**. |
| A judge asks to break something | Demo → Feed failures: let them pick any feed and mode. |

## Shorter version (2 minutes)

1. Opening screen (10-second read): 15 s
2. Demo → **Heavy rainfall** → read the simple panel → **Explain in detail**: 60 s
3. Demo → Feed failures → Weather **Outage** → point at the data chip: 30 s
4. Close: 15 s
