"""Tests for FastAPI HTTP endpoints."""

from fastapi.testclient import TestClient
from services.api.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "gateway_mode" in data
    assert "dry_run" in data


def test_create_run_and_approval_flow():
    # 1. Create run (wait=True blocks until the proposal is ready)
    resp = client.post(
        "/api/runs",
        json={"objective": "Scale high performing mutual fund ads", "wait": True},
    )
    assert resp.status_code == 200
    run = resp.json()
    run_id = run["run_id"]
    assert run["status"] == "pending_approval"
    assert "proposal" in run
    assert run["proposal"]["data_source"] in ("synthetic", "byod", "live", "degraded")
    assert "campaign_drafts" in run["proposal"]
    assert "agent_reports" in run and "analyst" in run["agent_reports"]

    # 2. Get run state
    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == run_id

    # 3. Get audit trail
    resp = client.get(f"/api/runs/{run_id}/audit")
    assert resp.status_code == 200
    trail = resp.json()
    assert len(trail) >= 6

    # 4. Submit approval
    resp = client.post(
        f"/api/runs/{run_id}/approval",
        json={"decision": "approved", "decision_notes": "Looks solid."},
    )
    assert resp.status_code == 200
    completed = resp.json()
    assert completed["status"] == "completed"
    assert len(completed["execution_results"]) > 0


def test_reject_run_flow():
    resp = client.post("/api/runs", json={"objective": "Test rejection flow", "wait": True})
    run_id = resp.json()["run_id"]

    resp = client.post(
        f"/api/runs/{run_id}/approval",
        json={"decision": "rejected", "decision_notes": "Not needed."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_background_run_returns_immediately_and_streams_progress():
    """Default (non-wait) runs return a run_id at once; the checkpoint then
    progresses hop by hop until pending_approval.

    Uses a context-managed client: the persistent portal event loop is what
    keeps the background asyncio task alive between requests (mirrors uvicorn).
    """
    import time

    with TestClient(app) as bg_client:
        resp = bg_client.post("/api/runs", json={"objective": "Background progress check"})
        assert resp.status_code == 200
        body = resp.json()
        run_id = body["run_id"]
        assert body["status"] == "running"
        assert "proposal" not in body

        final_state = None
        for _ in range(50):
            state = bg_client.get(f"/api/runs/{run_id}").json()
            if state["status"] in ("pending_approval", "failed"):
                final_state = state
                break
            time.sleep(0.2)

    assert final_state is not None, "run never settled"
    assert final_state["status"] == "pending_approval"
    assert len(final_state["hops"]) >= 6
    assert final_state["agent_reports"].keys() >= {"analyst", "creative", "compliance", "budget", "governor"}


def test_connections_endpoints_masked_status():
    resp = client.get("/api/connections")
    assert resp.status_code == 200
    data = resp.json()
    assert "google_ads" in data and "meta_ads" in data
    assert "connected" in data["google_ads"]
    # Raw secret VALUES must never be returned — only masked forms.
    for masked in (data["google_ads"].get("client_id", ""), data["meta_ads"].get("access_token", "")):
        assert masked == "" or "…" in masked, f"unmasked credential leaked: {masked!r}"


def test_health_reports_data_source_facet():
    resp = client.get("/api/health")
    data = resp.json()
    assert data["data_source"] in ("live", "synthetic")
    assert "connections" in data


def test_byod_sample_endpoint():
    resp = client.get("/api/byod/sample")
    assert resp.status_code == 200
    data = resp.json()
    assert "sheets" in data
    assert "Google_Ads" in data["sheets"]


def test_byod_parse_endpoint():
    csv_content = """campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status
cmp_01,Search Intent,google_ads,45000,125000,8400,420,3.4,107.14,6.72,ENABLED"""
    resp = client.post("/api/byod/parse", json={"csv_content": csv_content})
    assert resp.status_code == 200
    data = resp.json()
    assert data["campaign_count"] == 1
    assert data["total_spend_inr"] == 45000.0


def test_citations_verify_endpoint():
    resp = client.post(
        "/api/citations/verify",
        json={
            "headline": "Start Disciplined SIPs for Long-Term Growth",
            "primary_text": "Mutual fund investments are subject to market risks, read all scheme related documents carefully.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_grounding_score"] >= 0.7
    assert data["is_fully_grounded"] is True


