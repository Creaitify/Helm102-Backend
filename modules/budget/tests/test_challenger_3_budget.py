"""Empirical Adversarial Stress Suite for Budget Optimizer.
Authored by Challenger 3.

Covers:
- Clamps: ±25% exact and extreme upper/lower boundaries
- Zero and negative proposed budgets rejection
- Non-numeric / boolean / malformed type rejection
- 100-run randomized portfolio conservation law invariant proof
"""

import random
import pytest
from modules.budget.optimizer import BudgetOptimizer, apply_budget_policy


class TestBudgetOptimizerChallenger3:
    """Adversarial stress suite for Budget Optimizer."""

    def test_upper_and_lower_clamp_boundaries(self):
        """Test exact boundary transitions for ±25% clamps."""
        budgets = {"c_up": 1000.0, "c_down": 2000.0}

        # Exact +25% and -25%
        exact_shifts = [
            {"campaign_id": "c_up", "proposed_budget": 1250.0, "reason": "exact +25%"},
            {"campaign_id": "c_down", "proposed_budget": 1500.0, "reason": "exact -25%"},
        ]
        res_exact = apply_budget_policy(budgets, exact_shifts)
        assert res_exact.is_conserved
        assert len(res_exact.shifts) == 2
        s_up = next(s for s in res_exact.shifts if s.campaign_id == "c_up")
        s_down = next(s for s in res_exact.shifts if s.campaign_id == "c_down")
        assert s_up.proposed_daily_budget_inr == 1250.0
        assert s_up.shift_percentage == 25.0
        assert s_down.proposed_daily_budget_inr == 1500.0
        assert s_down.shift_percentage == -25.0

        # Extreme overflow (+1,000,000%) and underflow (-99.99%)
        extreme_shifts = [
            {"campaign_id": "c_up", "proposed_budget": 10000000.0, "reason": "massive scale"},
            {"campaign_id": "c_down", "proposed_budget": 0.01, "reason": "near zero slash"},
        ]
        res_extreme = apply_budget_policy(budgets, extreme_shifts)
        assert res_extreme.is_conserved
        s_up_ex = next(s for s in res_extreme.shifts if s.campaign_id == "c_up")
        s_down_ex = next(s for s in res_extreme.shifts if s.campaign_id == "c_down")
        assert s_up_ex.proposed_daily_budget_inr == 1250.0
        assert s_down_ex.proposed_daily_budget_inr == 1500.0

    def test_non_positive_and_malformed_budgets(self):
        """Test negative, zero, boolean, None, string budgets are rejected."""
        budgets = {"c1": 1000.0}
        bad_values = [-500.0, -0.001, 0, 0.0, True, False, "1000", None, [], {}]
        for val in bad_values:
            res = apply_budget_policy(budgets, [{"campaign_id": "c1", "proposed_budget": val}])
            assert len(res.shifts) == 0, f"Budget {val!r} was not rejected"

    def test_negative_and_invalid_current_budgets(self):
        """Test that negative, zero, NaN, or non-numeric current budgets are dropped safely."""
        invalid_current_budgets = [
            {"c1": -100.0},
            {"c1": 0.0},
            {"c1": float("nan")},
            {"c1": float("-inf")},
            {"c1": "not_a_number"},
            {"c1": None},
        ]
        for b in invalid_current_budgets:
            res = apply_budget_policy(b, [{"campaign_id": "c1", "proposed_budget": 1000.0}])
            assert len(res.shifts) == 0, f"Current budget {b} was not dropped"
            if "c1" in b and b["c1"] not in (None, "not_a_number"):
                assert any("non-positive or invalid current budget" in n for n in res.notes)

        # Non-dict budgets and non-list raw_shifts
        assert len(apply_budget_policy(None, []).shifts) == 0
        assert len(apply_budget_policy({}, None).shifts) == 0
        assert len(apply_budget_policy("bad", "bad").shifts) == 0

    def test_conservation_invariant_randomized_trials(self):
        """Verify conservation invariant holds across 100 randomized multi-campaign portfolios."""
        random.seed(12345)
        for i in range(100):
            n = random.randint(2, 10)
            budgets = {f"cmp_{k}": round(random.uniform(500.0, 20000.0), 2) for k in range(n)}
            raw_shifts = []
            for k in range(n):
                cid = f"cmp_{k}"
                cur = budgets[cid]
                # Random multiplier from -0.5 to 5.0
                mult = random.uniform(-0.5, 5.0)
                prop = round(cur * mult, 2) if mult > 0 else 0.0
                raw_shifts.append({"campaign_id": cid, "proposed_budget": prop})

            res = apply_budget_policy(budgets, raw_shifts)
            assert res.is_conserved
            assert res.total_proposed_inr <= res.total_current_inr + 0.01
