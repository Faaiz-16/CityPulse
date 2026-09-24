# CityPulse — Demo Guide (3–5 minutes)

A reliable, rehearsable walkthrough for judges. Everything runs locally; the only internet
dependency is the map background (the demo still works without it).

The interface is **map-first**: the default screen is the map, a slim header, a compact legend and
at most four active alerts. Everything else opens on demand — **Demo** and **Insights** drawers on
the left, the **zone story** on the right, **Replay** at the bottom.

---

## Before you present (5 minutes earlier)

1. Start the backend and frontend (see [SETUP.md](SETUP.md)), or one-server mode.
2. Open <http://localhost:5173> full-screen (1440 × 900 or larger looks best on a projector).
3. Header → **Demo** → **Normal city**. Close the drawer (✕ or Esc).
4. Check: header says **City normal**, mode **LIVE**, data chip **Data OK · demo city**,
   alerts say **All clear**.

Pre-flight checklist:

- [ ] Five zone labels are small and green; nothing glowing on the map
- [ ] Active alerts: *All clear — nothing unusual right now.*
- [ ] Laptop won't sleep; notifications off

## Timeline at a glance (Heavy rainfall at 2×)

| Time | What you do | What judges see |
|---|---|---|
| 0:00 | Open on the map | Calm city: faint zones, green heart, "All clear" |
| 0:20 | **Demo → Heavy rainfall → Run scenario**, set **2×**, close the drawer | Demo pill: *Heavy rainfall · T+… · 0/8 detected* |
| 0:45 | (≈ 24 s after start) | Rain cells appear; Zone 3 turns **amber** |
| 1:20 | (≈ 60 s after start) | Zone 3 **Possible disruption**: red area, traffic corridors, waterlogging cluster; heart turns red and speeds up; alerts update |
| 1:30 | Click the top alert | Map flies to Zone 3; zone story opens |
| 2:20 | **Show the data behind this** | Metrics vs normal, "Why these flags?", 15-minute chart |
| 2:50 | **Demo → Feed failures → Weather: Outage** | Data chip turns amber; alert "Weather using fallback data"; later "cannot check" wording |
| 3:30 | **Replay** (header) → click key moments | Yesterday's recorded storm through the same engine |
| 4:10 | **Back to live**, close | One sentence on scale |

## Step by step

### 1. The 10-second read (0:00–0:20)
**Show:** the opening screen.
**Say:** "This is CityPulse. A resident opens it and in ten seconds knows: is the city OK, where is
the problem, what kind, how serious. Right now the heart is green and calm, the zones are quiet,
and there are no alerts. We only draw what matters."

### 2. Create an incident (0:20–0:45)
**Click:** header **Demo** → **Heavy rainfall** → **Run scenario** → **2×**. Close the drawer.
**Say while waiting:** "We're not faking the result. The scenario changes the simulated *city* —
rain gauges, road sensors, bus feeds, 311 reports and water sensors — each in its own messy
format. CityPulse has to normalize, detect and connect it on its own. The pill up top counts the
storyline beats the analysis has actually detected."

### 3. Watch it develop (0:45–1:20)
**Show:** blue rain cells over Zone 3; the zone goes **amber**, then **red** with glowing traffic
corridors and a waterlogging icon cluster; the heart turns red and beats faster.
**Say:** "Rain first, then traffic builds, water rises on the streets, reports come in — same zone,
same ten-minute window. Only then does CityPulse call it a possible disruption."

### 4. Ask why (1:30–2:50)
**Click:** the top alert (*Elevated traffic disruption risk · Zone 3*).
**Show:** the zone story — status, what's happening, measured evidence, possible relationship,
advice for residents.
**Say:** "Look at the wording: the signals *may be related* — a possible link, not a confirmed
cause. And residents get one sentence of advice."
**Click:** *Show the data behind this* → point at a metric card and *Why these flags?*
**Say:** "Every flag is traceable: value, normal for this time of day, percentage, rule, strength."

### 5. Break something (2:50–3:30)
**Click:** Demo → **Feed failures** → Weather → **Outage**. Close the drawer.
**Show:** the header data chip turns amber (*Weather using fallback data*, then *temporarily
unavailable*); an info alert appears; the zone story later says CityPulse *cannot check* whether
rain is involved.
**Say:** "One feed fails — everything else keeps running, and we say exactly what we can no
longer check instead of guessing."
Set Weather back to **Healthy**.

### 6. Past data (3:30–4:10)
**Click:** header **Replay**. Click the key-moment chips: *Rain begins → Traffic increases →
Possible relationship found → Potential disruption flagged*.
**Say:** "This is yesterday's recorded storm, replayed minute by minute through the exact same
engine and agent — REPLAY mode, archive data, clearly not live."
**Click:** **Back to live**.

### 7. Close (4:10)
**Say:** "Disconnected signals, one honest pulse: where, what, how serious — and only possibly
why. In a real city you swap the simulated feeds for real ones; everything else stays."

## Other scenarios worth showing

| Scenario | Zone | What it demonstrates | Typical time to result at 1× |
|---|---|---|---|
| Flash flood | 4 | Rain + street flooding + waterlogging surge | ~75 s |
| Major congestion | 2 | Traffic → bus delays → air quality, **no weather link claimed** | ~145 s |
| Road accident | 1 | Accident reports → queue → possible disruption | ~95–145 s |
| Power outage | 4 | Outage + signal reports → traffic at dark junctions | ~130 s |
| Poor air quality | 5 | Flagged, but *"no related signal — no cause claimed"* | ~25 s |
| Severe storm | 2 | Rain + flooding + power cuts, three linked signals | ~85 s |
| Multi-event evening | 3 (+1) | Rain in Zone 3 and an unrelated jam in Zone 1 that is **not** blamed on the rain | ~70 s |

Use **2×/4×** to speed any of them up, **Pause** to talk over a frozen moment, **Reset** to
return to normal. The **Custom** tab sets rain, flooding, traffic, accident, outage and air
pollution with sliders for any zone.

## If something goes wrong

| Problem | Recovery |
|---|---|
| Story feels slow | Switch to **4×** in the demo pill, or use **Replay** — it shows the same story instantly. |
| Map background doesn't load (no internet) | Say "map tiles need internet; the data doesn't" — zones, labels and panels still work. |
| Screen shows "Connecting…" | Backend stopped — restart it; the page reconnects by itself. |
| Something looks stuck after the demo | Demo → **Normal city**. |
| A judge asks to break something | Demo → Feed failures — let them pick any feed and mode. |

## Shorter version (2 minutes)

1. Opening screen (10-second read) — 15 s
2. **Replay** → click through the key moments → click the red zone — 60 s
3. Demo → Feed failures → Weather **Outage** → point at the data chip — 30 s
4. Close — 15 s
