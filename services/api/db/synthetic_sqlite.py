"""SQLite Synthetic Marketing Data Generator with Coherent Data Variations.

Design rules:
- Deterministic: the same (scenario, days) pair always produces the identical
  dataset (seeded RNG), so demos, tests, and analyst output are reproducible.
- Scenario-shaped: each preset assigns different performance tiers to the
  campaign templates, so switching scenarios visibly changes what the analyst
  finds (winners, decay, compliance loopback).
- Date-window safe: all period filtering uses Python-computed local dates on
  both write and read paths — never SQLite's UTC `date('now')`, which is off
  by a day for non-UTC operators.
"""

from __future__ import annotations

import os
import random
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from modules.ads.contracts import (
    CampaignSnapshot,
    HistoryPeriod,
    MetricRow,
    Platform,
)

SQLITE_SYNTHETIC_DB_PATH = os.environ.get(
    "HELM_SYNTHETIC_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_campaigns.sqlite"),
)

# Tier metric shapes: (prior period, current period) — the split powers the
# analyst's decay detection over the stored history.
_TIER_SHAPES = {
    "TOP_PERFORMER": {
        "prior": {"ctr": 6.27, "cpc": 5.5, "conv_rate": 0.048, "roas": 3.0},
        "current": {"ctr": 6.72, "cpc": 5.3, "conv_rate": 0.050, "roas": 3.4},
    },
    "STABLE": {
        "prior": {"ctr": 4.17, "cpc": 4.5, "conv_rate": 0.036, "roas": 2.1},
        "current": {"ctr": 4.17, "cpc": 4.5, "conv_rate": 0.036, "roas": 2.1},
    },
    "DECAYING": {
        "prior": {"ctr": 2.83, "cpc": 4.7, "conv_rate": 0.028, "roas": 1.9},
        "current": {"ctr": 1.85, "cpc": 7.7, "conv_rate": 0.012, "roas": 1.1},
    },
}

# Per-scenario tier assignment for the five campaign templates, in template
# order. This is what makes each preset tell a different story.
_SCENARIO_TIERS = {
    "growth_and_fatigue": ["TOP_PERFORMER", "STABLE", "DECAYING", "TOP_PERFORMER", "STABLE"],
    "sebi_risk_scenario": ["TOP_PERFORMER", "STABLE", "DECAYING", "TOP_PERFORMER", "STABLE"],
    "scale_winner": ["TOP_PERFORMER", "TOP_PERFORMER", "STABLE", "TOP_PERFORMER", "STABLE"],
    "multi_channel_mix": ["STABLE", "TOP_PERFORMER", "STABLE", "STABLE", "TOP_PERFORMER"],
}

_TEMPLATES = [
    {
        "id": "cmp_google_search_high_intent",
        "name": "Finnovate — Mutual Fund High-Intent Search",
        "platform": "google_ads",
        "objective": "CONVERSIONS",
        "channel_type": "SEARCH",
        "budget": 45000.0,
        "audience": "High-intent investors searching 'best mutual fund SIP'",
    },
    {
        "id": "cmp_meta_sip_growth_mof",
        "name": "Finnovate — SIP Growth Mid-Funnel Video",
        "platform": "meta_ads",
        "objective": "CONVERSIONS",
        "channel_type": "VIDEO",
        "budget": 65000.0,
        "audience": "Salaried Professionals 25-45, Personal Finance interest",
    },
    {
        "id": "cmp_meta_gold_etf_fatigued",
        "name": "Finnovate — Gold ETF Broad Audience",
        "platform": "meta_ads",
        "objective": "TRAFFIC",
        "channel_type": "DISPLAY",
        "budget": 30000.0,
        "audience": "Broad India 21-50, Precious Metals",
    },
    {
        "id": "cmp_google_pmax_wealth",
        "name": "Finnovate — Wealth Accelerator Performance Max",
        "platform": "google_ads",
        "objective": "CONVERSIONS",
        "channel_type": "PERFORMANCE_MAX",
        "budget": 50000.0,
        "audience": "Automated Multi-Asset Placement",
    },
    {
        "id": "cmp_meta_elss_tax_season",
        "name": "Finnovate — ELSS Tax Saving 80C Special",
        "platform": "meta_ads",
        "objective": "CONVERSIONS",
        "channel_type": "CAROUSEL",
        "budget": 40000.0,
        "audience": "Tax filers, Income Tax 80C deductions",
    },
]

