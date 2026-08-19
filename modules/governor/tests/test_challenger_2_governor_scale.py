"""Challenger 2 Empirical Adversarial Stress & Load Tests for Governor & Ad-Ops at Scale.

Validates:
1. Ingestion of the full 320-row multi-channel dataset (sample_multichannel_campaigns.csv)
2. Complete Governor 6-hop Star Relay execution on 320 campaigns (Hops 0-6, checkpointer persistence, human approval gate, execution engine)
3. Performance analytics precision on 320 campaigns (blended ROAS, composite scoring distribution, monotonicity, channel breakdown)
4. Multi-platform anomaly and fatigue decay detection across TikTok Ads, Meta Ads, and Google Ads
5. Policy-bounded Budget Optimizer reallocation on 320 campaigns (±25% bounds, total conservation proof, platform distribution)
6. Adversarial multi-shift matrix with extreme variations (+300%, -90%, NaN, duplicates, non-existent campaigns)
"""

from __future__ import annotations

import csv
import io
import math
import sqlite3
from pathlib import Path
from typing import Any
import pytest

from modules.ads.analyst import AdOpsAnalyst
from modules.ads.byod_importer import (
    clear_active_byod_snapshot,
    get_active_byod_snapshot,
    has_active_byod_snapshot,
    import_byod_file,
    parse_csv,
    set_active_byod_snapshot,
)
from modules.ads.contracts import (
    CampaignSnapshot,
    HistoryPeriod,
    MetricRow,
    Platform,
)
from modules.audit.trail import AuditTrail
from modules.budget.optimizer import BudgetOptimizer, apply_budget_policy
from modules.compliance.verifier import SEBIComplianceVerifier
from modules.creative.worker import CreativeWorker
from modules.execution.executor import ExecutionEngine
from modules.governor.checkpoint import GovernorCheckpointer
from modules.governor.envelope import EnvelopeStatus, HandoffEnvelope
from modules.governor.orchestrator import GovernorOrchestrator
from services.api.gateway.service import GatewayService


CSV_DATA_PATH = Path("services/api/data/sample_multichannel_campaigns.csv")


# ===========================================================================
# 1. 320-Row Multi-Channel Ingestion & Metric Derivation Validation
# ===========================================================================

def test_ingest_320_row_sample_multichannel_csv_structure_and_metrics():
    """Verify 320-row sample_multichannel_campaigns.csv parses cleanly with 100% fidelity."""
    assert CSV_DATA_PATH.exists(), f"Missing dataset file at {CSV_DATA_PATH}"
    content = CSV_DATA_PATH.read_text(encoding="utf-8")
    
    snapshot = parse_csv(content)
    assert len(snapshot.campaigns) == 320, f"Expected 320 campaigns, found {len(snapshot.campaigns)}"
    assert snapshot.source == "byod"
    assert snapshot.total_spend_inr > 0
    assert snapshot.blended_roas > 0

    # Verify platform distribution includes Google Ads, Meta Ads, and TikTok Ads
    platforms_present = {c.platform for c in snapshot.campaigns}
    assert Platform.GOOGLE_ADS in platforms_present, "Google Ads missing from dataset"
    assert Platform.META_ADS in platforms_present, "Meta Ads missing from dataset"
    assert Platform.TIKTOK_ADS in platforms_present, "TikTok Ads missing from dataset"

    # Count campaigns per platform
    counts = {}
    for c in snapshot.campaigns:
        counts[c.platform] = counts.get(c.platform, 0) + 1
    
    # Each platform must have substantial representation
    assert counts[Platform.GOOGLE_ADS] >= 50
    assert counts[Platform.META_ADS] >= 50
    assert counts[Platform.TIKTOK_ADS] >= 50

    # Metric validation for every single campaign
    for idx, c in enumerate(snapshot.campaigns):
        assert c.spend_inr > 0, f"Row {idx} has non-positive spend: {c.spend_inr}"
        assert c.impressions > 0, f"Row {idx} has non-positive impressions: {c.impressions}"
        assert c.clicks > 0, f"Row {idx} has non-positive clicks: {c.clicks}"
        assert c.conversions >= 0, f"Row {idx} has negative conversions: {c.conversions}"
        assert c.roas >= 0, f"Row {idx} has negative ROAS: {c.roas}"
        assert c.cpa_inr >= 0, f"Row {idx} has negative CPA: {c.cpa_inr}"
        # CTR must be percentage-scaled (e.g. 3.53 not 0.0353)
        assert 0.0 < c.ctr <= 100.0, f"Row {idx} has invalid CTR scaling: {c.ctr}"
        # Campaign names must be synthesized with descriptive platform tags
        assert c.campaign_name.startswith("["), f"Row {idx} name not synthesized: {c.campaign_name}"
        assert c.campaign_id.startswith("cmp_"), f"Row {idx} ID not prefixed: {c.campaign_id}"


