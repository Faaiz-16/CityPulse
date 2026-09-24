# CityPulse — Demo Guide (3–5 minutes)

A reliable, rehearsable walkthrough for judges. Everything runs locally; the only internet
dependency is the map background (the demo still works without it).

---

## Before you present (5 minutes earlier)

1. Start the backend and frontend (see [SETUP.md](SETUP.md)).
2. Open <http://localhost:5173> in a full-screen browser window (1440 × 900 or larger looks best
   on a projector). Zoom the browser to 100 %.
3. Click **Demo controls → Normal state**. All five zones should be green; the pulse strip says
   *City normal*.
4. Check <http://127.0.0.1:8000/api/health> shows `"status": "ok"`.
5. Close the demo panel. Leave the map at its default view.

Pre-flight checklist:

- [ ] All five feed chips say **SIMULATED** (or LIVE if live APIs are on)
- [ ] "Right now" says *All zones look normal right now.*
- [ ] Monitoring agent says *Watching all feeds — nothing needs attention.*
- [ ] Laptop won't sleep; notifications off

## Timeline at a glance

| Time | What you do | What judges see |
|---|---|---|
| 0:00 | Open on the map | Five green zones, pulse strip, feed chips |
| 0:20 | Click **Zone 3** | Investigation panel: current vs normal, rules |
| 0:40 | **Demo controls → Run full scenario** | Rain begins over Zone 3 |
| 1:10 | Point at Zone 3 turning **amber** | Early warning: "Traffic may slow in Zone 3" |
| 1:40 | Zone 3 turns **red** | "Possible disruption", critical agent alert |
| 1:50 | Open **Why this flag?** | Evidence: same zone, same window, timing, co-movement, caveat |
| 2:30 | Point at Zone 1 turning amber | Traffic unusual — *insufficient evidence*, not blamed on rain |
| 2:50 | **Weather → Outage** | Weather chip → FALLBACK; summary says what can't be checked |
| 3:20 | **Replay storm** → click key moments | Same engine detects yesterday's recorded storm |
| 4:00 | **Back to live**, wrap up | Architecture and scale in one sentence |

## Step by step

### 1. The 10-second read (0:00–0:20)
**Show:** the opening screen.
**Say:** "This is CityPulse. A resident opens it and in ten seconds knows where something is
happening, how serious it is, and what kind of issue it is. Right now: five zones, all normal —
green, a tick, and the word *Normal*, never colour alone."
Point at the pulse strip: "That heartbeat is the city's pulse. Its colour is the worst zone and
it beats faster when more is unusual."
Point at the feed chips: "Five feeds, and we always show their health."

### 2. The investigation layer (0:20–0:40)
**Click:** Zone 3 on the map.
**Say:** "Click any zone and you get the *why*: every signal against what's normal for this zone at
this time of day, the percentage difference, and the exact rule we use — for example traffic is
flagged at 30 % above normal."
**Close** the panel (✕ or Esc).

### 3. Trigger the scenario (0:40–1:10)
**Click:** Demo controls → **Run full scenario**. (The demo panel appears in the left column and
shows a stage checklist.)
**Say while waiting:** "We're now simulating heavy rain over Zone 3. Important: we're not faking
the analysis — we change the simulated *city*, and the feeds report it in five different
formats: Fahrenheit, epoch milliseconds, CSV with day-first dates, Open311 reports with personal
fields we strip out. CityPulse has to normalize and detect it on its own. The checklist only
ticks when the analysis actually detects each stage."

### 4. Early warning (≈ 1:10)
**Show:** Zone 3 turns **amber**; the agent posts *Early warning: Traffic may slow in Zone 3*.
**Say:** "Rain is heavy and traffic is climbing but hasn't crossed its threshold yet — so we warn
*before* it becomes a disruption. That's the brief's 'alerts are reactive, not predictive'
problem."

### 5. Possible disruption (≈ 1:40)
**Show:** Zone 3 turns **red**, the ring pulses, the pulse strip turns red and speeds up, the
agent raises a **critical** alert.
**Click:** Zone 3 → the **Possible impact** card and the first relationship's **Why this flag?**
**Say:** "Now we have heavy rain, traffic about 80 % above normal, bus delays, water on the street
sensors and waterlogging reports — same zone, same 10-minute window, and the rain started first.
So we say *these signals may be related*. Look at the wording: 'a possible link, not a confirmed
cause'. The agent's alert keeps what we observed, the possible link and the causation note
separate."

### 6. Correlation is not causation (≈ 2:30)
**Show:** at about 70 s into the scenario Zone 1 turns **amber** (an unrelated traffic build-up).
Click Zone 1.
**Say:** "Here traffic is unusual in Zone 1, but nothing related is — no rain, no outages. So
CityPulse says *insufficient evidence to suggest any explanation*. It doesn't invent a reason."

### 7. Feed failure (≈ 2:50)
**Click:** Demo controls → Weather → **Outage**.
**Show:** the Weather chip turns **FALLBACK** within ~10 s ("showing last known values"), then
**UNAVAILABLE** after ~90 s. The agent adds a data-quality alert. The summary adds a note.
**Say:** "One API fails — everything else keeps running. We say exactly what's missing, we never
present old data as live, and once rain data ages out, CityPulse says *it cannot check* whether
rain is involved, instead of guessing."
Set Weather back to **Healthy**.

### 8. Historical replay (≈ 3:20)
**Click:** **Normal state**, then **Replay storm** (top-right of the map).
**Show:** the top bar says *Replay · Recorded … — not live*; feed chips say **ARCHIVE**. Click the
key-moment chips: *Rain begins → Traffic increases → Possible relationship found → Potential
disruption flagged*.
**Say:** "This is yesterday evening's recorded storm, replayed minute by minute through the exact
same engine and agent. It proves the detection works on past data, not just a scripted demo."
**Click:** **Back to live**.

### 9. Close (≈ 4:00)
**Say:** "Five mismatched feeds, one common model, honest analysis, a map anyone can read — and it
survives failures. To go live in a real city you swap the synthetic feeds for real ones; the
normalizers, engine, agent and map stay the same."

## If something goes wrong

| Problem | Recovery |
|---|---|
| Scenario feels slow | Keep talking through step 3; the red state reliably arrives within ~90–100 s. Or jump to **Replay storm** — it shows the same story instantly. |
| Map background doesn't load (no internet) | Say "map tiles need internet; the data doesn't" — zones, labels and panels still work. |
| Browser shows "Connecting…" | Backend stopped — restart it; the page reconnects by itself. |
| Something looks stuck in red after the demo | **Demo controls → Normal state**. |
| A judge asks to break something | Let them pick any feed and fault mode — that's the point. |

## Shorter version (2 minutes)

1. Opening screen (10-second read) — 20 s
2. **Replay storm** → click through the key moments — 60 s
3. **Weather → Outage** → point at the chip and the "cannot check" wording — 30 s
4. Close — 10 s
