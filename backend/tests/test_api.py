"""HTTP API behaviour, including safe error responses."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] in ("ok", "degraded")
    assert body["storage"]["ok"] is True
    assert set(body["feeds"]) == {"weather", "traffic", "incidents", "air_quality", "iot_sensors"}


def test_dashboard_contains_everything_the_ui_needs(client):
    body = client.get("/api/dashboard").json()
    assert len(body["zones"]) == 225
    for key in ("pulse", "feeds", "alerts", "summary", "ticker", "simulation", "config"):
        assert key in body
    z = body["zones"][0]
    assert {"status", "status_label", "headline", "metrics", "anomalies", "relationships"} <= set(z)


def test_zone_endpoints(client):
    zones = client.get("/api/zones").json()
    assert zones[0]["boundary"]["type"] == "Polygon"
    detail = client.get("/api/zones/C2-9").json()
    assert detail["zone"]["id"] == "C2-9" and "series" in detail and "explanation" in detail
    missing = client.get("/api/zones/Z9")
    assert missing.status_code == 404 and "Unknown block" in missing.json()["detail"]


@pytest.mark.parametrize("path", ["/api/anomalies", "/api/correlations", "/api/risks", "/api/summary",
                                  "/api/sources/status", "/api/alerts", "/api/agent", "/api/sensors",
                                  "/api/timeline", "/api/simulation/status", "/api/incidents"])
def test_read_endpoints_ok(client, path):
    assert client.get(path).status_code == 200


def test_readings_endpoint(client):
    rows = client.get("/api/readings", params={"zone_id": "C3-2", "metric": "congestion_pct"}).json()
    common_model = {"source", "source_type", "provider", "zone_id", "timestamp", "ingested_at", "metric", "value",
                    "unit", "confidence", "data_status", "sensor_id", "lat", "lon", "metadata"}
    assert rows and set(rows[0]) == common_model
    assert rows[0]["zone_id"] == "C3-2" and rows[0]["metric"] == "congestion_pct" and rows[0]["unit"] == "%"


def test_invalid_simulation_requests_get_clear_errors(client):
    bad_event = client.post("/api/simulation/event", json={"event": "meteor", "zone_id": "C2-9"})
    assert bad_event.status_code == 422 and bad_event.json()["error"] == "invalid_request"
    bad_zone = client.post("/api/simulation/event", json={"event": "heavy_rain", "zone_id": "Z9"})
    assert bad_zone.status_code == 422
    bad_feed = client.post("/api/simulation/feed-fault", json={"feed_id": "radar", "mode": "outage"})
    assert bad_feed.status_code == 400


def test_simulation_endpoints(client):
    assert client.post("/api/simulation/event", json={"event": "heavy_rain", "zone_id": "C2-9"}).json()["ok"]
    assert client.post("/api/simulation/feed-fault", json={"feed_id": "weather", "mode": "outage"}).json()["ok"]
    assert client.post("/api/simulation/scenario", json={"name": "full"}).json()["ok"]
    assert client.get("/api/simulation/status").json()["scenario"]["focus_zone"] == "C2-9"
    assert client.post("/api/simulation/reset").json()["ok"]
    feeds = client.get("/api/sources/status").json()
    assert all(f["fault_mode"] == "none" for f in feeds)


def test_unexpected_errors_do_not_leak_internals(client, monkeypatch):
    from app.services.pipeline import CityPulse

    def explode(self, zone_id, now=None):
        raise RuntimeError("secret internal detail /etc/passwd")

    monkeypatch.setattr(CityPulse, "zone_detail", explode)
    r = client.get("/api/zones/C3-2")
    assert r.status_code == 500
    assert "secret" not in r.text and "Traceback" not in r.text
    assert r.json()["error"] == "internal_error"
