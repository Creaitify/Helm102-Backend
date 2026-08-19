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
