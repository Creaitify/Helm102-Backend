"""Tests for the direct-agent, chat, conversation, and report surfaces."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """App instance with isolated SQLite stores so tests never touch dev data."""
    tmp = tmp_path_factory.mktemp("helm_api")
    os.environ["HELM_CONVERSATIONS_DB"] = str(tmp / "conversations.sqlite")
    os.environ["HELM_REPORTS_DB"] = str(tmp / "reports.sqlite")
    os.environ["HELM_SECRETS_DIR"] = str(tmp / "secrets")

    # Import after the env is set so the modules pick up the temp paths.
    from services.api.main import app

    with TestClient(app) as test_client:
        yield test_client


# ----------------------------------------------------------------------
# Agents
# ----------------------------------------------------------------------


def test_agent_roster_lists_every_specialist(client):
    agents = client.get("/api/agents").json()
    assert {a["id"] for a in agents} == {
        "governor",
        "analyst",
        "creative",
        "media_buyer",
        "compliance",
    }
    assert all(a["label"] and a["icon"] and a["description"] for a in agents)


@pytest.mark.parametrize(
    "agent_id,prompt,expected_block",
    [
        ("analyst", "Analyze performance for the last 30 days", "kpi_grid"),
        ("media_buyer", "Propose a budget reallocation", "table"),
        ("creative", "Write 3 ad variations for a SIP campaign", "variations"),
        ("compliance", "Guaranteed returns with zero risk", "policy_check"),
    ],
)
def test_direct_agent_returns_renderable_blocks(client, agent_id, prompt, expected_block):
    response = client.post(f"/api/agents/{agent_id}/invoke", json={"prompt": prompt})
    assert response.status_code == 200

    body = response.json()
    assert body["agent"] == agent_id
    assert body["message"].strip()
    assert any(block["type"] == expected_block for block in body["blocks"])
    # Every block must carry a type the renderer can dispatch on.
    assert all("type" in block for block in body["blocks"])


def test_analyst_kpis_reflect_real_snapshot_totals(client):
    body = client.post(
        "/api/agents/analyst/invoke", json={"prompt": "How is the account doing?"}
    ).json()

    kpis = body["raw"]["account_kpis"]
    per_campaign = body["raw"]["per_campaign"]
    # The headline spend must equal the sum of the rows it claims to summarize.
    assert kpis["total_spend_inr"] == pytest.approx(
        sum(c["spend_inr"] for c in per_campaign), rel=1e-6
    )


def test_media_buyer_shifts_stay_inside_policy_cap(client):
    body = client.post(
        "/api/agents/media_buyer/invoke", json={"prompt": "Optimize the budget"}
    ).json()

    for shift in body["raw"]["shifts"]:
        assert abs(shift["shift_percentage"]) <= 25.0

    policy = next(b for b in body["blocks"] if b["type"] == "policy_check")
    assert policy["verdict"] == "PASS"
    assert body["meta"]["requires_approval"] is True


def test_compliance_blocks_prohibited_claims(client):
    body = client.post(
        "/api/agents/compliance/invoke",
        json={"prompt": "Get guaranteed returns with zero risk on your investment"},
    ).json()

    assert body["raw"]["passed"] is False
    verdict = next(b for b in body["blocks"] if b["type"] == "policy_check")
    assert verdict["verdict"] in ("FLAG", "BLOCK")
    # Violations must be renderable by the table block: phrase + citation present.
    violations = next(b for b in body["blocks"] if b["type"] == "table")["rows"]
    assert violations and all(v["phrase"] and v["citation"] for v in violations)


def test_compliant_copy_passes(client):
    body = client.post(
        "/api/agents/compliance/invoke",
        json={
            "prompt": (
                "Start a SIP from Rs 500 a month. Mutual fund investments are subject to "
                "market risks. Read all scheme related documents carefully."
            )
        },
    ).json()
    assert body["raw"]["passed"] is True


def test_unknown_agent_is_rejected(client):
    response = client.post("/api/agents/wizard/invoke", json={"prompt": "hello"})
    assert response.status_code == 404
    assert "wizard" in response.json()["detail"]


def test_empty_prompt_is_rejected(client):
    response = client.post("/api/agents/analyst/invoke", json={"prompt": "   "})
    assert response.status_code == 400


def test_grounding_toggle_controls_citations(client):
    grounded = client.post(
        "/api/agents/analyst/invoke", json={"prompt": "Analyze", "grounded": True}
    ).json()
    ungrounded = client.post(
        "/api/agents/analyst/invoke", json={"prompt": "Analyze", "grounded": False}
    ).json()

    assert len(grounded["sources"]) > 0
    assert ungrounded["sources"] == []


# ----------------------------------------------------------------------
# Chat + conversations
# ----------------------------------------------------------------------


def test_chat_persists_both_turns_and_replays_them(client):
    result = client.post(
        "/api/chat", json={"prompt": "Analyze campaign performance", "mode": "analyst"}
    ).json()

    conversation_id = result["conversation_id"]
    assert result["user_message"]["role"] == "user"
    assert result["agent_message"]["agent"] == "analyst"
    assert result["agent_message"]["payload"]["blocks"]

    # Reopening replays the stored render payload without re-running the agent.
    conversation = client.get(f"/api/conversations/{conversation_id}").json()
    assert [m["role"] for m in conversation["messages"]] == ["user", "agent"]
    assert conversation["messages"][1]["payload"]["blocks"]
    # The conversation is titled from its opening prompt.
    assert conversation["title"].startswith("Analyze campaign performance")


def test_chat_continues_an_existing_conversation(client):
    first = client.post("/api/chat", json={"prompt": "First question", "mode": "analyst"}).json()
    conversation_id = first["conversation_id"]

    client.post(
        "/api/chat",
        json={
            "prompt": "Now propose budget shifts",
            "mode": "media_buyer",
            "conversation_id": conversation_id,
        },
    )

    conversation = client.get(f"/api/conversations/{conversation_id}").json()
    assert len(conversation["messages"]) == 4
    assert conversation["messages"][3]["agent"] == "media_buyer"


def test_chat_rejects_unknown_mode(client):
    response = client.post("/api/chat", json={"prompt": "hi", "mode": "telepathy"})
    assert response.status_code == 400


def test_conversation_pin_rename_and_delete(client):
    conversation_id = client.post(
        "/api/chat", json={"prompt": "Disposable thread", "mode": "analyst"}
    ).json()["conversation_id"]

    renamed = client.patch(
        f"/api/conversations/{conversation_id}", json={"title": "Renamed", "pinned": True}
    ).json()
    assert renamed["title"] == "Renamed"
    assert renamed["pinned"] is True

    # Pinned conversations sort ahead of unpinned ones.
    assert client.get("/api/conversations").json()[0]["id"] == conversation_id

    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 200
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404


def test_missing_conversation_is_404(client):
    assert client.get("/api/conversations/conv_nope").status_code == 404


# ----------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------


def test_report_generation_stores_a_retrievable_document(client):
    document = client.post(
        "/api/reports/generate", json={"title": "Q3 Review", "period_days": 30}
    ).json()

    assert document["title"] == "Q3 Review"
    assert document["account_kpis"]["total_spend_inr"] > 0
    assert document["campaigns"]
    assert document["budget_plan"]["shifts"] is not None

    fetched = client.get(f"/api/reports/{document['id']}").json()
    assert fetched == document
    assert any(r["id"] == document["id"] for r in client.get("/api/reports").json())


def test_report_markdown_export_contains_the_real_numbers(client):
    document = client.post("/api/reports/generate", json={"period_days": 30}).json()
    markdown = client.get(f"/api/reports/{document['id']}/markdown").text

    assert markdown.startswith("# ")
    assert "## Account performance" in markdown
    assert "## Campaign performance" in markdown
    assert f"{document['account_kpis']['blended_roas']}x" in markdown
    # Every campaign in the document appears in the export.
    for campaign in document["campaigns"]:
        assert campaign["campaign_name"] in markdown


def test_missing_report_is_404(client):
    assert client.get("/api/reports/rpt_nope").status_code == 404
    assert client.get("/api/reports/rpt_nope/markdown").status_code == 404


# ----------------------------------------------------------------------
# Dashboard + connections
# ----------------------------------------------------------------------


def test_dashboard_stats_are_computed_not_hardcoded(client):
    stats = client.get("/api/dashboard/stats").json()
    snapshot = client.get("/api/synthetic/current").json()

    assert stats["total_spend_inr"] == pytest.approx(snapshot["total_spend_inr"], rel=1e-6)
    assert stats["total_campaigns"] == snapshot["campaign_count"]
    assert stats["data_source_label"]


def test_connection_verify_reports_missing_credentials_honestly(client):
    result = client.post("/api/connections/verify").json()

    for platform in ("google_ads", "meta_ads"):
        assert result["platforms"][platform]["connected"] is False
        assert result["platforms"][platform]["reason"]
    # With nothing connected, the console must not claim live data.
    assert result["data_source"] == "synthetic"


# ----------------------------------------------------------------------
# File Attachment & Auto-Activation
# ----------------------------------------------------------------------


def test_agent_invoke_with_attached_csv_auto_activates_byod(client):
    from modules.ads.byod_importer import clear_active_byod_snapshot, get_active_byod_snapshot

    clear_active_byod_snapshot()

    csv_data = (
        "campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status\n"
        "cmp_custom_101,Custom Direct Alpha,google_ads,33000,90000,5000,250,3.9,132.0,5.56,ENABLED\n"
        "cmp_custom_102,Custom Direct Beta,meta_ads,22000,70000,3000,100,2.1,220.0,4.29,ENABLED\n"
    )

    resp = client.post(
        "/api/agents/analyst/invoke",
        json={
            "prompt": "Analyze my uploaded dataset",
            "file_content": csv_data,
            "filename": "custom_campaigns.csv",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent"] == "analyst"
    assert body["meta"]["data_source"] == "byod"

    # Verify active BYOD store was populated
    active_snap = get_active_byod_snapshot()
    assert active_snap is not None
    assert len(active_snap.campaigns) == 2
    assert active_snap.campaigns[0].campaign_name == "Custom Direct Alpha"

    # Analyst raw report reflects the 2 uploaded campaigns
    per_campaign = body["raw"]["per_campaign"]
    assert len(per_campaign) == 2
    assert per_campaign[0]["campaign_name"] == "Custom Direct Alpha"

    clear_active_byod_snapshot()


def test_agent_invoke_with_attached_json_auto_activates_byod(client):
    import json
    from modules.ads.byod_importer import clear_active_byod_snapshot, get_active_byod_snapshot

    clear_active_byod_snapshot()

    json_data = json.dumps([
        {
            "campaign_id": "cmp_json_direct_1",
            "campaign_name": "High Converting Search",
            "platform": "google_ads",
            "spend": 40000.0,
            "impressions": 100000,
            "clicks": 6000,
            "conversions": 300,
            "roas": 4.5,
            "cpa": 133.33,
            "ctr": 6.0,
            "status": "ENABLED",
        },
        {
            "campaign_id": "cmp_json_direct_2",
            "campaign_name": "Decayed Retargeting",
            "platform": "meta_ads",
            "spend": 20000.0,
            "impressions": 50000,
            "clicks": 2000,
            "conversions": 50,
            "roas": 1.2,
            "cpa": 400.0,
            "ctr": 4.0,
            "status": "ENABLED",
        },
    ])

    resp = client.post(
        "/api/agents/media_buyer/invoke",
        json={
            "prompt": "Reallocate budget for this imported data",
            "file_content": json_data,
            "filename": "metrics.json",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent"] == "media_buyer"
    assert body["meta"]["data_source"] == "byod"

    shifts = body["raw"]["shifts"]
    assert len(shifts) >= 2
    # Verify shifts are for the json dataset campaigns
    shift_ids = {s["campaign_id"] for s in shifts}
    assert "cmp_json_direct_1" in shift_ids
    assert "cmp_json_direct_2" in shift_ids

    clear_active_byod_snapshot()


def test_pipeline_run_with_attachment_auto_activates_byod(client):
    from modules.ads.byod_importer import clear_active_byod_snapshot, get_active_byod_snapshot

    clear_active_byod_snapshot()

    csv_data = (
        "campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status\n"
        "cmp_run_01,Pipeline Scale Alpha,google_ads,60000,150000,10000,500,4.0,120.0,6.67,ENABLED\n"
        "cmp_run_02,Pipeline Decay Beta,meta_ads,30000,80000,3000,80,1.0,375.0,3.75,ENABLED\n"
    )

    resp = client.post(
        "/api/runs",
        json={
            "objective": "Scale Alpha and reduce Beta",
            "file_content": csv_data,
            "filename": "pipeline_data.csv",
            "wait": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending_approval"
    proposal = body["proposal"]
    assert proposal["data_source"] == "byod"
    per_campaign = proposal["analyst_findings"]["per_campaign"]
    assert len(per_campaign) == 2
    assert per_campaign[0]["campaign_name"] == "Pipeline Scale Alpha"

    clear_active_byod_snapshot()


def test_chat_endpoint_with_attached_file(client):
    from modules.ads.byod_importer import clear_active_byod_snapshot

    clear_active_byod_snapshot()

    csv_data = (
        "campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status\n"
        "cmp_chat_01,Chat Imported Search,google_ads,45000,120000,8000,400,3.5,112.5,6.67,ENABLED\n"
    )

    resp = client.post(
        "/api/chat",
        json={
            "prompt": "Diagnose my uploaded campaigns",
            "mode": "analyst",
            "file_content": csv_data,
            "filename": "chat_upload.csv",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_message"]["agent"] == "analyst"
    assert data["agent_message"]["payload"]["meta"]["data_source"] == "byod"

    clear_active_byod_snapshot()


def test_agent_invoke_with_multisheet_unicode_excel_data_url(client):
    import base64
    import io
    import openpyxl
    from modules.ads.byod_importer import clear_active_byod_snapshot, get_active_byod_snapshot

    clear_active_byod_snapshot()

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Google_Ads"
    ws1.append(["campaign_id", "campaign_name", "platform", "spend_inr", "impressions", "clicks", "conversions", "roas", "cpa_inr", "ctr", "status"])
    ws1.append(["cmp_u1", "🎯 दिवाली स्पेशल Growth 2026", "google_ads", 50000, 100000, 5000, 250, 4.2, 200, 5.0, "ENABLED"])

    ws2 = wb.create_sheet(title="Meta_Ads")
    ws2.append(["campaign_id", "campaign_name", "platform", "spend_inr", "impressions", "clicks", "conversions", "roas", "cpa_inr", "ctr", "status"])
    ws2.append(["cmp_u2", "🚀 Tokyo Scale 東京", "meta_ads", 30000, 80000, 4000, 150, 3.1, 200, 5.0, "ENABLED"])

    buf = io.BytesIO()
    wb.save(buf)
    b64_content = "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    resp = client.post(
        "/api/agents/analyst/invoke",
        json={
            "prompt": "Analyze our festive campaigns",
            "file_content": b64_content,
            "filename": "festive_growth.xlsx",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent"] == "analyst"
    assert body["meta"]["data_source"] == "byod"

    active_snap = get_active_byod_snapshot()
    assert active_snap is not None
    assert len(active_snap.campaigns) == 2
    names = {c.campaign_name for c in active_snap.campaigns}
    assert "🎯 दिवाली स्पेशल Growth 2026" in names
    assert "🚀 Tokyo Scale 東京" in names

    clear_active_byod_snapshot()


def test_agent_invoke_with_corrupted_dataset_returns_400(client):
    from modules.ads.byod_importer import clear_active_byod_snapshot

    clear_active_byod_snapshot()

    # Invalid columns (missing spend, roas, clicks, conversions)
    bad_csv = "col1,col2,col3\nval1,val2,val3\n"

    resp = client.post(
        "/api/agents/analyst/invoke",
        json={
            "prompt": "Analyze this file",
            "file_content": bad_csv,
            "filename": "invalid.csv",
        },
    )
    assert resp.status_code == 400
    assert "Failed to process attached dataset" in resp.json()["detail"]

    # Corrupt base64 string
    resp_b64 = client.post(
        "/api/agents/analyst/invoke",
        json={
            "prompt": "Analyze this file",
            "file_content": "data:text/csv;base64,!!!NotBase64!!!",
            "filename": "broken.csv",
        },
    )
    assert resp_b64.status_code == 400
    assert "Failed to process attached dataset" in resp_b64.json()["detail"]


def test_pipeline_run_with_corrupted_dataset_returns_400(client):
    resp = client.post(
        "/api/runs",
        json={
            "objective": "Run with broken data",
            "file_content": "not,valid,headers\n1,2,3",
            "filename": "bad.csv",
        },
    )
    assert resp.status_code == 400
    assert "Failed to process attached dataset" in resp.json()["detail"]


def test_multi_agent_pipeline_with_edge_case_aliases_and_decimal_ctr(client):
    from modules.ads.byod_importer import clear_active_byod_snapshot, get_active_byod_snapshot

    clear_active_byod_snapshot()

    # Headers with extreme aliases: campaign_title, ad_network, ad_spend, conv_value, clicks_count, conversions_count, click_through_rate, delivery_status
    csv_edge = (
        "id,campaign_title,ad_network,ad_spend,conv_value,clicks_count,conversions_count,click_through_rate,delivery_status\n"
        "cmp_edge_1,Festive Search Max,google_ads,80000,320000,12000,600,0.0450,ACTIVE\n"
        "cmp_edge_2,Brand Video Scale,meta_ads,40000,80000,5000,160,0.0250,ACTIVE\n"
    )

    resp = client.post(
        "/api/runs",
        json={
            "objective": "Scale Festive Search and reallocate Video spend",
            "file_content": csv_edge,
            "filename": "edge_case_aliases.csv",
            "wait": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending_approval"
    proposal = body["proposal"]
    assert proposal["data_source"] == "byod"

    # 1. Analyst findings
    analyst_findings = proposal["analyst_findings"]
    assert analyst_findings["account_kpis"]["total_spend_inr"] == 120000.0
    assert len(analyst_findings["per_campaign"]) == 2
    c1 = next(c for c in analyst_findings["per_campaign"] if c["campaign_name"] == "Festive Search Max")
    assert c1["roas"] == 4.0  # 320000 / 80000
    assert c1["ctr"] == 4.5   # 0.0450 auto-scaled to 4.5%

    # 2. Creative package
    assert proposal["creative_package"]["brief"]["target_audience"]
    assert proposal["creative_package"]["creative"]["headline"]

    # 3. Compliance verdict
    assert proposal["compliance_verdict"]["status"].upper() in ("PASS", "FLAG", "BLOCK")

    # 4. Budget optimizer
    assert len(proposal["budget_shifts"]) == 2
    assert proposal["total_budget_current_inr"] == 4000.0

    # 5. Subsequent direct agent invocations without attachment use the active BYOD dataset
    analyst_resp = client.post(
        "/api/agents/analyst/invoke",
        json={"prompt": "How is Festive Search performing?"},
    )
    assert analyst_resp.status_code == 200
    assert analyst_resp.json()["meta"]["data_source"] == "byod"
    assert analyst_resp.json()["raw"]["account_kpis"]["total_spend_inr"] == 120000.0

    buyer_resp = client.post(
        "/api/agents/media_buyer/invoke",
        json={"prompt": "Recommend budget shifts for these campaigns"},
    )
    assert buyer_resp.status_code == 200
    assert buyer_resp.json()["meta"]["data_source"] == "byod"
    assert len(buyer_resp.json()["raw"]["shifts"]) == 2

    clear_active_byod_snapshot()



