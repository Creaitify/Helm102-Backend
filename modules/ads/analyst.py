"""Ad-Ops Analyst worker: deterministic performance analytics.

Reads the campaign snapshot plus past-period history and answers, in
structured form: what is working, what is decaying, where budget should go
("what to buy"), and which new campaigns are worth drafting. No LLM calls —
numbers come straight from the ad accounts (or the labelled synthetic set).
"""

from __future__ import annotations

from typing import Any

from modules.ads.contracts import (
    CampaignDraft,
    CampaignSnapshot,
    HistoryPeriod,
    MetricRow,
    Platform,
)

# A campaign is "working" when it beats the blended account ROAS (or, when
# ROAS is untracked, when its CPA beats the account average).
_DECAY_CTR_DROP = 0.25  # ≥25% CTR drop vs prior period = fatigue signal
_DECAY_CPA_RISE = 0.30  # ≥30% CPA rise vs prior period = decay signal


class AdOpsAnalyst:
    """Deterministic analytics over live/synthetic campaign data."""

    def analyze(
        self,
        snapshot: CampaignSnapshot,
        history: list[HistoryPeriod] | None = None,
    ) -> dict[str, Any]:
        campaigns = list(snapshot.campaigns)
        findings: dict[str, Any] = {
            "data_source": snapshot.source,
            "data_notes": snapshot.notes,
            "trends": [],
            "top_angles": [],
            "decay_signals": [],
            "what_works": [],
            "recommendations": [],
            "per_campaign": [],
            "campaign_drafts": [],
        }

        if not campaigns:
            findings["trends"].append(
                "No campaign rows available for this period — nothing to analyze."
            )
            return findings

        # --- Per-campaign table with a composite efficiency score ---
        avg_cpa = _avg([c.cpa_inr for c in campaigns if c.cpa_inr > 0])
        for c in campaigns:
            findings["per_campaign"].append(
                {
                    "campaign_id": c.campaign_id,
                    "campaign_name": c.campaign_name,
                    "platform": c.platform.value,
                    "spend_inr": c.spend_inr,
                    "impressions": c.impressions,
                    "clicks": c.clicks,
                    "conversions": c.conversions,
                    "roas": c.roas,
                    "cpa_inr": c.cpa_inr,
                    "ctr": c.ctr,
                    "score": _score(c, snapshot.blended_roas, avg_cpa),
                }
            )
        findings["per_campaign"].sort(key=lambda r: r["score"], reverse=True)

        # --- Overall trend line ---
        findings["trends"].append(
            f"Blended ROAS {snapshot.blended_roas}x across {len(campaigns)} campaigns, "
            f"total spend ₹{int(snapshot.total_spend_inr):,} ({snapshot.source} data)."
        )

        # --- What works: campaigns above blended performance ---
        winners = [r for r in findings["per_campaign"] if r["score"] >= 60]
        losers = [r for r in findings["per_campaign"] if r["score"] < 40]
        for w in winners:
            reason = (
                f"{w['campaign_name']}: score {w['score']}/100 — "
                f"ROAS {w['roas']}x, CPA ₹{int(w['cpa_inr'])}, CTR {w['ctr']}%."
            )
            findings["what_works"].append(reason)
        if winners:
            top = winners[0]
            findings["top_angles"].append(
                f"{top['campaign_name']} is the strongest angle "
                f"({top['roas']}x ROAS, ₹{int(top['cpa_inr'])} CPA)."
            )

        # --- Past-data decay detection (current vs prior period) ---
        prior_by_id: dict[str, MetricRow] = {}
        history_meta: dict[str, Any] | None = None
        if history:
            current = next((h for h in history if h.label == "current"), None)
            prior = next((h for h in history if h.label == "prior"), None)
            if prior:
                prior_by_id = {c.campaign_id: c for c in prior.campaigns}
                history_meta = {
                    "current_range": f"{current.date_start}..{current.date_end}" if current else None,
                    "prior_range": f"{prior.date_start}..{prior.date_end}",
                    "source": prior.source,
                }

        for c in campaigns:
            p = prior_by_id.get(c.campaign_id)
            if p is None:
                continue
            deltas = []
            if p.ctr > 0 and (p.ctr - c.ctr) / p.ctr >= _DECAY_CTR_DROP:
                deltas.append(f"CTR fell {round((p.ctr - c.ctr) / p.ctr * 100)}% ({p.ctr}% → {c.ctr}%)")
            if p.cpa_inr > 0 and c.cpa_inr > 0 and (c.cpa_inr - p.cpa_inr) / p.cpa_inr >= _DECAY_CPA_RISE:
                deltas.append(f"CPA rose {round((c.cpa_inr - p.cpa_inr) / p.cpa_inr * 100)}% (₹{int(p.cpa_inr)} → ₹{int(c.cpa_inr)})")
            if p.roas > 0 and c.roas > 0 and (p.roas - c.roas) / p.roas >= 0.25:
                deltas.append(f"ROAS fell from {p.roas}x to {c.roas}x")
            if deltas:
                findings["decay_signals"].append(
                    f"{c.campaign_name} is decaying vs prior period: " + "; ".join(deltas) + "."
                )

        if not findings["decay_signals"]:
            if prior_by_id:
                findings["decay_signals"].append("No significant decay vs prior period.")
            else:
                worst = findings["per_campaign"][-1]
                findings["decay_signals"].append(
                    f"No prior-period history available; weakest current performer is "
                    f"{worst['campaign_name']} (score {worst['score']}/100)."
                )
        if history_meta:
            findings["history"] = history_meta

        # --- What to buy: budget direction recommendations ---
        for w in winners[:2]:
            findings["recommendations"].append(
                {
                    "action": "SCALE",
                    "campaign_id": w["campaign_id"],
                    "campaign_name": w["campaign_name"],
                    "reason": f"Beats account benchmarks (score {w['score']}/100); scale within the ±25% policy cap.",
                }
            )
        for l in losers:
            findings["recommendations"].append(
                {
                    "action": "REDUCE_OR_REFRESH",
                    "campaign_id": l["campaign_id"],
                    "campaign_name": l["campaign_name"],
                    "reason": f"Underperforming (score {l['score']}/100); reduce budget and refresh creative.",
                }
            )

        # --- New campaign opportunities (drafts, created only after approval) ---
        findings["campaign_drafts"] = [
            _draft_to_dict(d) for d in self.propose_campaign_drafts(snapshot, findings)
        ]
        return findings

    def propose_campaign_drafts(
        self, snapshot: CampaignSnapshot, findings: dict[str, Any]
    ) -> list[CampaignDraft]:
        """Draft new campaigns cloned from the winning angle onto its own and
        the under-served platform. Always PAUSED; human approves creation."""
        ranked = findings.get("per_campaign", [])
        if not ranked:
            return []
        top = ranked[0]
        top_platform = Platform(top["platform"])
        other_platform = (
            Platform.META_ADS if top_platform == Platform.GOOGLE_ADS else Platform.GOOGLE_ADS
        )
        seed_budget = max(500.0, round(top["spend_inr"] * 0.10 / 30, -1))  # ~10% of winner, daily

        drafts = [
            CampaignDraft(
                name=f"{top['campaign_name']} — Scale Test v2",
                platform=top_platform,
                objective="OUTCOME_TRAFFIC" if top_platform == Platform.META_ADS else "search_expansion",
                daily_budget_inr=seed_budget,
                rationale=(
                    f"Clone of top performer ({top['roas']}x ROAS, score {top['score']}/100) "
                    "with fresh creative to test incremental headroom."
                ),
                channel_type="SEARCH",
            ),
            CampaignDraft(
                name=f"{top['campaign_name']} — {other_platform.value} Expansion",
                platform=other_platform,
                objective="OUTCOME_TRAFFIC" if other_platform == Platform.META_ADS else "search_expansion",
                daily_budget_inr=seed_budget,
                rationale=(
                    f"Winning angle currently runs only on {top_platform.value}; "
                    f"test the same angle on {other_platform.value} at a small seed budget."
                ),
                channel_type="SEARCH",
            ),
        ]
        return drafts


def _score(c: MetricRow, blended_roas: float, avg_cpa: float) -> int:
    """Composite 0-100 efficiency score, deterministic and explainable.

    ROAS vs account blend (50%), CPA vs account average (30%), CTR (20%).
    When ROAS is untracked (live accounts without value tracking), CPA and
    CTR carry the weight.
    """
    if c.roas > 0 and blended_roas > 0:
        roas_part = min(c.roas / blended_roas, 2.0) / 2.0 * 50
    else:
        roas_part = 25.0  # neutral when untracked
    if c.cpa_inr > 0 and avg_cpa > 0:
        cpa_part = min(avg_cpa / c.cpa_inr, 2.0) / 2.0 * 30
    else:
        cpa_part = 15.0
    ctr_part = min(c.ctr / 5.0, 1.0) * 20  # 5%+ CTR = full marks
    return int(round(roas_part + cpa_part + ctr_part))


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _draft_to_dict(d: CampaignDraft) -> dict[str, Any]:
    return {
        "name": d.name,
        "platform": d.platform.value,
        "objective": d.objective,
        "daily_budget_inr": d.daily_budget_inr,
        "rationale": d.rationale,
        "channel_type": d.channel_type,
        "status": d.status,
    }
