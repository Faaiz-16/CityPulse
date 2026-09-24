"""Historical replay of the recorded storm through the same analysis pipeline."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.simulation.history import ARCHIVE_PROVIDER
from tests.conftest import T0


@pytest.fixture
def replay(pipeline):
    return pipeline.replay


def test_replay_finds_the_recorded_event_and_builds_minute_frames(replay):
    meta = replay.meta()
    assert meta["available"] and meta["focus_zone"] == "Z3"
    frames = meta["frames"]
    assert len(frames) > 60
    steps = {(b["t"] - a["t"]) for a, b in zip(frames, frames[1:])}
    assert steps == {timedelta(minutes=1)}


def test_replay_story_calm_then_disruption_then_recovery(replay):
    frames = replay.meta()["frames"]
    assert frames[0]["statuses"]["Z3"] == "GREEN"  # calm before the storm
    assert any(f["statuses"]["Z3"] == "RED" for f in frames)
    assert any(f["statuses"]["Z4"] == "RED" for f in frames)  # the storm also reached Zone 4
    assert frames[-1]["statuses"]["Z3"] == "GREEN"  # recovery
    assert all(f["statuses"]["Z1"] == "GREEN" for f in frames)  # unaffected zones stay calm


def test_replay_key_moments_follow_the_storm_order(replay):
    moments = {m["label"]: m["i"] for m in replay.meta()["key_moments"]}
    assert moments["Rain begins"] < moments["Traffic increases"] <= moments["Possible relationship found"]
    assert moments["Possible relationship found"] <= moments["Potential disruption flagged"]


def test_replay_frame_uses_same_engine_and_agent(replay):
    meta = replay.meta()
    red = next(f["i"] for f in meta["frames"] if f["statuses"]["Z3"] == "RED")
    state = replay.frame(red + 3).state
    assert state.mode == "replay" and state.replay_time == state.generated_at
    z3 = next(z for z in state.zones if z.id == "Z3")
    assert any(r.rule_id == "rain_traffic" for r in z3.relationships)
    assert any(a.kind == "potential_disruption" and a.active for a in state.alerts)
    assert all(f.status.value == "ARCHIVE" for f in state.feeds)
    assert not any(a.kind == "data_quality" for a in state.alerts)  # archive feeds aren't "degraded"


def test_replay_zone_detail_has_minute_series(replay):
    detail = replay.zone_detail(40, "Z3")
    rain = detail["series"]["rain_mm_h"]
    assert len(rain) == 15 and all(p["v"] is not None for p in rain)


def test_frame_out_of_range(replay):
    with pytest.raises(IndexError):
        replay.frame(10_000)


def test_storm_archive_does_not_distort_live_baselines(pipeline):
    # The 1-minute archive is replay-only, and report baselines use the median across days,
    # so yesterday's storm must not make waterlogging look "normal" today.
    evening = T0.replace(hour=13, minute=0)  # 18:30 local
    assert pipeline.baselines.expected_incidents("Z3", "waterlogging_reports", evening, 10) < 1
    assert pipeline.baselines.continuous("Z3", "rain_mm_h", evening).median == 0


def test_archive_rows_are_labelled(pipeline):
    from sqlalchemy import func, select

    from app import database as db
    with db.SessionLocal() as s:
        n = s.scalar(select(func.count()).select_from(db.ReadingRow).where(db.ReadingRow.provider == ARCHIVE_PROVIDER))
    assert n > 0


def test_replay_api():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        meta = client.get("/api/replay").json()
        assert meta["available"]
        frame = client.get("/api/replay/frames/30").json()
        assert frame["mode"] == "replay" and len(frame["zones"]) == 5
        assert client.get("/api/replay/frames/30/zones/Z3").json()["zone"]["id"] == "Z3"
        assert client.get("/api/replay/frames/99999").status_code == 404
        assert client.get("/api/replay/frames/3/zones/Z9").status_code == 404
