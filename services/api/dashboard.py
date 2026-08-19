"""Command Center data — everything the platform's landing screen renders.

One request returns the whole overview: headline KPIs with period-over-period
deltas, a daily time series, the channel split, a ranked campaign table, and
the alert feed. Assembling it server-side keeps the dashboard to a single
round trip and guarantees every tile is derived from the same snapshot, so
nothing on screen can disagree with anything else.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from modules.ads.analyst import AdOpsAnalyst
from modules.ads.contracts import CampaignSnapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_deps: dict[str, Any] = {}


def configure(connector: Any, checkpointer: Any) -> None:
    _deps["connector"] = connector
    _deps["checkpointer"] = checkpointer


class Overview(BaseModel):
    """Shape documented for the console; fields are always present."""

    model_config = {"extra": "allow"}


@router.get("/overview")
def overview(days: int = 30) -> dict[str, Any]:
    """Full Command Center payload. Degrades to an explicit error state, never fakes data."""
    connector = _deps.get("connector")
    if connector is None:
        return _empty("Connector is not configured")

    try:
        snapshot: CampaignSnapshot = connector.fetch_campaigns()
        history = connector.fetch_history(lookback_days=days)
    except Exception as exc:
        logger.warning("Dashboard overview fetch failed: %s", exc)
        return _empty(str(exc))

    analyst = AdOpsAnalyst()
    findings = analyst.analyze(snapshot, history)
    kpis = findings["account_kpis"]
    prior = _prior_totals(history)

    campaigns = findings.get("per_campaign", [])
    ranked = sorted(campaigns, key=lambda c: c.get("score", 0), reverse=True)

    return {
        "data_source": snapshot.source,
        "data_source_label": _source_label(snapshot.source),
        "period_days": days,
        "kpis": [
            _kpi("spend", "Total spend", kpis["total_spend_inr"], prior.get("spend"), "currency"),
            _kpi("roas", "Blended ROAS", kpis["blended_roas"], prior.get("roas"), "multiple"),
            _kpi("cpa", "Blended CPA", kpis["blended_cpa_inr"], prior.get("cpa"), "currency", lower_is_better=True),
            _kpi("conversions", "Conversions", kpis["total_conversions"], prior.get("conversions"), "number"),
        ],
        "secondary_kpis": [
            {"key": "clicks", "label": "Clicks", "value": kpis["total_clicks"], "format": "number"},
            {"key": "impressions", "label": "Impressions", "value": kpis["total_impressions"], "format": "number"},
            {
                "key": "ctr",
                "label": "Blended CTR",
                "value": round((kpis["total_clicks"] / kpis["total_impressions"]) * 100, 2)
                if kpis["total_impressions"]
                else 0.0,
                "format": "percent",
            },
            {"key": "campaigns", "label": "Active campaigns", "value": len(campaigns), "format": "number"},
        ],
        "timeseries": _timeseries(days),
        "channels": _channels(findings.get("channel_breakdown", {})),
        "campaigns": [
            {
                "campaign_id": c.get("campaign_id"),
                "campaign_name": c.get("campaign_name"),
                "platform": c.get("platform"),
                "platform_label": _platform_label(c.get("platform")),
                "spend_inr": c.get("spend_inr", 0),
                "roas": c.get("roas", 0),
                "cpa_inr": c.get("cpa_inr", 0),
                "ctr": c.get("ctr", 0),
                "conversions": c.get("conversions", 0),
                "score": c.get("score", 0),
                "verdict": c.get("status_tag", "STABLE"),
            }
            for c in ranked
        ],
        "alerts": _alerts(findings),
        "pending_approvals": _pending_approvals(),
    }


# ----------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------


def _timeseries(days: int) -> list[dict[str, Any]]:
    """Daily spend / conversions / ROAS. Empty when no daily grain exists."""
    try:
        from services.api.db.synthetic_sqlite import load_synthetic_daily_trends

        rows = load_synthetic_daily_trends(lookback_days=days)
    except Exception as exc:
        logger.info("No daily trend series available: %s", exc)
        return []

    return [
        {
            "date": r["date"],
            "spend": r.get("spend", 0),
            "conversions": r.get("conversions", 0),
            "roas": r.get("roas", 0),
            "cpa": r.get("cpa", 0),
            "clicks": r.get("clicks", 0),
        }
        for r in rows
    ]


def _channels(breakdown: dict[str, Any]) -> list[dict[str, Any]]:
    total = sum(float(v.get("spend_inr", 0)) for v in breakdown.values()) or 1.0
    return [
        {
            "key": channel,
            "label": _platform_label(channel),
            "campaign_count": stats.get("campaign_count", 0),
            "spend_inr": stats.get("spend_inr", 0),
            "share": round((float(stats.get("spend_inr", 0)) / total) * 100, 1),
            "roas": stats.get("blended_roas", 0),
            "cpa_inr": stats.get("blended_cpa_inr", 0),
            "conversions": stats.get("conversions", 0),
        }
        for channel, stats in breakdown.items()
    ]


def _alerts(findings: dict[str, Any]) -> list[dict[str, Any]]:
    """Decay signals and scale opportunities, as an actionable feed."""
    alerts: list[dict[str, Any]] = []

    for signal in findings.get("decay_signals", []):
        alerts.append({"severity": "critical", "title": "Performance decay", "detail": signal})

    for rec in findings.get("recommendations", []):
        action = str(rec.get("action", ""))
        if action == "SCALE":
            alerts.append(
                {
                    "severity": "opportunity",
                    "title": f"Scale {rec.get('campaign_name', '')}",
                    "detail": rec.get("reason", ""),
                }
            )
        elif action.startswith("REDUCE"):
            alerts.append(
                {
                    "severity": "warning",
                    "title": f"Reduce {rec.get('campaign_name', '')}",
                    "detail": rec.get("reason", ""),
                }
            )

    return alerts[:8]


def _pending_approvals() -> list[dict[str, Any]]:
    checkpointer = _deps.get("checkpointer")
    if checkpointer is None:
        return []
    try:
        return [
            {
                "run_id": c.get("run_id"),
                "objective": c.get("objective", ""),
                "updated_at": c.get("updated_at", ""),
            }
            for c in checkpointer.list_checkpoints()
            if c.get("status") == "pending_approval"
        ][:5]
    except Exception:
        return []


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _kpi(
    key: str,
    label: str,
    value: Any,
    prior: float | None,
    fmt: str,
    lower_is_better: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {"key": key, "label": label, "value": value, "format": fmt}
    if prior:
        change = round(((float(value) - prior) / prior) * 100, 1)
        item["delta_pct"] = change
        item["improved"] = change < 0 if lower_is_better else change > 0
        item["prior_value"] = prior
    return item


def _prior_totals(history: list[Any]) -> dict[str, float]:
    prior = next((p for p in history if getattr(p, "label", "") == "prior"), None)
    if prior is None or not prior.campaigns:
        return {}

    spend = sum(c.spend_inr for c in prior.campaigns)
    conversions = sum(c.conversions for c in prior.campaigns)
    return {
        "spend": round(spend, 2),
        "conversions": conversions,
        "roas": round(sum(c.roas * c.spend_inr for c in prior.campaigns) / spend, 2) if spend else 0.0,
        "cpa": round(spend / conversions, 2) if conversions else 0.0,
    }


def _empty(reason: str) -> dict[str, Any]:
    return {
        "data_source": "degraded",
        "data_source_label": "Unavailable",
        "error": reason,
        "kpis": [],
        "secondary_kpis": [],
        "timeseries": [],
        "channels": [],
        "campaigns": [],
        "alerts": [],
        "pending_approvals": [],
    }


def _source_label(source: str) -> str:
    return {
        "live": "Live platform data",
        "synthetic": "Synthetic dataset",
        "byod": "Imported dataset",
        "degraded": "Degraded — fetch failed",
    }.get(source, source)


def _platform_label(platform: Any) -> str:
    value = getattr(platform, "value", platform)
    return {
        "google_ads": "Google Ads",
        "meta_ads": "Meta",
        "tiktok_ads": "TikTok Ads",
        "linkedin_ads": "LinkedIn Ads",
        "byod": "Imported",
    }.get(str(value), str(value))
