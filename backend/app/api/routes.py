"""HTTP API. Every read endpoint serves the latest pre-computed CityState, so it is fast
and cannot be slowed down by a failing feed or AI call."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.geo import zones as grid
from app.geo.zones import ZONE_IDS, ZONES, load_roads
from app.schemas import HEALTHY_FEED_STATUSES, CityState
from app.services.feed_manager import FAULT_MODES, FEEDS_BY_ID
from app.services.pipeline import CityPulse
from app.simulation.replay import ReplayUnavailable

router = APIRouter(prefix="/api")


def get_pipeline(request: Request) -> CityPulse:
    pipeline: CityPulse | None = getattr(request.app.state, "pipeline", None)
    if pipeline is None or pipeline.state is None:
        raise HTTPException(503, "CityPulse is starting up — try again in a few seconds.")
    return pipeline


def _state(p: CityPulse) -> CityState:
    return p.state


def _zone_or_404(zone_id: str) -> str:
    if zone_id not in ZONE_IDS:
        raise HTTPException(404, f"Unknown block {zone_id!r}. Blocks look like C2-5 (district A1–E5, block 1–9).")
    return zone_id


# ----------------------------------------------------------------------- reads

@router.get("/health")
def health(request: Request):
    p: CityPulse | None = getattr(request.app.state, "pipeline", None)
    if p is None or p.state is None:
        return {"status": "starting"}
    age = (datetime.now(UTC) - p.state.generated_at).total_seconds()
    degraded_feeds = [f.id for f in p.state.feeds if f.status not in HEALTHY_FEED_STATUSES]
    pipeline_ok = age < max(15, 5 * p.s.tick_seconds) and p.last_tick_error is None
    status = "ok" if pipeline_ok and p.db.ok and not degraded_feeds else "degraded"
    return {
        "status": status,
        "pipeline": {"ok": pipeline_ok, "last_update_seconds_ago": round(age, 1), "ticks": p.tick_count},
        "storage": {"ok": p.db.ok, "detail": p.db.last_error or "ok"},
        "feeds": {f.id: f.status.value for f in p.state.feeds},
        "ai": p.summarizer.status,
    }


@router.get("/dashboard", response_model=CityState)
def dashboard(p: CityPulse = Depends(get_pipeline)):
    return _state(p)


@router.get("/zones")
def zones(p: CityPulse = Depends(get_pipeline)):
    by_id = {z.id: z for z in p.state.zones}
    return [
        {"id": z.id, "number": z.number, "name": z.name, "short_name": z.short_name, "row": z.row, "col": z.col,
         "district": z.district, "district_name": z.district_name,
         "status": by_id[z.id].status, "status_label": by_id[z.id].status_label,
         "headline": by_id[z.id].headline, "centroid": z.centroid, "anchor": z.label_point,
         "boundary": {"type": "Polygon", "coordinates": [z.geojson_ring()]}}
        for z in ZONES
    ]


_ROADS = load_roads()


@router.get("/map")
def city_map():
    """Static map furniture: the district/block grid and the main roads (per block) for traffic overlays."""
    return {
        "city": "Jaipur",
        "grid": {"north": grid.GRID_NORTH, "south": grid.GRID_SOUTH, "west": grid.GRID_WEST, "east": grid.GRID_EAST,
                 "rows": grid.ROWS, "cols": grid.COLS, "districts": grid.DISTRICTS, "blocks": grid.BLOCKS,
                 "col_letters": grid.COL_LETTERS},
        "roads": _ROADS,
        "roads_attribution": "Road shapes © OpenStreetMap contributors (ODbL)",
    }


@router.get("/zones/{zone_id}")
def zone_detail(zone_id: str, p: CityPulse = Depends(get_pipeline)):
    return p.zone_detail(_zone_or_404(zone_id))


@router.get("/readings")
def readings(zone_id: str = Query(...), metric: str = Query(...),
             minutes: int = Query(15, ge=1, le=40), p: CityPulse = Depends(get_pipeline)):
    _zone_or_404(zone_id)
    now = p.state.generated_at
    return [{"ts": pt.ts, "value": pt.value, "data_status": pt.data_status, "sensor_id": pt.sensor_id}
            for pt in p.store.series(zone_id, metric, now - timedelta(minutes=minutes), now)]


@router.get("/incidents")
def incidents(zone_id: str | None = None, minutes: int = Query(10, ge=1, le=40),
              p: CityPulse = Depends(get_pipeline)):
    if zone_id:
        _zone_or_404(zone_id)
    now = p.state.generated_at
    return p.store.incidents(now - timedelta(minutes=minutes), now, zone_id)


@router.get("/anomalies")
def anomalies(p: CityPulse = Depends(get_pipeline)):
    return [a for z in p.state.zones for a in z.anomalies]


@router.get("/correlations")
def correlations(p: CityPulse = Depends(get_pipeline)):
    return [r for z in p.state.zones for r in z.relationships]


@router.get("/risks")
def risks(p: CityPulse = Depends(get_pipeline)):
    return [r for z in p.state.zones for r in z.risks]


@router.get("/summary")
def summary(p: CityPulse = Depends(get_pipeline)):
    return {"city": p.state.summary, "zones": p.zone_explanations}


@router.get("/sources/status")
def sources_status(p: CityPulse = Depends(get_pipeline)):
    return p.state.feeds


@router.get("/alerts")
def alerts(p: CityPulse = Depends(get_pipeline)):
    return {"active": p.agent.active(), "recently_resolved": p.agent.recent_resolved()}


@router.get("/agent")
def agent(p: CityPulse = Depends(get_pipeline)):
    return {"runs": p.agent.runs, "last_trace": p.agent.trace, "active_alerts": p.agent.active()}


@router.get("/sensors")
def sensors(p: CityPulse = Depends(get_pipeline)):
    return p.sensor_list()


@router.get("/timeline")
def timeline(p: CityPulse = Depends(get_pipeline)):
    return p.timeline_view()


# ------------------------------------------------------------------ simulation

class EventRequest(BaseModel):
    event: Literal["heavy_rain", "traffic_spike", "incident_cluster", "poor_air", "flooding", "road_accident"]
    zone_id: str = Field(pattern=r"^[A-E][1-5]-[1-9]$")
    intensity: float = Field(1.0, ge=0.2, le=1.5)
    duration_s: float = Field(600, ge=60, le=3600)


class ScenarioRequest(BaseModel):
    name: str = Field("full", max_length=40)
    instant: bool = True  # show the developed situation now (False = watch it unfold live)


class PlaybackRequest(BaseModel):
    action: Literal["pause", "resume", "speed"]
    speed: float | None = None


class CustomRequest(BaseModel):
    zone_id: str = Field(pattern=r"^[A-E][1-5]-[1-9]$")
    values: dict[str, float] = Field(default_factory=dict)
    duration_s: float = Field(600, ge=60, le=3600)

    @field_validator("values")
    @classmethod
    def _levels_in_range(cls, v: dict[str, float]) -> dict[str, float]:
        for key, level in v.items():
            if not 0 <= level <= 1.5:
                raise ValueError(f"{key} must be between 0 and 1.5")
        return v


class FaultRequest(BaseModel):
    feed_id: str
    mode: str


@router.get("/simulation/status")
def simulation_status(p: CityPulse = Depends(get_pipeline)):
    return p.state.simulation


@router.post("/simulation/event")
def simulation_event(body: EventRequest, p: CityPulse = Depends(get_pipeline)):
    label = p.trigger_event(body.event, body.zone_id, body.intensity, body.duration_s)
    p.tick()
    return {"ok": True, "message": f"{label} started. Watch the map — feeds will pick it up within seconds."}


@router.post("/simulation/reset")
def simulation_reset(p: CityPulse = Depends(get_pipeline)):
    p.reset()
    return {"ok": True, "message": "Simulation reset to normal conditions."}


@router.get("/simulation/scenarios")
def simulation_scenarios(p: CityPulse = Depends(get_pipeline)):
    return p.state.simulation["presets"]


@router.post("/simulation/scenario")
def simulation_scenario(body: ScenarioRequest, p: CityPulse = Depends(get_pipeline)):
    name = p.run_scenario(body.name, instant=body.instant)
    if body.instant:
        return {"ok": True, "message": f"{name}: showing the situation now."}
    return {"ok": True, "message": f"Scenario started: {name}. Watch the map — it unfolds over the next minutes."}


@router.post("/simulation/playback")
def simulation_playback(body: PlaybackRequest, p: CityPulse = Depends(get_pipeline)):
    message = p.playback(body.action, body.speed)
    p.tick()
    return {"ok": True, "message": message}


@router.post("/simulation/custom")
def simulation_custom(body: CustomRequest, p: CityPulse = Depends(get_pipeline)):
    message = p.apply_custom(body.zone_id, body.values, body.duration_s)
    p.tick()
    return {"ok": True, "message": message}


@router.post("/simulation/feed-fault")
def simulation_feed_fault(body: FaultRequest, p: CityPulse = Depends(get_pipeline)):
    if body.feed_id not in FEEDS_BY_ID:
        raise HTTPException(400, f"Unknown feed {body.feed_id!r}. Valid feeds: {', '.join(FEEDS_BY_ID)}.")
    if body.mode not in FAULT_MODES:
        raise HTTPException(400, f"Unknown mode {body.mode!r}. Valid modes: {', '.join(FAULT_MODES)}.")
    p.set_feed_fault(body.feed_id, body.mode)
    p.tick()
    return {"ok": True, "message": f"{FEEDS_BY_ID[body.feed_id].label}: fault mode set to {body.mode}."}


# ---------------------------------------------------------------------- replay
# The client owns the playhead: it asks for frame i. Frames are computed once and cached.

def _replay_or_error(fn):
    try:
        return fn()
    except ReplayUnavailable as exc:
        raise HTTPException(404, str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(404, "Replay frame out of range.") from exc


@router.get("/replay")
def replay_meta(p: CityPulse = Depends(get_pipeline)):
    return _replay_or_error(p.replay.meta)


@router.get("/replay/frames/{index}", response_model=CityState)
def replay_frame(index: int, p: CityPulse = Depends(get_pipeline)):
    return _replay_or_error(lambda: p.replay.frame(index).state)


@router.get("/replay/frames/{index}/zones/{zone_id}")
def replay_zone(index: int, zone_id: str, p: CityPulse = Depends(get_pipeline)):
    _zone_or_404(zone_id)
    return _replay_or_error(lambda: p.replay.zone_detail(index, zone_id))
