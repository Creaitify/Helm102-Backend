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


def _make_test_pdf(text: str) -> bytes:
    escaped = text.replace("(", "\\(").replace(")", "\\)")
    stream = f"BT\n/F1 12 Tf\n72 712 Td\n({escaped}) Tj\nET\n"
    stream_bytes = stream.encode("latin1")
    stream_len = len(stream_bytes)
    pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length {stream_len} >>
stream
{stream}endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000227 00000 n 
0000000300 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
370
%%EOF"""
    return pdf.encode("latin1")


def test_byod_pdf_parsing_and_metrics_extraction():
    from modules.ads.byod_importer import parse_pdf

    raw_pdf = _make_test_pdf(
        "Campaign: Diwali Search Max Spend: 95000 ROAS: 4.35 Clicks: 4200 Conversions: 240"
    )
    snap = parse_pdf(raw_pdf)
    assert len(snap.campaigns) >= 1
    c = snap.campaigns[0]
    assert "Diwali Search Max" in c.campaign_name
    assert c.spend_inr == 95000.0
    assert c.roas == 4.35
    assert c.clicks == 4200
    assert c.conversions == 240
    assert snap.total_spend_inr == 95000.0


def test_byod_upload_pdf_endpoint(client: TestClient):
    clear_active_byod_snapshot()

    raw_pdf = _make_test_pdf(
        "Campaign: Mutual Funds PMax Spend: 120000 ROAS: 3.8 Clicks: 5000 Conversions: 300"
    )
    b64_pdf = "data:application/pdf;base64," + base64.b64encode(raw_pdf).decode("utf-8")

    resp = client.post(
        "/api/byod/upload",
        json={
            "file_content": b64_pdf,
            "filename": "q4_campaign_summary.pdf",
            "activate": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["campaign_count"] >= 1
    assert data["total_spend_inr"] == 120000.0
    assert has_active_byod_snapshot() is True

    # Direct agent invocation uses active BYOD
    analyst_resp = client.post(
        "/api/agents/analyst/invoke",
        json={"prompt": "Analyze our Q4 PDF report performance"},
    )
    assert analyst_resp.status_code == 200
    analyst_data = analyst_resp.json()
    assert analyst_data["meta"]["data_source"] == "byod"
    assert analyst_data["raw"]["account_kpis"]["total_spend_inr"] == 120000.0

    clear_active_byod_snapshot()


def test_agent_invoke_with_attached_pdf(client: TestClient):
    clear_active_byod_snapshot()

    raw_pdf = _make_test_pdf(
        "Campaign: Retargeting Video Boost Spend: 65000 ROAS: 2.9 Clicks: 2800 Conversions: 140"
    )
    b64_pdf = "data:application/pdf;base64," + base64.b64encode(raw_pdf).decode("utf-8")

    resp = client.post(
        "/api/agents/creative/invoke",
        json={
            "prompt": "Write new ad copy based on this attached campaign PDF",
            "file_content": b64_pdf,
            "filename": "brief.pdf",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent"] == "creative"
    assert has_active_byod_snapshot() is True
    assert get_active_byod_snapshot().total_spend_inr == 65000.0

    clear_active_byod_snapshot()



