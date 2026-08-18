"""Empirical Adversarial Stress Tests for Budget Optimizer.

Tests extreme proposed allocations (+500%, -99%), negative budgets, 0 budgets,
non-numeric / boolean values, ±25% clamps, and budget conservation enforcement.
"""

import pytest
from modules.ads.contracts import CampaignSnapshot, MetricRow, Platform
from modules.budget.optimizer import BudgetOptimizer, apply_budget_policy


class TestBudgetOptimizerAdversarial:
    """Stress testing Budget Policy Engine and Optimizer with extreme and edge-case inputs."""

    def test_extreme_positive_increase_clamp_to_25_pct(self):
        """Verify +500% increase is clamped to exactly +25%."""
        budgets_with_offset = {"c_scale": 1000.0, "c_reduce": 5000.0}
        raw_shifts_with_offset = [
            {"campaign_id": "c_scale", "proposed_budget": 6000.0, "reason": "scale x6"},  # +500% -> clamp to 1250
            {"campaign_id": "c_reduce", "proposed_budget": 4500.0, "reason": "reduce spend"},  # -500 INR
        ]
        res = apply_budget_policy(budgets_with_offset, raw_shifts_with_offset)
        
        c_scale_shift = next((s for s in res.shifts if s.campaign_id == "c_scale"), None)
        assert c_scale_shift is not None
        assert c_scale_shift.proposed_daily_budget_inr == 1250.0
        assert c_scale_shift.shift_percentage == 25.0
        assert any("Clamped c_scale to +/-25%: 6000 -> 1250 INR" in n for n in res.notes)
        assert res.is_conserved

    def test_extreme_reduction_clamp_to_minus_25_pct(self):
        """Verify -90% decrease is clamped to exactly -25%."""
        budgets = {"c_loser": 2000.0, "c_winner": 2000.0}
        raw_shifts = [
            {"campaign_id": "c_loser", "proposed_budget": 200.0, "reason": "slash spend"},  # -90% -> clamp to 1500 (-25%)
            {"campaign_id": "c_winner", "proposed_budget": 2500.0, "reason": "boost winner"},  # +500 INR (+25%)
        ]
        res = apply_budget_policy(budgets, raw_shifts)
        c_loser_shift = next((s for s in res.shifts if s.campaign_id == "c_loser"), None)
        assert c_loser_shift is not None
        assert c_loser_shift.proposed_daily_budget_inr == 1500.0
        assert c_loser_shift.shift_percentage == -25.0
        assert any("Clamped c_loser to +/-25%: 200 -> 1500 INR" in n for n in res.notes)
        assert res.is_conserved

    def test_negative_and_zero_budgets_rejected(self):
        """Verify negative, zero, and non-positive numbers are safely dropped."""
        budgets = {"c1": 1000.0, "c2": 2000.0}
        raw_shifts = [
            {"campaign_id": "c1", "proposed_budget": -500.0, "reason": "negative budget attack"},
            {"campaign_id": "c2", "proposed_budget": 0.0, "reason": "zero budget attack"},
            {"campaign_id": "c2", "proposed_budget": -0.0001, "reason": "tiny negative"},
        ]
        res = apply_budget_policy(budgets, raw_shifts)
        assert len(res.shifts) == 0
        assert any("invalid non-positive budget" in n for n in res.notes)

    def test_non_numeric_and_boolean_budgets(self):
        """Verify boolean, string, list, and dict types are rejected safely."""
        budgets = {"c1": 1000.0, "c2": 2000.0}
        raw_shifts = [
            {"campaign_id": "c1", "proposed_budget": True, "reason": "boolean injection"},
            {"campaign_id": "c1", "proposed_budget": "5000", "reason": "string number"},
            {"campaign_id": "c2", "proposed_budget": None, "reason": "null"},
            {"campaign_id": "c2", "proposed_budget": [1000], "reason": "list"},
            {"campaign_id": "c2", "proposed_budget": {"val": 1000}, "reason": "dict"},
        ]
        res = apply_budget_policy(budgets, raw_shifts)
        assert len(res.shifts) == 0
        assert len(res.notes) >= 2

    def test_duplicate_and_unknown_campaigns(self):
        """Verify duplicate shifts in same payload are deduplicated and unknown campaigns are dropped."""
        budgets = {"c1": 1000.0, "c2": 2000.0}
        raw_shifts = [
            {"campaign_id": "c1", "proposed_budget": 1100.0, "reason": "first shift"},
            {"campaign_id": "c1", "proposed_budget": 1200.0, "reason": "duplicate shift"},
            {"campaign_id": "c_phantom", "proposed_budget": 500.0, "reason": "ghost campaign"},
            {"campaign_id": "c2", "proposed_budget": 1800.0, "reason": "valid reduction"},
        ]
        res = apply_budget_policy(budgets, raw_shifts)
        assert any("Dropped duplicate shift for c1" in n for n in res.notes)
        assert any("Dropped shift for unknown campaign 'c_phantom'" in n for n in res.notes)
        assert len(res.shifts) == 2
        assert res.is_conserved

    def test_strict_budget_conservation_enforcement(self):
        """Verify that total proposed budget NEVER exceeds total current budget."""
        budgets = {f"c{i}": 1000.0 for i in range(1, 6)}  # 5 campaigns @ 1000 = 5000 INR
        
        # Propose +25% on 4 campaigns (+1000) and -25% on only 1 campaign (-250)
        # Net requested increase = +750 INR. Conservation MUST trim the increases by 750 INR total.
        raw_shifts = [
            {"campaign_id": "c1", "proposed_budget": 1250.0, "reason": "boost 1"},
            {"campaign_id": "c2", "proposed_budget": 1250.0, "reason": "boost 2"},
            {"campaign_id": "c3", "proposed_budget": 1250.0, "reason": "boost 3"},
            {"campaign_id": "c4", "proposed_budget": 1250.0, "reason": "boost 4"},
            {"campaign_id": "c5", "proposed_budget": 750.0, "reason": "cut 5"},
        ]
        
        res = apply_budget_policy(budgets, raw_shifts)
        assert res.is_conserved
        assert res.total_proposed_inr <= res.total_current_inr + 0.01
        assert any("Trimmed total increase" in n for n in res.notes)
        assert round(res.total_proposed_inr, 2) == round(res.total_current_inr, 2)

    def test_optimizer_with_empty_and_single_campaign(self):
        """Verify BudgetOptimizer handles empty or single campaign snapshots gracefully."""
        optimizer = BudgetOptimizer()
        
        # 1. Empty snapshot
        empty_snap = CampaignSnapshot(
            account_ids=["acc_1"],
            platform=Platform.META_ADS,
            campaigns=[],
            total_spend_inr=0.0,
            blended_roas=0.0,
        )
        res_empty = optimizer.optimize(empty_snap)
        assert len(res_empty.shifts) == 0
        assert res_empty.is_conserved

        # 2. Single campaign
        single_c = MetricRow(
            campaign_id="cmp_single",
            campaign_name="Solo Campaign",
            platform=Platform.META_ADS,
            spend_inr=30000.0,
            impressions=10000,
            clicks=500,
            conversions=100,
            roas=3.5,
            cpa_inr=300.0,
            ctr=0.05,
        )
        single_snap = CampaignSnapshot(
            account_ids=["acc_1"],
            platform=Platform.META_ADS,
            campaigns=[single_c],
            total_spend_inr=30000.0,
            blended_roas=3.5,
        )
        res_single = optimizer.optimize(single_snap)
        assert len(res_single.shifts) == 0  # Cannot reallocate with single campaign
        assert res_single.is_conserved

    def test_optimizer_equal_roas_campaigns(self):
        """Verify BudgetOptimizer does not make unnecessary shifts if ROAS is equal."""
        optimizer = BudgetOptimizer()
        c1 = MetricRow("c1", "Camp 1", Platform.META_ADS, 30000.0, 10000, 500, 100, 2.5, 300.0, 0.05)
        c2 = MetricRow("c2", "Camp 2", Platform.GOOGLE_ADS, 30000.0, 10000, 500, 100, 2.5, 300.0, 0.05)
        snap = CampaignSnapshot(
            account_ids=["acc_1", "acc_2"],
            platform=Platform.META_ADS,
            campaigns=[c1, c2],
            total_spend_inr=60000.0,
            blended_roas=2.5,
        )
        res = optimizer.optimize(snap)
        assert len(res.shifts) == 0
        assert res.is_conserved
