"""Demo scenario presets, playback (pause / speed) and custom scenarios.

Each preset must change the simulated feeds and produce its expected outcome through the real
pipeline — the storyline beats are ticked only by actual analysis output.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.simulation.controller import SimulationError
from app.simulation.scenarios import PRESETS
from tests.conftest import T0

EXPECTED_STATUS = {p.id: ("YELLOW" if p.id == "poor_air" else "RED") for p in PRESETS}


def run(pipeline, seconds: int, start=T0, step: int = 3):
    for i in range(1, seconds // step + 1):
        pipeline.tick(start + timedelta(seconds=i * step))


@pytest.mark.parametrize("preset", PRESETS, ids=[p.id for p in PRESETS])
def test_every_preset_propagates_through_the_pipeline(pipeline, preset):
    pipeline.run_scenario(preset.id, now=T0)
    run(pipeline, 240)
    scenario = pipeline.state.simulation["scenario"]
    assert scenario["complete"], [s for s in scenario["stages"] if not s["reached_at"]]
    zone = next(z for z in pipeline.state.zones if z.id == preset.zone)
    assert zone.status.value == EXPECTED_STATUS[preset.id]
    text = " ".join([zone.headline, *(r.statement for r in zone.relationships)]).lower()
    assert "caused" not in text and "due to" not in text


def test_poor_air_is_flagged_but_no_cause_is_claimed(pipeline):
    pipeline.run_scenario("poor_air", now=T0)
    run(pipeline, 90)
    z5 = next(z for z in pipeline.state.zones if z.id == "Z5")
    assert z5.metrics["aqi"].is_anomaly and not z5.relationships
    assert "insufficient evidence" in z5.insufficient_evidence[0]


def test_unknown_scenario_is_rejected_without_resetting(pipeline):
    pipeline.trigger_event("heavy_rain", "Z2", now=T0)
    with pytest.raises(SimulationError):
        pipeline.run_scenario("meteor_strike", now=T0)
    assert pipeline.model.effects  # the running event was not wiped


def test_pause_freezes_the_scenario_and_resume_continues(pipeline):
    pipeline.run_scenario("heavy_rain", now=T0)
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
    pipeline.run_scenario("heavy_rain", now=T0)
    pipeline.playback("speed", speed=4, now=T0)
    run(pipeline, 60)
    scenario = pipeline.state.simulation["scenario"]
    assert scenario["elapsed_s"] >= 230
    z3 = next(z for z in pipeline.state.zones if z.id == "Z3")
    assert z3.metrics["rain_mm_h"].is_anomaly
    with pytest.raises(SimulationError):
        pipeline.playback("speed", speed=3, now=T0)


def test_custom_scenario_drives_real_feeds(pipeline):
    pipeline.apply_custom("Z2", {"rain": 1.0, "flooding": 0.8, "air": 0}, now=T0)
    labels = [e.label for e in pipeline.model.effects]
    assert len(labels) == 2 and all(label.startswith("Custom: ") for label in labels)
    run(pipeline, 120)
    z2 = next(z for z in pipeline.state.zones if z.id == "Z2")
    assert z2.metrics["rain_mm_h"].is_anomaly and z2.metrics["water_level_cm"].is_anomaly
    pipeline.apply_custom("Z2", {"rain": 0}, now=T0 + timedelta(seconds=121))
    assert pipeline.model.effects == []  # sliders at zero clear the custom scenario


def test_custom_rejects_unknown_controls(pipeline):
    with pytest.raises(SimulationError):
        pipeline.apply_custom("Z2", {"earthquake": 1.0}, now=T0)


def test_scenario_api():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        presets = client.get("/api/simulation/scenarios").json()
        assert {p["id"] for p in presets} >= {"heavy_rain", "accident", "power_outage", "poor_air"}
        assert presets[0]["storyline"]
        assert client.post("/api/simulation/scenario", json={"name": "accident"}).json()["ok"]
        status = client.get("/api/simulation/status").json()
        assert status["scenario"]["id"] == "accident" and status["clock"]["speed"] == 1
        assert client.post("/api/simulation/playback", json={"action": "speed", "speed": 2}).json()["ok"]
        assert client.post("/api/simulation/playback", json={"action": "pause"}).json()["ok"]
        assert client.get("/api/simulation/status").json()["clock"]["paused"] is True
        assert client.post("/api/simulation/scenario", json={"name": "nope"}).status_code == 400
        bad = client.post("/api/simulation/custom", json={"zone_id": "Z1", "values": {"rain": 9}})
        assert bad.status_code == 422
        assert client.post("/api/simulation/custom", json={"zone_id": "Z1", "values": {"traffic": 1}}).json()["ok"]
        assert client.post("/api/simulation/reset").json()["ok"]
