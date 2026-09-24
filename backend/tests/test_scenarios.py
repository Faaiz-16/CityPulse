"""Demo scenario presets, instant start, playback (pause / speed) and custom scenarios.

Each preset must change the simulated feeds and produce its expected outcome through the real
pipeline — the storyline beats are ticked only by actual analysis output.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.simulation.controller import SimulationError
from app.simulation.scenarios import PRESETS, PRESETS_BY_ID
from tests.conftest import T0

EXPECTED_STATUS = {p.id: ("YELLOW" if p.id == "poor_air" else "RED") for p in PRESETS}


def run(pipeline, seconds: int, start=T0, step: int = 3):
    for i in range(1, seconds // step + 1):
        pipeline.tick(start + timedelta(seconds=i * step))


def zone(pipeline, zone_id: str):
    return next(z for z in pipeline.state.zones if z.id == zone_id)


@pytest.mark.parametrize("preset", PRESETS, ids=[p.id for p in PRESETS])
def test_every_preset_propagates_through_the_pipeline(pipeline, preset):
    """Instant start: the situation is fully developed the moment the scenario is chosen."""
    pipeline.run_scenario(preset.id, now=T0)
    scenario = pipeline.state.simulation["scenario"]
    assert scenario["complete"], [s for s in scenario["stages"] if not s["reached_at"]]
    assert scenario["elapsed_s"] == preset.ready_s
    z = zone(pipeline, preset.zone)
    assert z.status.value == EXPECTED_STATUS[preset.id]
    text = " ".join([z.headline, *(r.statement for r in z.relationships)]).lower()
    assert "caused" not in text and "due to" not in text


def test_events_form_a_local_hotspot(pipeline):
    """A storm hits its centre hardest and fades with distance; far areas stay normal."""
    pipeline.run_scenario("heavy_rain", now=T0)
    rain = {z.id: z.metrics["rain_mm_h"].current or 0 for z in pipeline.state.zones}
    assert rain["F4"] > rain["F5"] > rain["G5"] > 0  # centre > neighbour > diagonal
    assert rain["A9"] == 0 and rain["I1"] == 0
    red = [z.id for z in pipeline.state.zones if z.status.value == "RED"]
    assert "F4" in red and len(red) <= 9


def test_watch_mode_unfolds_live(pipeline):
    pipeline.run_scenario("heavy_rain", now=T0, instant=False)
    scenario = pipeline.state.simulation["scenario"]
    assert scenario["elapsed_s"] == 0 and not any(s["reached_at"] for s in scenario["stages"])
    run(pipeline, 150)
    assert pipeline.state.simulation["scenario"]["complete"]


def test_poor_air_is_flagged_but_no_cause_is_claimed(pipeline):
    pipeline.run_scenario("poor_air", now=T0)
    z = zone(pipeline, PRESETS_BY_ID["poor_air"].zone)
    assert z.metrics["aqi"].is_anomaly and not z.relationships
    assert "insufficient evidence" in z.insufficient_evidence[0]


def test_unknown_scenario_is_rejected_without_resetting(pipeline):
    pipeline.trigger_event("heavy_rain", "E4", now=T0)
    with pytest.raises(SimulationError):
        pipeline.run_scenario("meteor_strike", now=T0)
    assert pipeline.model.effects  # the running event was not wiped


def test_pause_freezes_the_scenario_and_resume_continues(pipeline):
    pipeline.run_scenario("heavy_rain", now=T0, instant=False)
    run(pipeline, 30)
    t = T0 + timedelta(seconds=30)
    pipeline.playback("pause", now=t)
    frozen = pipeline.state.simulation["scenario"]["elapsed_s"]
    run(pipeline, 60, start=t)
    assert pipeline.state.simulation["scenario"]["elapsed_s"] == frozen
    assert pipeline.state.simulation["clock"]["paused"] is True
    pipeline.playback("resume", now=t + timedelta(seconds=60))
    run(pipeline, 30, start=t + timedelta(seconds=60))
    assert pipeline.state.simulation["scenario"]["elapsed_s"] >= frozen + 27


def test_speed_makes_the_story_unfold_faster(pipeline):
    pipeline.run_scenario("heavy_rain", now=T0, instant=False)
    pipeline.playback("speed", speed=4, now=T0)
    run(pipeline, 60)
    scenario = pipeline.state.simulation["scenario"]
    assert scenario["elapsed_s"] >= 230
    assert zone(pipeline, "F4").metrics["rain_mm_h"].is_anomaly
    with pytest.raises(SimulationError):
        pipeline.playback("speed", speed=3, now=T0)


def test_custom_scenario_drives_real_feeds(pipeline):
    pipeline.apply_custom("C7", {"rain": 1.0, "flooding": 0.8, "air": 0}, now=T0)
    labels = [e.label for e in pipeline.model.effects]
    assert len(labels) == 2 and all(label.startswith("Custom: ") for label in labels)
    run(pipeline, 120)
    z = zone(pipeline, "C7")
    assert z.metrics["rain_mm_h"].is_anomaly and z.metrics["water_level_cm"].is_anomaly
    pipeline.apply_custom("C7", {"rain": 0}, now=T0 + timedelta(seconds=121))
    assert pipeline.model.effects == []  # sliders at zero clear the custom scenario


def test_custom_rejects_unknown_controls_and_areas(pipeline):
    with pytest.raises(SimulationError):
        pipeline.apply_custom("C7", {"earthquake": 1.0}, now=T0)
    with pytest.raises(SimulationError):
        pipeline.apply_custom("Z9", {"rain": 1.0}, now=T0)


def test_scenario_api():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        presets = client.get("/api/simulation/scenarios").json()
        assert {p["id"] for p in presets} >= {"heavy_rain", "accident", "power_outage", "poor_air"}
        assert presets[0]["storyline"] and presets[0]["place"] == "Walled City"
        assert client.post("/api/simulation/scenario", json={"name": "accident"}).json()["ok"]
        status = client.get("/api/simulation/status").json()
        assert status["scenario"]["id"] == "accident" and status["clock"]["speed"] == 1
        assert status["scenario"]["complete"]  # instant: already fully developed
        assert client.post("/api/simulation/scenario", json={"name": "traffic", "instant": False}).json()["ok"]
        assert client.post("/api/simulation/playback", json={"action": "speed", "speed": 2}).json()["ok"]
        assert client.post("/api/simulation/playback", json={"action": "pause"}).json()["ok"]
        assert client.get("/api/simulation/status").json()["clock"]["paused"] is True
        assert client.post("/api/simulation/scenario", json={"name": "nope"}).status_code == 400
        bad = client.post("/api/simulation/custom", json={"zone_id": "F4", "values": {"rain": 9}})
        assert bad.status_code == 422
        assert client.post("/api/simulation/custom", json={"zone_id": "Z1", "values": {"rain": 1}}).status_code == 422
        assert client.post("/api/simulation/custom", json={"zone_id": "F4", "values": {"traffic": 1}}).json()["ok"]
        assert client.post("/api/simulation/reset").json()["ok"]
