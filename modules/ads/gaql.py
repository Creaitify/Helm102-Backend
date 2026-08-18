"""Google Ads Query Language (GAQL) Query Generators and Performance Parsers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Sequence

from modules.ads.contracts import CampaignSnapshot, MetricRow, Platform

_SAFE_ID_PATTERN = re.compile(r"^[0-9]+$")
_SAFE_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
VALID_DATE_RANGES = frozenset({
    "TODAY",
    "YESTERDAY",
    "LAST_7_DAYS",
    "LAST_14_DAYS",
    "LAST_30_DAYS",
    "THIS_MONTH",
    "LAST_MONTH",
    "THIS_WEEK_SUN_TODAY",
    "THIS_WEEK_MON_TODAY",
    "LAST_WEEK_SUN_SAT",
    "LAST_WEEK_MON_SUN",
    "LAST_BUSINESS_WEEK",
})


def generate_campaign_performance_gaql(
    date_range: str = "LAST_30_DAYS",
    campaign_ids: Sequence[str] | None = None,
    status_filter: str | None = "ENABLED",
) -> str:
    """Generate a sanitized GAQL query for campaign performance metrics.

    Args:
        date_range: Date range literal (e.g. 'LAST_30_DAYS') or custom WHERE clause date filter.
        campaign_ids: Optional list of numeric campaign IDs to filter.
        status_filter: Optional campaign status (e.g. 'ENABLED', 'PAUSED', or None for all).

    Returns:
        Formatted GAQL query string.
    """
    fields = [
        "campaign.id",
        "campaign.name",
        "campaign.status",
        "metrics.cost_micros",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.conversions",
        "metrics.conversions_value",
        "metrics.ctr",
        "metrics.average_cpc",
        "metrics.cost_per_conversion",
    ]

    where_clauses: list[str] = []

    # Status filter
    if status_filter:
        clean_status = re.sub(r"[^A-Z_]", "", status_filter.upper())
        if clean_status:
            where_clauses.append(f"campaign.status = '{clean_status}'")

    # Campaign IDs
    if campaign_ids:
        clean_ids = [str(cid).strip() for cid in campaign_ids if _SAFE_ID_PATTERN.match(str(cid).strip())]
        if clean_ids:
            ids_str = ", ".join(clean_ids)
            where_clauses.append(f"campaign.id IN ({ids_str})")

    # Date range
    date_range_clean = date_range.strip().upper()
    if date_range_clean in VALID_DATE_RANGES:
        where_clauses.append(f"segments.date DURING {date_range_clean}")
    elif _SAFE_DATE_PATTERN.match(date_range):
        where_clauses.append(f"segments.date = '{date_range}'")

    where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = (
        f"SELECT {', '.join(fields)} "
        f"FROM campaign{where_str} "
        f"ORDER BY metrics.cost_micros DESC"
    )
    return query


def parse_gaql_response(
    rows: list[dict[str, Any]],
    account_id: str = "cust_google_ads",
    source: str = "live",
) -> CampaignSnapshot:
    """Parse Google Ads API / GAQL search response dicts into a CampaignSnapshot.

    Args:
        rows: List of dicts representing search stream / search rows from Google Ads API.
        account_id: Customer ID.
        source: Source tag ("live" | "synthetic" | "byod").

    Returns:
        CampaignSnapshot containing parsed MetricRows.
    """
    campaigns: list[MetricRow] = []

    for r in rows:
        # Support both flattened dicts and nested Google Ads API structures
        camp_dict = r.get("campaign", {}) if isinstance(r.get("campaign"), dict) else r
        metrics_dict = r.get("metrics", {}) if isinstance(r.get("metrics"), dict) else r

        campaign_id = str(camp_dict.get("id") or r.get("campaign_id") or r.get("campaign.id") or "")
        campaign_name = str(camp_dict.get("name") or r.get("campaign_name") or r.get("campaign.name") or "Unnamed Campaign")
        status = str(camp_dict.get("status") or r.get("campaign_status") or r.get("campaign.status") or "ENABLED").upper()

        # Google Ads API returns spend in micros (1 INR = 1,000,000 micros)
        cost_micros = metrics_dict.get("cost_micros") or r.get("metrics.cost_micros") or 0
        spend_inr = float(cost_micros) / 1_000_000.0 if cost_micros else float(metrics_dict.get("cost", 0.0) or r.get("spend_inr", 0.0))

        impressions = int(metrics_dict.get("impressions") or r.get("metrics.impressions") or 0)
        clicks = int(metrics_dict.get("clicks") or r.get("metrics.clicks") or 0)
        conversions = int(round(float(metrics_dict.get("conversions") or r.get("metrics.conversions") or 0)))
        conv_value = float(metrics_dict.get("conversions_value") or r.get("metrics.conversions_value") or 0.0)

        # ROAS = conversion_value / cost
        roas = round(conv_value / spend_inr, 2) if spend_inr > 0 and conv_value > 0 else 0.0

        # CPA = spend / conversions
        cost_per_conv_micros = metrics_dict.get("cost_per_conversion") or r.get("metrics.cost_per_conversion")
        if cost_per_conv_micros:
            cpa_inr = round(float(cost_per_conv_micros) / 1_000_000.0, 2)
        else:
            cpa_inr = round(spend_inr / conversions, 2) if conversions > 0 else 0.0

        # CTR = (clicks / impressions) * 100
        raw_ctr = metrics_dict.get("ctr") or r.get("metrics.ctr")
        if raw_ctr is not None:
            # Google Ads API returns CTR as fraction 0.0672 for 6.72%
            fctr = float(raw_ctr)
            ctr = round(fctr * 100.0 if fctr <= 1.0 else fctr, 2)
        else:
            ctr = round((clicks / impressions) * 100.0, 2) if impressions > 0 else 0.0

        campaigns.append(
            MetricRow(
                campaign_id=campaign_id or f"cmp_{len(campaigns) + 1}",
                campaign_name=campaign_name,
                platform=Platform.GOOGLE_ADS,
                spend_inr=round(spend_inr, 2),
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                roas=roas,
                cpa_inr=cpa_inr,
                ctr=ctr,
                status=status,
            )
        )

    total_spend = sum(c.spend_inr for c in campaigns)
    blended_roas = sum(c.roas * c.spend_inr for c in campaigns) / total_spend if total_spend > 0 else 0.0

    return CampaignSnapshot(
        account_ids=[account_id],
        platform=Platform.GOOGLE_ADS,
        campaigns=campaigns,
        total_spend_inr=round(total_spend, 2),
        blended_roas=round(blended_roas, 2),
        source=source,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