# ===========================================================================
# 2. Governor 6-Hop Complete Star Relay on 320 Campaigns
# ===========================================================================

@pytest.mark.asyncio
async def test_governor_complete_6hop_star_relay_on_320_campaigns(tmp_path: Path):
    """Execute complete 6-hop Governor run on 320 multi-channel campaigns."""
    # 1. Load and activate 320-row dataset
    content = CSV_DATA_PATH.read_text(encoding="utf-8")
    snapshot = parse_csv(content)
    set_active_byod_snapshot(snapshot)

    # 2. Set up isolated checkpoint and audit databases
    chk_path = tmp_path / "scale_checkpoints.sqlite"
    audit_path = tmp_path / "scale_audit.sqlite"
    checkpointer = GovernorCheckpointer(db_path=chk_path)
    audit_trail = AuditTrail(db_path=audit_path)
    gateway = GatewayService(replay_mode=True)

    orchestrator = GovernorOrchestrator(
        gateway=gateway,
        checkpointer=checkpointer,
        audit_trail=audit_trail,
        dry_run=True,
    )

    # 3. Start run up to Human Approval Gate (Hops 0 -> 5)
    objective = "Optimize spend across 320 multi-channel campaigns and scale high-performing angles"
    run_state = await orchestrator.start_run(objective=objective)

    assert run_state["status"] == "pending_approval"
    assert run_state["current_agent"] == "HumanApprover"
    run_id = run_state["run_id"]

    # Verify all 6 initial envelopes (Hop 0 through Hop 5)
    hops = run_state["hops"]
    assert len(hops) == 6
    assert hops[0]["action"] == "INGEST_OBJECTIVE"
    assert hops[0]["status"] == "success"

    assert hops[1]["action"] == "FETCH_AND_ANALYZE_CAMPAIGNS"
    assert hops[1]["payload"]["campaign_count"] == 320
    assert hops[1]["payload"]["source"] == "byod"
    assert hops[1]["payload"]["blended_roas"] == snapshot.blended_roas

    assert hops[2]["action"] == "GENERATE_CREATIVE_PACKAGE"
    assert "brief" in hops[2]["payload"]
    assert "script" in hops[2]["payload"]
    assert "creative" in hops[2]["payload"]
    assert "captions" in hops[2]["payload"]

    assert hops[3]["action"] == "VERIFY_SEBI_REGULATORY"
    assert hops[3]["payload"]["passed"] is True

    assert hops[4]["action"] == "PROPOSE_BUDGET_REALLOCATION"
    assert len(hops[4]["payload"]["shifts"]) > 0
    assert hops[4]["payload"]["is_conserved"] is True

    assert hops[5]["action"] == "SUBMIT_PROPOSAL_FOR_APPROVAL"
    assert hops[5]["payload"]["data_source"] == "byod"

    # Verify checkpoint persistence in SQLite
    saved_state = checkpointer.load_checkpoint(run_id)
    assert saved_state is not None
    assert saved_state["status"] == "pending_approval"
    assert len(saved_state["hops"]) == 6

    # 4. Resolve Approval (Hop 6 Execution)
    approval_result = orchestrator.resolve_approval(
        run_id=run_id,
        decision="approved",
        decision_notes="Approved all 320 campaign reallocations.",
    )

    assert approval_result["status"] == "completed"
    assert approval_result["decision"] == "approved"
    assert approval_result["current_agent"] == "ExecutionEngine"
    assert len(approval_result["execution_results"]) > 0

    # Verify execution results have dry-run receipts
    for res in approval_result["execution_results"]:
        assert res["success"] is True
        assert res["dry_run"] is True
        assert res["response"]["status"] == "DRY_RUN_VALIDATED"

    # Verify audit trail entries
    trail = audit_trail.get_trail(run_id)
    assert len(trail) >= 7  # 6 hops + 1 execution envelope


