"""Tests for MureoConnector, Connector Protocol adherence, and the analyst."""

from modules.ads.analyst import AdOpsAnalyst
from modules.ads.connector import Connector, MureoConnector
from modules.ads.contracts import BudgetShift, CampaignDraft, CreativeVariant, Platform
from services.api.auth.secret_store import HelmSecretStore


def _unconnected() -> MureoConnector:
    return MureoConnector(secret_store=HelmSecretStore(memory_only=True))


def test_connector_protocol_conformance():
    connector = _unconnected()
    assert isinstance(connector, Connector)


def test_fetch_campaigns_returns_snapshot():
    connector = _unconnected()
    snapshot = connector.fetch_campaigns()
    assert len(snapshot.campaigns) > 0
    assert snapshot.total_spend_inr > 0
    assert snapshot.blended_roas > 0


def test_unconnected_snapshot_is_labelled_synthetic_never_live():
    """Without platform credentials the data must be labelled synthetic."""
    snapshot = _unconnected().fetch_campaigns()
    assert snapshot.source == "synthetic"


def test_fetch_history_returns_current_and_prior_periods():
    history = _unconnected().fetch_history(lookback_days=30)
    labels = [h.label for h in history]
    assert labels == ["current", "prior"]
    assert all(h.source == "synthetic" for h in history)
    assert all(len(h.campaigns) > 0 for h in history)


def test_live_budget_write_without_connection_fails_honestly():
    """Live (non-dry-run) writes must never fabricate success."""
    shift = BudgetShift(
        campaign_id="cmp_01",
        platform=Platform.META_ADS,
        current_daily_budget_inr=1000.0,
        proposed_daily_budget_inr=1200.0,
        shift_percentage=20.0,
        rationale="Scale winning ad set",
    )
    res = _unconnected().apply_budget(shift, dry_run=False)
    assert res.success is False
    assert res.error
    assert res.response_received["status"] != "APPLIED"


def test_live_campaign_create_without_connection_fails_honestly():
    draft = CampaignDraft(
        name="Test Draft",
        platform=Platform.META_ADS,
        objective="OUTCOME_TRAFFIC",
        daily_budget_inr=500.0,
        rationale="test",
    )
    res = _unconnected().create_campaign(draft, dry_run=False)
    assert res.success is False
    assert res.error


def test_create_campaign_dry_run_previews_exact_payload():
    draft = CampaignDraft(
        name="Finnovate Scale Test",
        platform=Platform.META_ADS,
        objective="OUTCOME_TRAFFIC",
        daily_budget_inr=750.0,
        rationale="clone winner",
    )
    res = _unconnected().create_campaign(draft, dry_run=True)
    assert res.success and res.dry_run
    assert res.payload_sent["name"] == "Finnovate Scale Test"
    assert res.payload_sent["status"] == "PAUSED"


def test_analyst_findings_and_drafts():
    from services.api.db.synthetic_sqlite import generate_synthetic_scenario
    generate_synthetic_scenario("growth_and_fatigue", days=60)

    connector = _unconnected()
    snapshot = connector.fetch_campaigns()
    history = connector.fetch_history()
    findings = AdOpsAnalyst().analyze(snapshot, history)

    assert findings["data_source"] == "synthetic"
    assert findings["per_campaign"], "per-campaign table missing"
    # Ranked best-first by composite score
    scores = [c["score"] for c in findings["per_campaign"]]
    assert scores == sorted(scores, reverse=True)
    # Synthetic history contains a deliberately decaying campaign
    assert any("decaying" in d for d in findings["decay_signals"])
    assert findings["recommendations"], "budget direction recommendations missing"
    assert len(findings["campaign_drafts"]) == 2
    assert all(d["status"] == "PAUSED" for d in findings["campaign_drafts"])


def test_apply_budget_dry_run():
    connector = _unconnected()
    shift = BudgetShift(
        campaign_id="cmp_01",
        platform=Platform.META_ADS,
        current_daily_budget_inr=1000.0,
        proposed_daily_budget_inr=1200.0,
        shift_percentage=20.0,
        rationale="Scale winning ad set",
    )
    res = connector.apply_budget(shift, dry_run=True)
    assert res.success
    assert res.dry_run
    assert res.response_received["status"] == "DRY_RUN_VALIDATED"


def test_deploy_creative_dry_run():
    connector = _unconnected()
    variant = CreativeVariant(
        campaign_id="cmp_01",
        platform=Platform.META_ADS,
        headline="Start SIP with Finnovate",
        primary_text="Disciplined long term growth.",
        call_to_action="Install App",
    )
    res = connector.deploy_creative(variant, dry_run=True)
    assert res.success
    assert res.dry_run
    assert res.response_received["status"] == "DRY_RUN_VALIDATED"
