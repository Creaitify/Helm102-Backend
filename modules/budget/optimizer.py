"""Deterministic Budget Policy and Allocation Optimizer.

Enforces ±25% shift cap and budget conservation in code, below the model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any
from modules.ads.contracts import BudgetShift, CampaignSnapshot, Platform

MAX_SHIFT_FRACTION = 0.25


@dataclass(frozen=True, slots=True)
class PolicyResult:
    """Outcome of deterministic budget policy enforcement."""

    shifts: list[BudgetShift] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    total_current_inr: float = 0.0
    total_proposed_inr: float = 0.0
    is_conserved: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "shifts": [
                {
                    "campaign_id": s.campaign_id,
                    "platform": s.platform.value,
                    "current_daily_budget_inr": s.current_daily_budget_inr,
                    "proposed_daily_budget_inr": s.proposed_daily_budget_inr,
                    "shift_percentage": round(s.shift_percentage, 2),
                    "rationale": s.rationale,
                }
                for s in self.shifts
            ],
            "notes": self.notes,
            "total_current_inr": round(self.total_current_inr, 2),
            "total_proposed_inr": round(self.total_proposed_inr, 2),
            "is_conserved": self.is_conserved,
        }


def _as_positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return float(value) if value > 0 else None


def apply_budget_policy(
    campaign_budgets: dict[str, float] | Any,
    raw_shifts: list[dict[str, Any]] | Any,
    platform_map: dict[str, Platform] | None = None,
) -> PolicyResult:
    """Enforce ±25% cap and conservation on proposed budget shifts."""
    if not isinstance(campaign_budgets, dict) or not isinstance(raw_shifts, list):
        return PolicyResult()

    notes: list[str] = []
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    platform_map = platform_map or {}

    for raw in raw_shifts:
        if not isinstance(raw, dict):
            continue

        cid = str(raw.get("campaign_id", "")).strip()
        if not cid:
            continue

        if cid not in campaign_budgets:
            notes.append(f"Dropped shift for unknown campaign {cid!r}")
            continue

        current = _as_positive_number(campaign_budgets.get(cid))
        if current is None or current <= 0 or not math.isfinite(current):
            notes.append(f"Dropped shift for {cid}: non-positive or invalid current budget")
            continue

        if cid in seen:
            notes.append(f"Dropped duplicate shift for {cid}")
            continue

        proposed = _as_positive_number(raw.get("proposed_budget"))
        if proposed is None:
            notes.append(f"Dropped shift for {cid}: invalid non-positive budget")
            continue

        seen.add(cid)
        low = current * (1 - MAX_SHIFT_FRACTION)
        high = current * (1 + MAX_SHIFT_FRACTION)

        if proposed < low or proposed > high:
            clamped = min(max(proposed, low), high)
            notes.append(f"Clamped {cid} to +/-25%: {int(proposed)} -> {int(clamped)} INR")
            proposed = clamped

        accepted.append({
            "campaign_id": cid,
            "current_budget": current,
            "proposed_budget": proposed,
            "reason": str(raw.get("reason", "")),
        })

    # Conservation Rule: Total proposed across shifted campaigns cannot exceed total current
    total_current = sum(s["current_budget"] for s in accepted)
    total_proposed = sum(s["proposed_budget"] for s in accepted)

    if total_proposed > total_current:
        excess = total_proposed - total_current
        notes.append(f"Trimmed total increase by {int(excess)} INR to enforce budget conservation")

        # Trim increases largest-first
        increases = [s for s in accepted if s["proposed_budget"] > s["current_budget"]]
        increases.sort(key=lambda s: s["proposed_budget"] - s["current_budget"], reverse=True)

        for inc in increases:
            margin = inc["proposed_budget"] - inc["current_budget"]
            trim = min(margin, excess)
            inc["proposed_budget"] -= trim
            excess -= trim
            if excess <= 0:
                break

    # Build final verified shifts (dropping trivial 0-diff moves)
    final_shifts: list[BudgetShift] = []
    for s in accepted:
        cid = s["campaign_id"]
        cur = s["current_budget"]
        prop = s["proposed_budget"]
        if abs(prop - cur) < 0.01:
            notes.append(f"Dropped trivial 0-shift for {cid}")
            continue

        pct = ((prop - cur) / cur) * 100.0
        final_shifts.append(
            BudgetShift(
                campaign_id=cid,
                platform=platform_map.get(cid, Platform.META_ADS),
                current_daily_budget_inr=cur,
                proposed_daily_budget_inr=prop,
                shift_percentage=pct,
                rationale=s["reason"],
            )
        )

    final_cur = sum(s.current_daily_budget_inr for s in final_shifts)
    final_prop = sum(s.proposed_daily_budget_inr for s in final_shifts)

    return PolicyResult(
        shifts=final_shifts,
        notes=notes,
        total_current_inr=final_cur,
        total_proposed_inr=final_prop,
        is_conserved=(final_prop <= final_cur + 0.01),
    )


class BudgetOptimizer:
    """Proposes high-efficiency budget shifts based on ROAS and fatigue."""

    def optimize(self, snapshot: CampaignSnapshot) -> PolicyResult:
        """Analyze snapshot campaigns and produce policy-checked shifts."""
        if not snapshot.campaigns:
            return PolicyResult()

        campaign_budgets: dict[str, float] = {}
        platform_map: dict[str, Platform] = {}
        for c in snapshot.campaigns:
            # Estimate daily budget from spend
            daily_est = round(c.spend_inr / 30.0, 2) if c.spend_inr > 0 else 1000.0
            campaign_budgets[c.campaign_id] = daily_est
            platform_map[c.campaign_id] = c.platform

        # Identify top performers vs fatigued/underperforming
        sorted_by_roas = sorted(snapshot.campaigns, key=lambda c: c.roas, reverse=True)
        top = sorted_by_roas[0]
        bottom = sorted_by_roas[-1]

        raw_shifts = []
        if len(sorted_by_roas) >= 2 and top.roas > bottom.roas:
            top_budget = campaign_budgets[top.campaign_id]
            bottom_budget = campaign_budgets[bottom.campaign_id]

            # Shift up to 20% from bottom to top
            shift_amount = bottom_budget * 0.20
            raw_shifts.append({
                "campaign_id": bottom.campaign_id,
                "proposed_budget": bottom_budget - shift_amount,
                "reason": f"Reallocating spend from underperforming campaign (ROAS {bottom.roas}x) to winner.",
            })
            raw_shifts.append({
                "campaign_id": top.campaign_id,
                "proposed_budget": top_budget + shift_amount,
                "reason": f"Scaling top-performing campaign (ROAS {top.roas}x, CPA {int(top.cpa_inr)} INR).",
            })

        return apply_budget_policy(campaign_budgets, raw_shifts, platform_map)