@pytest.mark.asyncio
async def test_governor_rejection_flow_on_320_campaigns(tmp_path: Path):
    """Verify Governor cleanly halts execution when human rejects proposal."""
    content = CSV_DATA_PATH.read_text(encoding="utf-8")
    snapshot = parse_csv(content)
    set_active_byod_snapshot(snapshot)

    checkpointer = GovernorCheckpointer(db_path=tmp_path / "reject_checkpoints.sqlite")
    audit_trail = AuditTrail(db_path=tmp_path / "reject_audit.sqlite")
    orchestrator = GovernorOrchestrator(
        gateway=GatewayService(replay_mode=True),
        checkpointer=checkpointer,
        audit_trail=audit_trail,
        dry_run=True,
    )

    run_state = await orchestrator.start_run(objective="Scale all channels")
    run_id = run_state["run_id"]

    reject_result = orchestrator.resolve_approval(
        run_id=run_id,
        decision="rejected",
        decision_notes="Operator declined budget shift proposal.",
    )

    assert reject_result["status"] == "rejected"
    assert reject_result["decision"] == "rejected"
    assert reject_result["execution_results"] == []

    # Attempting to re-resolve already rejected run must raise ValueError
    with pytest.raises(ValueError, match="already in state: rejected"):
        orchestrator.resolve_approval(run_id=run_id, decision="approved")


# ===========================================================================
# 3. Ad-Ops Performance Analytics & Metric Distribution on 320 Campaigns
# ===========================================================================

def test_ad_ops_analyst_analytics_320_campaigns_distribution():
    """Verify Ad-Ops Analyst performance analytics calculations on all 320 campaigns."""
    content = CSV_DATA_PATH.read_text(encoding="utf-8")
    snapshot = parse_csv(content)
    
    analyst = AdOpsAnalyst()
    findings = analyst.analyze(snapshot)

    # 1. Verify Account KPIs mathematical exactness
    kpis = findings["account_kpis"]
    total_spend = sum(c.spend_inr for c in snapshot.campaigns)
    total_clicks = sum(c.clicks for c in snapshot.campaigns)
    total_impressions = sum(c.impressions for c in snapshot.campaigns)
    total_conversions = sum(c.conversions for c in snapshot.campaigns)
    expected_blended_roas = round(sum(c.roas * c.spend_inr for c in snapshot.campaigns) / total_spend, 2)
    expected_blended_cpa = round(total_spend / total_conversions, 2)

    assert math.isclose(kpis["total_spend_inr"], total_spend, rel_tol=1e-5)
    assert kpis["total_clicks"] == total_clicks
    assert kpis["total_impressions"] == total_impressions
    assert kpis["total_conversions"] == total_conversions
    assert math.isclose(kpis["blended_roas"], expected_blended_roas, abs_tol=0.02)
    assert math.isclose(kpis["blended_cpa_inr"], expected_blended_cpa, abs_tol=0.02)

    # 2. Verify Composite Scoring Distribution
    per_camp = findings["per_campaign"]
    assert len(per_camp) == 320

    scores = [r["score"] for r in per_camp]
    # All scores must be in bounded [0, 100] range
    assert all(0 <= s <= 100 for s in scores)
    
    # Monotonicity check: must be strictly sorted in descending order
    assert scores == sorted(scores, reverse=True), "per_campaign is not sorted descending by score"

    # Status tag distribution
    winners = [r for r in per_camp if r["status_tag"] == "WINNER"]
    stable = [r for r in per_camp if r["status_tag"] == "STABLE"]
    fatigued = [r for r in per_camp if r["status_tag"] == "FATIGUED"]

    assert len(winners) > 0, "Expected winners in 320 campaign dataset"
    assert len(fatigued) > 0, "Expected fatigued campaigns in 320 campaign dataset"
    assert len(winners) + len(stable) + len(fatigued) == 320

    # 3. Dynamic Channel Breakdown Verification
    channels = findings["channel_breakdown"]
    assert "google_ads" in channels
    assert "meta_ads" in channels
    assert "tiktok_ads" in channels

    # Sum of platform spends must match total account spend
    platform_spend_sum = sum(ch["spend_inr"] for ch in channels.values())
    assert math.isclose(platform_spend_sum, total_spend, rel_tol=1e-5)

    # Verify per-platform counts sum to 320
    platform_count_sum = sum(ch["campaign_count"] for ch in channels.values())
    assert platform_count_sum == 320


# ===========================================================================
# 4. Anomaly & Fatigue Decay Detection across Platforms
# ===========================================================================

