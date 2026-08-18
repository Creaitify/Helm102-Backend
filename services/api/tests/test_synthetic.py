import pytest
from fastapi.testclient import TestClient
from services.api.main import app

client = TestClient(app)

def test_synthetic_scenarios_and_generate():
    # 1. List scenarios
    resp = client.get("/api/synthetic/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()
    assert len(scenarios) >= 4
    assert any(s["id"] == "growth_and_fatigue" for s in scenarios)

    # 2. Generate scenario
    resp = client.post(
        "/api/synthetic/generate",
        json={"scenario": "scale_winner", "days": 60},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["scenario"] == "scale_winner"
    assert data["campaign_count"] >= 5

    # 3. Get current synthetic snapshot
    resp = client.get("/api/synthetic/current")
    assert resp.status_code == 200
    snapshot = resp.json()
    assert snapshot["campaign_count"] >= 5
    assert snapshot["total_spend_inr"] > 0
    assert snapshot["blended_roas"] > 0
