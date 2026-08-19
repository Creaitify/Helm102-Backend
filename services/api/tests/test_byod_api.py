"""Tests for BYOD real data ingestion, file upload, JSON parsing, and Governor integration."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from modules.ads.byod_importer import (
    clear_active_byod_snapshot,
    get_active_byod_snapshot,
    has_active_byod_snapshot,
    import_byod_file,
    parse_csv,
    parse_json,
    set_active_byod_snapshot,
)
from services.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_byod_json_parsing():
    """Test parsing JSON array of campaign records."""
    json_data = [
        {
            "campaign_id": "cmp_json_01",
            "campaign_name": "Real Google Search Growth",
            "platform": "google_ads",
            "spend": 55000.0,
            "impressions": 140000,
            "clicks": 9200,
            "conversions": 480,
            "roas": 3.6,
            "cpa": 114.58,
            "ctr": 6.57,
            "status": "ENABLED",
        },
        {
            "campaign_id": "cmp_json_02",
            "campaign_name": "Real Meta Retargeting Core",
            "platform": "meta_ads",
            "spend": 70000.0,
            "impressions": 310000,
            "clicks": 13000,
            "conversions": 520,
            "roas": 2.4,
            "cpa": 134.62,
            "ctr": 4.19,
            "status": "ENABLED",
        },
    ]

    snapshot = parse_json(json_data)
    assert len(snapshot.campaigns) == 2
    assert snapshot.total_spend_inr == 125000.0
    assert snapshot.blended_roas > 2.8
    assert snapshot.source == "byod"


def test_byod_upload_csv_endpoint(client: TestClient):
    """Test POST /api/byod/upload with CSV content."""
    csv_text = (
        "campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status\n"
        "cmp_live_01,Real Estate Search,google_ads,48000,110000,7500,390,3.8,123.08,6.82,ENABLED\n"
        "cmp_live_02,Real Estate Video,meta_ads,62000,280000,11500,410,2.2,151.22,4.11,ENABLED\n"
    )

    resp = client.post(
        "/api/byod/upload",
        json={
            "file_content": csv_text,
            "filename": "real_campaigns.csv",
            "activate": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["campaign_count"] == 2
    assert data["activated"] is True
    assert data["total_spend_inr"] == 110000.0
    assert has_active_byod_snapshot() is True

    # Check GET /api/byod/current
    cur_resp = client.get("/api/byod/current")
    assert cur_resp.status_code == 200
    cur_data = cur_resp.json()
    assert cur_data["active"] is True
    assert cur_data["campaign_count"] == 2

    # Check health reflects BYOD
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["data_source"] == "byod"

    # Clean up via DELETE /api/byod/current
    del_resp = client.delete("/api/byod/current")
    assert del_resp.status_code == 200
    assert del_resp.json()["active"] is False
    assert has_active_byod_snapshot() is False


def test_byod_upload_base64_json_endpoint(client: TestClient):
    """Test POST /api/byod/upload with Base64 encoded JSON data."""
    payload = {
        "campaigns": [
            {
                "campaign_id": "cmp_b64_01",
                "campaign_name": "SaaS B2B Direct Search",
                "platform": "google_ads",
                "spend_inr": 80000.0,
                "impressions": 190000,
                "clicks": 11000,
                "conversions": 600,
                "roas": 4.1,
                "cpa_inr": 133.33,
                "ctr": 5.79,
                "status": "ENABLED",
            }
        ]
    }
    b64_str = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    resp = client.post(
        "/api/byod/upload",
        json={
            "file_content": b64_str,
            "filename": "dataset.json",
            "activate": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["campaign_count"] == 1
    assert data["campaigns"][0]["campaign_name"] == "SaaS B2B Direct Search"

    clear_active_byod_snapshot()


@pytest.mark.asyncio
async def test_governor_run_with_active_byod_real_data(client: TestClient):
    """Verify that Governor run uses active BYOD real dataset when present."""
    csv_text = (
        "campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status\n"
        "cmp_user_01,Custom User Campaign Alpha,google_ads,50000,120000,8000,400,3.5,125.0,6.67,ENABLED\n"
        "cmp_user_02,Custom User Campaign Beta,meta_ads,40000,180000,7000,200,1.8,200.0,3.89,ENABLED\n"
    )
    snap = parse_csv(csv_text)
    set_active_byod_snapshot(snap)

    # Start run with wait=True (synchronous proposal generation)
    resp = client.post(
        "/api/runs",
        json={
            "objective": "Scale Alpha and optimize Beta",
            "wait": True,
        },
    )
    assert resp.status_code == 200
    state = resp.json()
    assert state["status"] == "pending_approval"
    proposal = state["proposal"]
    assert proposal["data_source"] == "byod"
    assert len(proposal["analyst_findings"]["per_campaign"]) == 2
    assert proposal["analyst_findings"]["per_campaign"][0]["campaign_name"] == "Custom User Campaign Alpha"

    clear_active_byod_snapshot()


def test_byod_upload_csv_with_crlf_and_unquoted_newlines(client: TestClient):
    """Verify that CSV with Windows CRLF (\r\n), Mac CR (\r), and unquoted fields parses cleanly without csv.Error."""
    crlf_csv_text = (
        "campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status\r\n"
        "cmp_crlf_01,Mutual Fund SIP Growth,google_ads,45000,125000,8400,420,3.4,107.14,6.72,ENABLED\r\n"
        "cmp_crlf_02,Retargeting High ROAS,meta_ads,55000,210000,9500,450,2.8,122.22,4.52,ENABLED\r"
    )

    resp = client.post(
        "/api/byod/upload",
        json={
            "file_content": crlf_csv_text,
            "filename": "windows_export.csv",
            "activate": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["campaign_count"] == 2
    assert data["total_spend_inr"] == 100000.0

    clear_active_byod_snapshot()


def test_byod_upload_messy_multichannel_dataset(client: TestClient):
    """Verify ingestion of messy multi-channel datasets with TikTok Ads, ad_spend, decimal CTR, CPC, and revenue."""
    csv_file = Path("services/api/data/sample_multichannel_campaigns.csv")
    assert csv_file.is_file(), "Sample dataset file must exist"
    content = csv_file.read_text(encoding="utf-8")

    resp = client.post(
        "/api/byod/upload",
        json={
            "file_content": content,
            "filename": "multichannel_marketing_raw.csv",
            "activate": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["campaign_count"] >= 300
    assert data["total_spend_inr"] > 0
    assert data["blended_roas"] > 0

    # Verify synthesized campaign names and platform normalization
    platforms = {c["platform"] for c in data["campaigns"]}
    assert "google_ads" in platforms
    assert "meta_ads" in platforms
    assert "tiktok_ads" in platforms

    # Verify CTR normalization (0.0353 -> 3.53%)
    first_cmp = data["campaigns"][0]
    assert first_cmp["ctr"] > 1.0  # Normalized to percentage format (e.g. 3.53)
    assert "[" in first_cmp["campaign_name"]  # Synthesized descriptive title

    # Verify /api/byod/current reflects the active 300+ dataset
    curr_resp = client.get("/api/byod/current")
    assert curr_resp.status_code == 200
    curr_data = curr_resp.json()
    assert curr_data["active"] is True
    assert curr_data["campaign_count"] >= 300

    # Verify Governor run execution on active BYOD dataset
    run_resp = client.post(
        "/api/runs",
        json={
            "objective": "Scale best performing multi-channel campaigns",
            "business_context": {"industry": "Multi-channel", "quarter": "Q3"},
            "wait": True,
        },
    )
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert "run_id" in run_data
    assert run_data["status"] in ("pending_approval", "success", "running")

    # Verify dashboard overview aggregation on active BYOD dataset
    dash_resp = client.get("/api/dashboard/overview")
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["data_source"] == "byod"
    assert len(dash_data["campaigns"]) >= 300
    assert len(dash_data["channels"]) >= 3  # Google, Meta, TikTok

    clear_active_byod_snapshot()