def test_decay_detection_across_tiktok_meta_google_ads():
    """Verify decay detection correctly identifies CTR drops, CPA surges, and ROAS decay."""
    analyst = AdOpsAnalyst()

    # Create current and prior snapshots with targeted decay signals
    current_rows = [
        # TikTok decaying: CTR drop 6.0% -> 2.0% (66% drop >= 25%)
        MetricRow(
            campaign_id="cmp_tt_decay",
            campaign_name="TikTok Retargeting Video",
            platform=Platform.TIKTOK_ADS,
            spend_inr=50000.0,
            impressions=100000,
            clicks=2000,
            conversions=100,
            roas=2.5,
            cpa_inr=500.0,
            ctr=2.0,
        ),
        # Meta decaying: CPA surge 200 -> 350 (75% rise >= 30%)
        MetricRow(
            campaign_id="cmp_meta_decay",
            campaign_name="Meta Lookalike Core",
            platform=Platform.META_ADS,
            spend_inr=70000.0,
            impressions=150000,
            clicks=4500,
            conversions=200,
            roas=2.0,
            cpa_inr=350.0,
            ctr=3.0,
        ),
        # Google decaying: ROAS drop 4.0 -> 2.2 (45% drop >= 25%)
        MetricRow(
            campaign_id="cmp_google_decay",
            campaign_name="Google High Intent Search",
            platform=Platform.GOOGLE_ADS,
            spend_inr=60000.0,
            impressions=80000,
            clicks=3200,
            conversions=150,
            roas=2.2,
            cpa_inr=400.0,
            ctr=4.0,
        ),
        # Control stable campaign
        MetricRow(
            campaign_id="cmp_control_stable",
            campaign_name="Stable Winner Brand Search",
            platform=Platform.GOOGLE_ADS,
            spend_inr=40000.0,
            impressions=60000,
            clicks=3000,
            conversions=200,
            roas=5.0,
            cpa_inr=200.0,
            ctr=5.0,
        ),
    ]

    prior_rows = [
        MetricRow(
            campaign_id="cmp_tt_decay",
            campaign_name="TikTok Retargeting Video",
            platform=Platform.TIKTOK_ADS,
            spend_inr=48000.0,
            impressions=80000,
            clicks=4800,
            conversions=180,
            roas=3.8,
            cpa_inr=266.67,
            ctr=6.0,  # Prior CTR 6.0% vs Current 2.0%
        ),
        MetricRow(
            campaign_id="cmp_meta_decay",
            campaign_name="Meta Lookalike Core",
            platform=Platform.META_ADS,
            spend_inr=60000.0,
            impressions=120000,
            clicks=4000,
            conversions=300,
            roas=3.5,
            cpa_inr=200.0,  # Prior CPA 200 vs Current 350
            ctr=3.33,
        ),
        MetricRow(
            campaign_id="cmp_google_decay",
            campaign_name="Google High Intent Search",
            platform=Platform.GOOGLE_ADS,
            spend_inr=60000.0,
            impressions=80000,
            clicks=3200,
            conversions=240,
            roas=4.0,  # Prior ROAS 4.0 vs Current 2.2
            cpa_inr=250.0,
            ctr=4.0,
        ),
        MetricRow(
            campaign_id="cmp_control_stable",
            campaign_name="Stable Winner Brand Search",
            platform=Platform.GOOGLE_ADS,
            spend_inr=38000.0,
            impressions=58000,
            clicks=2900,
            conversions=190,
            roas=4.9,
            cpa_inr=200.0,
            ctr=5.0,
        ),
    ]

    current_snap = CampaignSnapshot(
        account_ids=["acc_decay_test"],
        platform=Platform.BYOD,
        campaigns=current_rows,
        total_spend_inr=sum(r.spend_inr for r in current_rows),
        blended_roas=round(sum(r.roas * r.spend_inr for r in current_rows) / sum(r.spend_inr for r in current_rows), 2),
        source="byod",
    )

    history = [
        HistoryPeriod(label="current", date_start="2026-07-01", date_end="2026-07-30", campaigns=current_rows, source="byod"),
        HistoryPeriod(label="prior", date_start="2026-06-01", date_end="2026-06-30", campaigns=prior_rows, source="byod"),
    ]

    findings = analyst.analyze(current_snap, history=history)
    signals = findings["decay_signals"]
    signals_text = " ".join(signals)

    # Verify all 3 platform decay anomalies were detected
    assert any("TikTok Retargeting Video" in s and "CTR fell" in s for s in signals), f"Missing TikTok CTR decay in {signals}"
    assert any("Meta Lookalike Core" in s and "CPA rose" in s for s in signals), f"Missing Meta CPA surge in {signals}"
    assert any("Google High Intent Search" in s and "ROAS fell" in s for s in signals), f"Missing Google ROAS decay in {signals}"

    # Stable control campaign must not be flagged
    assert "Stable Winner Brand Search is decaying" not in signals_text