_COMPLIANT_TEXT = (
    "Transparent investing with low expense ratios. "
    "Mutual fund investments are subject to market risks."
)


def get_db_connection() -> sqlite3.Connection:
    """Ensure directory exists and connect to synthetic SQLite database."""
    os.makedirs(os.path.dirname(os.path.abspath(SQLITE_SYNTHETIC_DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(SQLITE_SYNTHETIC_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_synthetic_schema() -> None:
    """Initialize synthetic campaign tables in SQLite."""
    conn = get_db_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS synthetic_campaigns (
                campaign_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                platform TEXT NOT NULL,
                objective TEXT NOT NULL,
                channel_type TEXT NOT NULL,
                target_roas REAL NOT NULL,
                target_cpa REAL NOT NULL,
                daily_budget REAL NOT NULL,
                status TEXT NOT NULL,
                audience_segment TEXT,
                scenario TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS synthetic_daily_metrics (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                date TEXT NOT NULL,
                spend REAL NOT NULL,
                impressions INTEGER NOT NULL,
                clicks INTEGER NOT NULL,
                conversions INTEGER NOT NULL,
                conversion_value REAL NOT NULL,
                ctr REAL NOT NULL,
                cpc REAL NOT NULL,
                cpa REAL NOT NULL,
                roas REAL NOT NULL,
                FOREIGN KEY (campaign_id) REFERENCES synthetic_campaigns(campaign_id)
            );

            CREATE INDEX IF NOT EXISTS idx_synth_metrics_campaign_date
                ON synthetic_daily_metrics(campaign_id, date);
            CREATE INDEX IF NOT EXISTS idx_synth_metrics_date
                ON synthetic_daily_metrics(date);

            CREATE TABLE IF NOT EXISTS synthetic_creatives (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                headline TEXT NOT NULL,
                primary_text TEXT NOT NULL,
                call_to_action TEXT NOT NULL,
                media_type TEXT NOT NULL,
                compliance_risk_tag TEXT NOT NULL,
                performance_tier TEXT NOT NULL,
                FOREIGN KEY (campaign_id) REFERENCES synthetic_campaigns(campaign_id)
            );

            CREATE TABLE IF NOT EXISTS synthetic_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()


def _creative_for(tier: str, scenario_name: str) -> tuple[str, str, str]:
    """(headline, primary_text, risk_tag) for a campaign tier under a scenario.

    Only the SEBI risk preset plants a non-compliant guaranteed-return claim
    (to exercise the deterministic verifier + loopback); every other preset
    ships fully compliant copy with the statutory disclaimer.
    """
    if tier == "DECAYING" and scenario_name == "sebi_risk_scenario":
        return (
            "Guaranteed Double Returns in 3 Years with Gold",
            "Invest in gold now for 100% assured safety and zero risk.",
            "NON_COMPLIANT_GUARANTEED_RETURN",
        )
    if tier == "TOP_PERFORMER":
        return (
            "Disciplined SIP Investing for Long-Term Wealth",
            "Start small with ₹500/month automated SIPs in top index funds. "
            "Mutual fund investments are subject to market risks.",
            "COMPLIANT",
        )
    return (
        "Automate Your Financial Future with Smart SIPs",
        _COMPLIANT_TEXT,
        "COMPLIANT",
    )


def generate_synthetic_scenario(scenario_name: str = "growth_and_fatigue", days: int = 60) -> dict[str, Any]:
    """Generate a coherent synthetic campaign dataset with specific variance patterns.

    Deterministic: identical (scenario_name, days) inputs rebuild the exact
    same dataset, byte for byte.
    """
    days = max(60, days)
    rng = random.Random(f"{scenario_name}:{days}")  # reproducible variance
    tiers = _SCENARIO_TIERS.get(scenario_name, _SCENARIO_TIERS["growth_and_fatigue"])

    init_synthetic_schema()
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Fresh scenario replaces prior data atomically (single transaction).
        cur.execute("DELETE FROM synthetic_daily_metrics")
        cur.execute("DELETE FROM synthetic_creatives")
        cur.execute("DELETE FROM synthetic_campaigns")

        generated_at = datetime.now(timezone.utc).isoformat()
        base_date = date.today() - timedelta(days=days)
        half_point = days // 2
        campaign_records = []

        for template, tier in zip(_TEMPLATES, tiers):
            c_id = template["id"]
            shape_cur = _TIER_SHAPES[tier]["current"]
            cur.execute(
                """
                INSERT INTO synthetic_campaigns
                (campaign_id, name, platform, objective, channel_type, target_roas, target_cpa,
                 daily_budget, status, audience_segment, scenario, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ENABLED', ?, ?, ?)
                """,
                (
                    c_id,
                    template["name"],
                    template["platform"],
                    template["objective"],
                    template["channel_type"],
                    shape_cur["roas"],
                    round(template["budget"] * 0.003, 2),
                    template["budget"],
                    template["audience"],
                    scenario_name,
                    generated_at,
                ),
            )

            headline, primary_text, risk_tag = _creative_for(tier, scenario_name)
            cur.execute(
                """
                INSERT INTO synthetic_creatives
                (id, campaign_id, headline, primary_text, call_to_action, media_type,
                 compliance_risk_tag, performance_tier)
                VALUES (?, ?, ?, ?, 'INVEST_NOW', ?, ?, ?)
                """,
                (
                    f"crt_{uuid.uuid4().hex[:8]}",
                    c_id,
                    headline,
                    primary_text,
                    template["channel_type"],
                    risk_tag,
                    tier,
                ),
            )

            daily_budget = template["budget"]
            for day in range(days):
                cur_date = (base_date + timedelta(days=day)).isoformat()
                period = "prior" if day < half_point else "current"
                shape = _TIER_SHAPES[tier][period]

                spend = daily_budget * rng.uniform(0.95, 1.05)
                ctr = shape["ctr"] + rng.uniform(-0.1, 0.1)
                cpc = shape["cpc"]
                conv_rate = shape["conv_rate"]
                roas = shape["roas"] + rng.uniform(-0.05, 0.05)

                clicks = max(10, int(spend / cpc))
                impressions = int(clicks / max(0.005, ctr / 100.0))
                conversions = max(1, int(clicks * conv_rate))
                cpa = round(spend / conversions, 2)
                conversion_value = round(spend * roas, 2)

                cur.execute(
                    """
                    INSERT INTO synthetic_daily_metrics
                    (id, campaign_id, date, spend, impressions, clicks, conversions,
                     conversion_value, ctr, cpc, cpa, roas)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"met_{uuid.uuid4().hex[:10]}",
                        c_id,
                        cur_date,
                        round(spend, 2),
                        impressions,
                        clicks,
                        conversions,
                        conversion_value,
                        round(ctr, 2),
                        round(cpc, 2),
                        cpa,
                        round(roas, 2),
                    ),
                )

            campaign_records.append(
                {
                    "campaign_id": c_id,
                    "name": template["name"],
                    "platform": template["platform"],
                    "tier": tier,
                    "daily_budget": daily_budget,
                }
            )

        # Store generation metadata so the console can show what's loaded.
        for key, value in (
            ("scenario", scenario_name),
            ("days", str(days)),
            ("generated_at", generated_at),
            ("date_start", base_date.isoformat()),
            ("date_end", date.today().isoformat()),
        ):
            cur.execute(
                "INSERT INTO synthetic_meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

        conn.commit()
    finally:
        conn.close()

    return {
        "status": "success",
        "scenario": scenario_name,
        "days": days,
        "campaign_count": len(_TEMPLATES),
        "campaigns": campaign_records,
        "database_path": SQLITE_SYNTHETIC_DB_PATH,
    }


def get_synthetic_meta() -> dict[str, Any]:
    """Generation metadata + row counts for the console's data panel."""
    init_synthetic_schema()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM synthetic_meta")
        meta = {r["key"]: r["value"] for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) AS cnt FROM synthetic_daily_metrics")
        meta["metric_rows"] = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM synthetic_campaigns")
        meta["campaign_count"] = cur.fetchone()["cnt"]
        return meta
    finally:
        conn.close()


def _rows_to_metric_rows(rows: list[sqlite3.Row]) -> list[MetricRow]:
    """Aggregate SQL rows into typed MetricRows with consistent derived metrics."""
    metric_rows: list[MetricRow] = []
    for r in rows:
        spend = float(r["total_spend"] or 0.0)
        impr = int(r["total_impressions"] or 0)
        clicks = int(r["total_clicks"] or 0)
        convs = int(r["total_conversions"] or 0)
        val = float(r["total_value"] or 0.0)

        metric_rows.append(
            MetricRow(
                campaign_id=r["campaign_id"],
                campaign_name=r["campaign_name"],
                platform=Platform.GOOGLE_ADS if r["platform"] == "google_ads" else Platform.META_ADS,
                spend_inr=spend,
                impressions=impr,
                clicks=clicks,
                conversions=convs,
                roas=round(val / spend, 2) if spend > 0 else 0.0,
                cpa_inr=round(spend / convs, 2) if convs > 0 else 0.0,
                ctr=round(clicks / impr * 100, 2) if impr > 0 else 0.0,
                status=r["status"] or "ENABLED",
            )
        )
    return metric_rows


_PERIOD_QUERY = """
    SELECT
        c.campaign_id,
        c.name as campaign_name,
        c.platform,
        c.status,
        SUM(m.spend) as total_spend,
        SUM(m.impressions) as total_impressions,
        SUM(m.clicks) as total_clicks,
        SUM(m.conversions) as total_conversions,
        SUM(m.conversion_value) as total_value
    FROM synthetic_campaigns c
    JOIN synthetic_daily_metrics m ON c.campaign_id = m.campaign_id
    WHERE m.date BETWEEN ? AND ?
    GROUP BY c.campaign_id
"""


def _ensure_seeded(conn: sqlite3.Connection, days: int) -> sqlite3.Connection:
    """Auto-seed the default scenario on first access; returns a live connection."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM synthetic_campaigns")
    if cur.fetchone()["cnt"] == 0:
        conn.close()
        generate_synthetic_scenario("growth_and_fatigue", days=days)
        return get_db_connection()
    return conn


def load_synthetic_snapshot(lookback_days: int = 30) -> CampaignSnapshot:
    """Query SQLite synthetic dataset and return a typed CampaignSnapshot.

    The window is computed in Python local dates so it always matches the
    write path (SQLite's `date('now')` is UTC and can be a day off).
    """
    init_synthetic_schema()
    conn = _ensure_seeded(get_db_connection(), days=lookback_days)
    try:
        today = date.today()
        cutoff = today - timedelta(days=lookback_days)
        cur = conn.cursor()
        cur.execute(_PERIOD_QUERY, (cutoff.isoformat(), today.isoformat()))
        metric_rows = _rows_to_metric_rows(cur.fetchall())
    finally:
        conn.close()

    total_spend = sum(m.spend_inr for m in metric_rows)
    blended_roas = (
        round(sum(m.roas * m.spend_inr for m in metric_rows) / total_spend, 2)
        if total_spend > 0
        else 0.0
    )

    return CampaignSnapshot(
        account_ids=["sqlite_synthetic_master_account"],
        platform=Platform.GOOGLE_ADS,
        campaigns=metric_rows,
        total_spend_inr=total_spend,
        blended_roas=blended_roas,
        source="synthetic",
        timestamp=datetime.now(timezone.utc).isoformat(),
        notes=f"Seeded from SQLite synthetic engine ({lookback_days}-day lookback with coherent variance)",
    )


def load_synthetic_history(lookback_days: int = 30) -> list[HistoryPeriod]:
    """Query current and prior periods from SQLite for decay detection."""
    init_synthetic_schema()
    conn = _ensure_seeded(get_db_connection(), days=lookback_days * 2)
    try:
        today = date.today()
        cur_start = today - timedelta(days=lookback_days)
        prior_start = today - timedelta(days=lookback_days * 2)
        prior_end = cur_start - timedelta(days=1)

        periods: list[HistoryPeriod] = []
        cur = conn.cursor()
        for label, start, end in [
            ("current", cur_start, today),
            ("prior", prior_start, prior_end),
        ]:
            cur.execute(_PERIOD_QUERY, (start.isoformat(), end.isoformat()))
            periods.append(
                HistoryPeriod(
                    label=label,
                    date_start=start.isoformat(),
                    date_end=end.isoformat(),
                    campaigns=_rows_to_metric_rows(cur.fetchall()),
                    source="synthetic",
                )
            )
        return periods
    finally:
        conn.close()
