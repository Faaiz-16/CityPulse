"""Predictive impact: possible next impacts here and in neighbouring blocks."""

from fastapi.testclient import TestClient

from app.geo.zones import cell_distance
from app.main import create_app
from app.simulation.scenarios import PRESETS_BY_ID
from tests.conftest import T0


def zone(pipeline, zone_id):
    return next(z for z in pipeline.state.zones if z.id == zone_id)


def test_quiet_city_predicts_nothing(pipeline):
    assert not any(z.predictions for z in pipeline.state.zones)


def test_heavy_rain_predicts_flooding_and_power_cuts_here_and_nearby(pipeline):
    pipeline.run_scenario("heavy_rain", now=T0)
    centre = PRESETS_BY_ID["heavy_rain"].zone
    kinds_here = {p.kind for p in zone(pipeline, centre).predictions}
    assert "power_cut" in kinds_here
    nearby = [z for z in pipeline.state.zones if z.status.value == "GREEN" and z.predictions]
    assert any(p.kind == "flooding" and p.nearby for z in nearby for p in z.predictions)
    # Nothing far from the storm is predicted to be affected.
    affected = [z.id for z in pipeline.state.zones if z.predictions]
    assert all(min(cell_distance(a, b) for b in affected if b != a) < 1.5 for a in affected)
    assert "A5-7" not in affected and "E1-3" not in affected


def test_no_prediction_for_what_is_already_happening(pipeline):
    pipeline.run_scenario("heavy_rain", now=T0)
    for z in pipeline.state.zones:
        for p in z.predictions:
            if p.kind == "traffic":
                assert not z.metrics["congestion_pct"].is_anomaly
            if p.kind == "flooding":
                assert not z.metrics["water_level_cm"].is_anomaly


def test_rain_does_not_predict_worse_air(pipeline):
    pipeline.run_scenario("heavy_rain", now=T0)
    for z in pipeline.state.zones:
        if (z.metrics["rain_mm_h"].current or 0) >= 2.5:
            assert not any(p.kind == "air_quality" for p in z.predictions)


def test_each_situation_has_a_nearby_outlook(pipeline):
    for preset in ("accident", "power_outage", "poor_air", "traffic"):
        pipeline.run_scenario(preset, now=T0)
        assert any(p.nearby for z in pipeline.state.zones for p in z.predictions), preset


def test_predictions_are_worded_as_possibilities(pipeline):
    pipeline.run_scenario("storm", now=T0)
    preds = [p for z in pipeline.state.zones for p in z.predictions]
    assert preds
    for p in preds:
        assert p.likelihood in ("low", "medium", "high") and p.horizon.startswith("next ")
        text = f"{p.label} {p.reason}".lower()
        assert "possible" in text or "may" in text
        assert not any(w in text for w in ("caused", "due to", " will "))


def test_dashboard_carries_predictions():
    with TestClient(create_app()) as client:
        client.post("/api/simulation/scenario", json={"name": "accident"})
        zones = client.get("/api/dashboard").json()["zones"]
        preds = [p for z in zones for p in z["predictions"]]
        assert preds and {"kind", "label", "likelihood", "horizon", "reason", "source_zone", "nearby"} <= set(preds[0])