# ===========================================================================
# 5. Budget Optimizer Reallocation, Bounds & Conservation Proof
# ===========================================================================

def test_budget_optimizer_320_campaigns_policy_bounds_and_conservation():
    """Verify Budget Optimizer obeys strict ±25% bounds and exact conservation on 320 campaigns."""
    content = CSV_DATA_PATH.read_text(encoding="utf-8")
    snapshot = parse_csv(content)
    
    optimizer = BudgetOptimizer()
    result = optimizer.optimize(snapshot)

    assert result.is_conserved is True
    assert result.total_proposed_inr <= result.total_current_inr + 0.01

    # Verify every shift is within ±25%
    for s in result.shifts:
        assert -25.01 <= s.shift_percentage <= 25.01, f"Shift exceeds 25% bound: {s.shift_percentage}%"
        low = s.current_daily_budget_inr * 0.75 - 0.01
        high = s.current_daily_budget_inr * 1.25 + 0.01
        assert low <= s.proposed_daily_budget_inr <= high, f"Budget out of bounds: {s}"
        assert s.platform in (Platform.GOOGLE_ADS, Platform.META_ADS, Platform.TIKTOK_ADS, Platform.LINKEDIN_ADS, Platform.BYOD)


def test_budget_optimizer_adversarial_stress_large_multi_shift_matrix():
    """Adversarial stress-test: apply_budget_policy with 50+ extreme, invalid, and out-of-bound shifts."""
    campaign_budgets = {f"cmp_{i}": 10000.0 for i in range(1, 51)}
    platform_map = {f"cmp_{i}": Platform.TIKTOK_ADS if i % 3 == 0 else Platform.GOOGLE_ADS if i % 3 == 1 else Platform.META_ADS for i in range(1, 51)}

    raw_shifts = []
    # 1. Extreme scaling attempts (+300%, +100%)
    for i in range(1, 10):
        raw_shifts.append({
            "campaign_id": f"cmp_{i}",
            "proposed_budget": 40000.0,  # +300% -> must clamp to 12,500 (+25%)
            "reason": "Aggressive scale",
        })
    # 2. Extreme reduction attempts (-90%)
    for i in range(10, 20):
        raw_shifts.append({
            "campaign_id": f"cmp_{i}",
            "proposed_budget": 1000.0,  # -90% -> must clamp to 7,500 (-25%)
            "reason": "Aggressive cut",
        })
    # 3. Invalid inputs: negative, zero, NaN, duplicate IDs, non-existent IDs
    raw_shifts.append({"campaign_id": "cmp_21", "proposed_budget": -500.0, "reason": "negative budget"})
    raw_shifts.append({"campaign_id": "cmp_22", "proposed_budget": 0.0, "reason": "zero budget"})
    raw_shifts.append({"campaign_id": "cmp_23", "proposed_budget": float("nan"), "reason": "nan budget"})
    raw_shifts.append({"campaign_id": "cmp_non_existent", "proposed_budget": 12000.0, "reason": "missing campaign"})
    raw_shifts.append({"campaign_id": "cmp_1", "proposed_budget": 11000.0, "reason": "duplicate cmp_1"})

    policy_result = apply_budget_policy(campaign_budgets, raw_shifts, platform_map)

    # 1. Total conservation must hold
    assert policy_result.is_conserved is True
    assert policy_result.total_proposed_inr <= policy_result.total_current_inr + 0.01

    # 2. All accepted shifts must obey ±25%
    for s in policy_result.shifts:
        assert s.shift_percentage <= 25.01
        assert s.shift_percentage >= -25.01
        assert s.proposed_daily_budget_inr <= 12500.01
        assert s.proposed_daily_budget_inr >= 7499.99

    # 3. Verify invalid inputs were dropped
    shifted_ids = {s.campaign_id for s in policy_result.shifts}
    assert "cmp_21" not in shifted_ids
    assert "cmp_22" not in shifted_ids
    assert "cmp_23" not in shifted_ids
    assert "cmp_non_existent" not in shifted_ids

    # 4. Total current vs proposed across the entire test set
    assert policy_result.total_proposed_inr <= policy_result.total_current_inr
