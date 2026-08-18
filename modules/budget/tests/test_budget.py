"""Tests for deterministic budget policy and ±25% shift clamp."""

from modules.budget.optimizer import apply_budget_policy


def test_budget_clamp_to_25_percent():
    budgets = {"c1": 1000.0, "c2": 2000.0}
    raw_shifts = [
        {"campaign_id": "c1", "proposed_budget": 1500.0, "reason": "scale up"},  # +50% -> clamped to +25% (1250)
        {"campaign_id": "c2", "proposed_budget": 1750.0, "reason": "scale down"},  # -250 INR
    ]
    res = apply_budget_policy(budgets, raw_shifts)
    assert len(res.shifts) == 2
    c1_shift = next(s for s in res.shifts if s.campaign_id == "c1")
    assert c1_shift.proposed_daily_budget_inr == 1250.0
    assert c1_shift.shift_percentage == 25.0
    assert any("Clamped c1 to +/-25%" in n for n in res.notes)


def test_budget_conservation_enforcement():
    budgets = {"c1": 1000.0, "c2": 1000.0}
    raw_shifts = [
        {"campaign_id": "c1", "proposed_budget": 1250.0, "reason": "increase"},  # +250
        {"campaign_id": "c2", "proposed_budget": 1100.0, "reason": "increase"},  # +100
    ]
    # Total current = 2000, Total proposed = 2350 (exceeds current!)
    res = apply_budget_policy(budgets, raw_shifts)
    assert res.total_proposed_inr <= res.total_current_inr
    assert res.is_conserved
    assert any("Trimmed total increase" in n for n in res.notes)


def test_unknown_campaign_dropped():
    budgets = {"c1": 1000.0}
    raw_shifts = [
        {"campaign_id": "c_unknown", "proposed_budget": 1200.0, "reason": "test"},
    ]
    res = apply_budget_policy(budgets, raw_shifts)
    assert len(res.shifts) == 0
    assert any("unknown campaign" in n for n in res.notes)
