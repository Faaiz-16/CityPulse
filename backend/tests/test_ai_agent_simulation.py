"""AI grounding + fallback, monitoring agent, and demo simulation."""

from datetime import timedelta

import anthropic
import httpx
import pytest

from app.ai import llm
from app.ai.llm import SummaryOut, ZoneExplanationOut
from app.ai.summarizer import Summarizer
from app.ai.validator import validate
from app.config import Settings
from app.simulation.controller import SimulationError
from tests.conftest import T0

FACTS = {
    "as_of_local_time": "15:00", "rolling_window_minutes": 10, "city_status": "RED",
    "zones": [
        {"zone_id": "Z3", "zone_name": "Zone 3 — East", "status": "RED", "anomalies": [
            {"signal": "Rainfall", "current": 26.5, "unit": "mm/h", "normal": 0, "deviation_pct": None},
            {"signal": "Traffic congestion", "current": 64.2, "unit": "%", "normal": 36.1, "deviation_pct": 77.8}],
         "possible_relationships": [], "risk_insights": [], "insufficient_evidence": [], "cannot_assess": []},
        {"zone_id": "Z1", "zone_name": "Zone 1 — Central", "status": "GREEN", "anomalies": [],
         "possible_relationships": [], "risk_insights": [], "insufficient_evidence": [], "cannot_assess": []},
    ],
    "degraded_feeds": [],
}


def summary(text: str, zones=None) -> SummaryOut:
    return SummaryOut(headline="Heavy rain in Zone 3", whats_happening=text, why_it_may_matter="Slower travel.",
                      possible_connection="The signals may be related.", zones=zones or [])


# ------------------------------------------------------------------- validator

def test_grounded_summary_passes():
    assert validate(summary("Rain is 26.5 mm/h and traffic is about 78% above normal in Zone 3."), FACTS) == []


def test_invented_numbers_rejected():
    problems = validate(summary("Rain is 40 mm/h and 12 roads are closed."), FACTS)
    assert any("40" in p for p in problems) and any("12" in p for p in problems)


@pytest.mark.parametrize("phrase", ["The rain caused the traffic.", "Traffic is up due to rain.",
                                    "Rain led to congestion.", "Congestion is because of the storm."])
def test_causal_language_rejected(phrase):
    assert any("causal" in p for p in validate(summary(phrase), FACTS))


def test_explaining_a_green_zone_is_rejected():
    z = ZoneExplanationOut(zone_id="Z1", whats_happening="x", why_it_may_matter="y", possible_connection="z")
    assert any("unexpected zone" in p for p in validate(summary("Rain in Zone 3.", [z]), FACTS))


# -------------------------------------------------------------------- fallback

def test_no_api_key_uses_template(pipeline):
    assert pipeline.state.summary.generated_by == "template"
    assert pipeline.state.summary.headline


