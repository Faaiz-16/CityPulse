# CityPulse — Presentation

**Format:** 10 slides (16:9), made to support the 7-minute presentation + live demo slot
described in [DEMO.md](DEMO.md). The slides take about 3 minutes in total; the rest is the live
product. Speaker notes are in each slide's notes pane, and [PITCH_SCRIPT.md](PITCH_SCRIPT.md) has
the same text in one place.

The deck covers every section the hackathon asks for:

| Required section | Slide(s) |
|---|---|
| Problem statement | 2 |
| Proposed solution | 3 |
| System architecture | 4 |
| Key features | 5 |
| Demo screenshots | 6, 7 |
| Future scope | 9 |

Design: dark background to match the app, one idea per slide, real screenshots on most slides,
and few words. Colours follow the app: teal for normal and CityPulse itself, amber for
attention, red for disruption, violet for "possible link" and "what may happen next".

---

| # | Slide | Visual | Key message |
|---|---|---|---|
| 1 | **CityPulse** (title) | Map of Jaipur with the Walled City hotspot | Understand what's happening in your city at a glance. Team name and members |
| 2 | **Problem statement**: "City data exists. The picture doesn't." | Five feeds, each with its own format problem, pointing at a confused resident | Data is scattered, not connected, and arrives too late. The real challenge is fusing it into one picture people can trust |
| 3 | **Proposed solution**: "Five messy feeds in. One live, honest map out." | Feed icons → CityPulse → screenshot of the area panel; tiles for 225 blocks, 3 s, 10 s | One live map, updated every 3 s, readable in about 10 s |
| 4 | **System architecture**: "One pipeline, every 3 seconds" | Diagram: 5 feeds → backend (feed manager, normalization, store, analysis engine, CityState, plus summary, agent, demo and replay) → REST API → React frontend | The API serves one pre-computed state; the same engine runs live, demo and replay. Same diagram as [`architecture.png`](architecture.png) |
| 5 | **Key features**: "Six things CityPulse does" | Six cards, each a real screenshot | Live map · spots the unusual · possible links, not causes · what may happen next · plain-language summary · survives feed failures |
| 6 | **Demo screenshots**: the working product | Full app screenshot with 4 numbered callouts; Live, Demo and Replay cards | It's a working product in three modes on one engine |
| 7 | **Demo screenshots**: end-to-end journey | 4 screenshots: pick a situation → see the hotspot → open the block → read the summary | From a situation to advice in four clicks. Backup if the live demo fails |
| 8 | **Technical implementation** | 5 engineering decisions and 6 measured numbers, plus a technology row | Pre-computed state, one validated data model, robust statistics, correlation never causation, graceful failure |
| 9 | **Future scope**: "From working prototype to city service" | "Today" checklist → 6 "Next" cards, marked as planned, not built | Real feeds, resident alerts, learned links, city-scale cloud, deeper replay, 3D view |
| 10 | **Thank you** | Links (GitHub, docs, deployment status, team) and a GitHub QR code | Questions, or more of the live demo |

## Every number on the slides

All numbers were measured on the running prototype (simulated data) or come from the code:
225 blocks · 5 feeds · 3-second tick · 45 minutes kept live · 3 days of history · all blocks
analysed in under 0.1 s · a demo situation on screen in about 1.4 s · heavy-rain demo: rain
detected at 20 s and a possible disruption at 100 s · no red blocks in two simulated quiet rush
hours · 128 automated tests.

## Before presenting

- Replace `[Team name]` and `[Member 1…4]` on slides 1 and 10, and fill in the team table in the
  [README](../README.md#team).
- Keep a PDF copy of the deck in case the projector laptop can't open the `.pptx` file.