def test_ai_service_failure_returns_none(monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            self.messages = self

        def parse(self, **kwargs):
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    monkeypatch.setattr(llm.anthropic, "Anthropic", Boom)
    assert llm.generate(FACTS, "key", "claude-opus-5", 1) is None


def test_summarizer_keeps_template_when_ai_fails(monkeypatch, pipeline):
    monkeypatch.setattr(llm, "generate", lambda *a, **k: None)
    s = Summarizer(Settings(run_background_loop=False, ANTHROPIC_API_KEY="test-key"))
    zones, feeds = pipeline.state.zones, pipeline.state.feeds
    first, _ = s.summarize(zones, feeds, T0)
    s._run({"zones": [], "degraded_feeds": [], "city_status": "GREEN"}, "fp")  # the background call
    second, _ = s.summarize(zones, feeds, T0)
    assert first.generated_by == second.generated_by == "template"
    assert "fallback" in s.status


def test_summarizer_uses_validated_ai_text(monkeypatch, pipeline):
    good = SummaryOut(headline="All zones look normal.", whats_happening="Everything is within the usual range.",
                      why_it_may_matter="No action needed.", possible_connection="Nothing unusual to connect.",
                      zones=[])
    monkeypatch.setattr(llm, "generate", lambda *a, **k: good)
    s = Summarizer(Settings(run_background_loop=False, ANTHROPIC_API_KEY="test-key"))
    zones, feeds = pipeline.state.zones, pipeline.state.feeds
    from app.ai.facts import build_facts, fingerprint
    facts = build_facts(zones, feeds, T0, s.s.tz, 10)
    s._run(facts, fingerprint(facts))
    result, _ = s.summarize(zones, feeds, T0)
    assert result.generated_by == "ai" and result.headline == "All zones look normal."


# ----------------------------------------------------------------------- agent

def test_agent_raises_disruption_alert_with_separated_epistemics(pipeline):
    pipeline.trigger_event("heavy_rain", "Z3", now=T0)
    for i in range(1, 50):
        pipeline.tick(T0 + timedelta(seconds=3 * i))
    critical = [a for a in pipeline.agent.active() if a.level == "critical"]
    assert len(critical) == 1
    alert = critical[0]
    assert alert.zone_id == "Z3" and alert.kind == "potential_disruption"
    assert alert.observed and "may be related" in alert.possible_relationship
    assert alert.causation_note.startswith("Not a confirmed cause")
    assert any("Decision" in line for line in pipeline.agent.trace)


def test_agent_resolves_alert_after_conditions_clear(pipeline):
    pipeline.trigger_event("heavy_rain", "Z3", now=T0)
    for i in range(1, 50):
        pipeline.tick(T0 + timedelta(seconds=3 * i))
    assert pipeline.agent.active()
    pipeline.sim.clear()
    t = T0 + timedelta(seconds=150)
    for i in range(1, 260):  # rolling window must empty out
        pipeline.tick(t + timedelta(seconds=3 * i))
    assert not [a for a in pipeline.agent.active() if a.zone_id == "Z3"]
    assert any(a.zone_id == "Z3" for a in pipeline.agent.recent_resolved())


def test_quiet_city_raises_no_alerts(pipeline):
    for i in range(1, 30):
        pipeline.tick(T0 + timedelta(seconds=3 * i))
    assert pipeline.agent.active() == []


# ------------------------------------------------------------------ simulation

@pytest.mark.parametrize("event,zone", [("meteor", "Z3"), ("heavy_rain", "Z9")])
def test_invalid_simulation_input_rejected(pipeline, event, zone):
    with pytest.raises(SimulationError):
        pipeline.trigger_event(event, zone, now=T0)


def test_full_scenario_reaches_every_stage(pipeline):
    pipeline.run_full_scenario(now=T0)
    for i in range(1, 60):
        pipeline.tick(T0 + timedelta(seconds=3 * i))
    stages = pipeline.state.simulation["scenario"]["stages"]
    assert all(s["reached_at"] is not None for s in stages), stages
    at = {s["key"]: s["reached_at"] for s in stages}
    assert at["rain"] <= at["traffic"]
    assert at["link"] <= at["disruption"]
    z3 = next(z for z in pipeline.state.zones if z.id == "Z3")
    assert z3.status.value == "RED"


def test_unrelated_traffic_spike_is_not_linked_to_rain(pipeline):
    pipeline.run_full_scenario(now=T0)
    for i in range(1, 80):
        pipeline.tick(T0 + timedelta(seconds=3 * i))
    z1 = next(z for z in pipeline.state.zones if z.id == "Z1")
    assert z1.metrics["congestion_pct"].is_anomaly
    assert not any(r.rule_id.startswith("rain") for r in z1.relationships)


def test_reset_returns_city_to_normal(pipeline):
    pipeline.trigger_event("heavy_rain", "Z3", now=T0)
    for i in range(1, 40):
        pipeline.tick(T0 + timedelta(seconds=3 * i))
    pipeline.reset(now=T0 + timedelta(seconds=200))
    assert all(z.status.value == "GREEN" for z in pipeline.state.zones)
    assert pipeline.agent.active() == []


def test_simulation_is_deterministic(settings):
    from app.services.pipeline import CityPulse

    def run_once():
        p = CityPulse(settings)
        p.startup(T0)
        p.trigger_event("heavy_rain", "Z3", now=T0)
        for i in range(1, 40):
            p.tick(T0 + timedelta(seconds=3 * i))
        z3 = next(z for z in p.state.zones if z.id == "Z3")
        return z3.metrics["congestion_pct"].current, sorted(i.id for i in z3.recent_incidents)

    assert run_once() == run_once()


def test_finished_events_are_forgotten_and_live_apis_resume(pipeline):
    pipeline.trigger_event("traffic_spike", "Z1", duration_s=60, now=T0)
    pipeline.tick(T0 + timedelta(seconds=3))
    assert pipeline.feeds.live_paused
    end = pipeline.model.effects[0].end
    pipeline.tick(end + timedelta(seconds=3))
    assert pipeline.model.effects == [] and not pipeline.feeds.live_paused
