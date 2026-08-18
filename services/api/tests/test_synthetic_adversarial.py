"""Adversarial and Stress Tests for SQLite Synthetic Engine and AdOpsAnalyst Decay Detection.

Empirically challenges:
1. All 4 scenario presets (growth_and_fatigue, scale_winner, sebi_risk_scenario, multi_channel_mix).
2. SQLite lookback boundaries, date-range filtering, and aggregation consistency.
3. CTR decay detection threshold exact boundaries (24.9% vs 25.0% vs 50.0%).
4. CPA surge detection threshold exact boundaries (29.9% vs 30.0% vs 100.0%).
5. Full pipeline integration: synthetic SQLite generation -> history loading -> AdOpsAnalyst analysis & recommendations.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import pytest

from modules.ads.analyst import AdOpsAnalyst
from modules.ads.contracts import (
    CampaignSnapshot,
    HistoryPeriod,
    MetricRow,
    Platform,
)
from services.api.db.synthetic_sqlite import (
    generate_synthetic_scenario,
    get_db_connection,
    init_synthetic_schema,
    load_synthetic_history,
    load_synthetic_snapshot,
)


class TestSyntheticEnginePresetsAdversarial:
    """Stress testing synthetic SQLite dataset generation across all presets."""

    @pytest.mark.parametrize("preset", [
        "growth_and_fatigue",
        "scale_winner",
        "sebi_risk_scenario",
        "multi_channel_mix",
    ])
    def test_all_four_presets_generate_valid_coherent_datasets(self, preset: str, tmp_path: Path, monkeypatch):
        """Verify each preset generates complete SQLite schema, campaigns, metrics, and creatives."""
        test_db = str(tmp_path / f"synthetic_{preset}.sqlite")
        monkeypatch.setattr("services.api.db.synthetic_sqlite.SQLITE_SYNTHETIC_DB_PATH", test_db)

        result = generate_synthetic_scenario(scenario_name=preset, days=60)
        assert result["status"] == "success"
        assert result["scenario"] == preset
        assert result["campaign_count"] == 5

        # Query SQLite directly to verify data integrity
        with sqlite3.connect(test_db) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 1. Campaigns
            cur.execute("SELECT * FROM synthetic_campaigns")
            campaigns = cur.fetchall()
            assert len(campaigns) == 5
            platforms = {c["platform"] for c in campaigns}
            assert "google_ads" in platforms
            assert "meta_ads" in platforms

            # 2. Daily metrics (5 campaigns * 60 days = 300 rows)
            cur.execute("SELECT COUNT(*) as cnt, SUM(spend) as total_spend FROM synthetic_daily_metrics")
            metrics_summary = cur.fetchone()
            assert metrics_summary["cnt"] == 300
            assert metrics_summary["total_spend"] > 0

            # 3. Creatives
            cur.execute("SELECT * FROM synthetic_creatives")
            creatives = cur.fetchall()
            assert len(creatives) == 5

            if preset == "sebi_risk_scenario":
                decaying_creative = next(c for c in creatives if c["performance_tier"] == "DECAYING")
                assert decaying_creative["compliance_risk_tag"] == "NON_COMPLIANT_GUARANTEED_RETURN"
                assert "Guaranteed" in decaying_creative["headline"]
            else:
                for c in creatives:
                    if c["performance_tier"] != "DECAYING":
                        assert c["compliance_risk_tag"] == "COMPLIANT"
                        assert "Mutual fund investments are subject to market risks" in c["primary_text"]


class TestSyntheticLookbackBoundariesAdversarial:
    """Stress testing lookback date window queries and aggregation."""

    def test_lookback_days_window_scaling(self, tmp_path: Path, monkeypatch):
        """Verify snapshot metrics scale coherently with lookback window size."""
        test_db = str(tmp_path / "synthetic_lookback.sqlite")
        monkeypatch.setattr("services.api.db.synthetic_sqlite.SQLITE_SYNTHETIC_DB_PATH", test_db)

        generate_synthetic_scenario("growth_and_fatigue", days=60)

        # 7-day snapshot
        snap_7 = load_synthetic_snapshot(lookback_days=7)
        # 30-day snapshot
        snap_30 = load_synthetic_snapshot(lookback_days=30)
        # 60-day snapshot
        snap_60 = load_synthetic_snapshot(lookback_days=60)

        assert snap_7.total_spend_inr < snap_30.total_spend_inr < snap_60.total_spend_inr
        assert len(snap_7.campaigns) == 5
        assert len(snap_30.campaigns) == 5
        assert len(snap_60.campaigns) == 5

        # Check math consistency on 30-day snapshot
        for c in snap_30.campaigns:
            if c.impressions > 0:
                expected_ctr = round((c.clicks / c.impressions) * 100, 2)
                assert c.ctr == expected_ctr
            if c.conversions > 0:
                expected_cpa = round(c.spend_inr / c.conversions, 2)
                assert c.cpa_inr == expected_cpa

    def test_synthetic_history_period_segmentation(self, tmp_path: Path, monkeypatch):
        """Verify load_synthetic_history partitions current and prior periods without date overlap."""
        test_db = str(tmp_path / "synthetic_history.sqlite")
        monkeypatch.setattr("services.api.db.synthetic_sqlite.SQLITE_SYNTHETIC_DB_PATH", test_db)

        generate_synthetic_scenario("growth_and_fatigue", days=60)
        history = load_synthetic_history(lookback_days=30)

        assert len(history) == 2
        current = next(h for h in history if h.label == "current")
        prior = next(h for h in history if h.label == "prior")

        assert current.date_start > prior.date_end
        assert len(current.campaigns) == 5
        assert len(prior.campaigns) == 5


class TestDecayDetectionThresholdsAdversarial:
    """Stress testing AdOpsAnalyst CTR decay (≥25%) and CPA surge (≥30%) exact boundary conditions."""

    def test_ctr_decay_detection_exact_boundaries(self):
        """Verify CTR decay is triggered at >= 25.0% drop and ignored at 24.9% drop."""
        analyst = AdOpsAnalyst()

        # Case 1: 24.75% drop (Prior 4.0% -> Current 3.01%) -> BELOW 25% -> NO DECAY
        current_camp_1 = MetricRow(
            campaign_id="cmp_test",
            campaign_name="Test Campaign",
            platform=Platform.META_ADS,
            spend_inr=10000.0,
            impressions=100000,
            clicks=3010,
            conversions=100,
            roas=2.0,
            cpa_inr=100.0,
            ctr=3.01,
        )
        prior_camp_1 = MetricRow(
            campaign_id="cmp_test",
            campaign_name="Test Campaign",
            platform=Platform.META_ADS,
            spend_inr=10000.0,
            impressions=100000,
            clicks=4000,
            conversions=100,
            roas=2.0,
            cpa_inr=100.0,
            ctr=4.00,
        )

        snap1 = CampaignSnapshot(["acc_1"], Platform.META_ADS, [current_camp_1], 10000.0, 2.0)
        hist1 = [
            HistoryPeriod("current", "2026-07-19", "2026-08-18", [current_camp_1]),
            HistoryPeriod("prior", "2026-06-19", "2026-07-18", [prior_camp_1]),
        ]
        res1 = analyst.analyze(snap1, hist1)
        assert not any("CTR fell" in s for s in res1["decay_signals"])

        # Case 2: Exactly 25.0% drop (Prior 4.0% -> Current 3.00%) -> AT THRESHOLD -> MUST TRIGGER DECAY
        current_camp_2 = MetricRow(
            campaign_id="cmp_test",
            campaign_name="Test Campaign",
            platform=Platform.META_ADS,
            spend_inr=10000.0,
            impressions=100000,
            clicks=3000,
            conversions=100,
            roas=2.0,
            cpa_inr=100.0,
            ctr=3.00,
        )
        snap2 = CampaignSnapshot(["acc_1"], Platform.META_ADS, [current_camp_2], 10000.0, 2.0)
        hist2 = [
            HistoryPeriod("current", "2026-07-19", "2026-08-18", [current_camp_2]),
            HistoryPeriod("prior", "2026-06-19", "2026-07-18", [prior_camp_1]),
        ]
        res2 = analyst.analyze(snap2, hist2)
        assert any("CTR fell 25% (4.0% → 3.0%)" in s for s in res2["decay_signals"])

        # Case 3: 50.0% drop (Prior 4.0% -> Current 2.00%) -> SEVERE DECAY
        current_camp_3 = MetricRow(
            campaign_id="cmp_test",
            campaign_name="Test Campaign",
            platform=Platform.META_ADS,
            spend_inr=10000.0,
            impressions=100000,
            clicks=2000,
            conversions=100,
            roas=2.0,
            cpa_inr=100.0,
            ctr=2.00,
        )
        snap3 = CampaignSnapshot(["acc_1"], Platform.META_ADS, [current_camp_3], 10000.0, 2.0)
        hist3 = [
            HistoryPeriod("current", "2026-07-19", "2026-08-18", [current_camp_3]),
            HistoryPeriod("prior", "2026-06-19", "2026-07-18", [prior_camp_1]),
        ]
        res3 = analyst.analyze(snap3, hist3)
        assert any("CTR fell 50% (4.0% → 2.0%)" in s for s in res3["decay_signals"])

    def test_cpa_surge_detection_exact_boundaries(self):
        """Verify CPA surge is triggered at >= 30.0% rise and ignored at 29.9% rise."""
        analyst = AdOpsAnalyst()

        # Prior CPA = 100.0 INR
        prior_camp = MetricRow(
            campaign_id="cmp_cpa_test",
            campaign_name="CPA Test",
            platform=Platform.GOOGLE_ADS,
            spend_inr=10000.0,
            impressions=50000,
            clicks=2000,
            conversions=100,
            roas=2.5,
            cpa_inr=100.0,
            ctr=4.0,
        )

        # Case 1: 29.9% rise (CPA = 129.9 INR) -> BELOW 30% -> NO SURGE
        curr_29_9 = MetricRow(
            campaign_id="cmp_cpa_test",
            campaign_name="CPA Test",
            platform=Platform.GOOGLE_ADS,
            spend_inr=12990.0,
            impressions=50000,
            clicks=2000,
            conversions=100,
            roas=2.5,
            cpa_inr=129.9,
            ctr=4.0,
        )
        snap1 = CampaignSnapshot(["acc_1"], Platform.GOOGLE_ADS, [curr_29_9], 12990.0, 2.5)
        hist1 = [
            HistoryPeriod("current", "2026-07-19", "2026-08-18", [curr_29_9]),
            HistoryPeriod("prior", "2026-06-19", "2026-07-18", [prior_camp]),
        ]
        res1 = analyst.analyze(snap1, hist1)
        assert not any("CPA rose" in s for s in res1["decay_signals"])

        # Case 2: Exactly 30.0% rise (CPA = 130.0 INR) -> AT THRESHOLD -> MUST TRIGGER SURGE
        curr_30_0 = MetricRow(
            campaign_id="cmp_cpa_test",
            campaign_name="CPA Test",
            platform=Platform.GOOGLE_ADS,
            spend_inr=13000.0,
            impressions=50000,
            clicks=2000,
            conversions=100,
            roas=2.5,
            cpa_inr=130.0,
            ctr=4.0,
        )
        snap2 = CampaignSnapshot(["acc_1"], Platform.GOOGLE_ADS, [curr_30_0], 13000.0, 2.5)
        hist2 = [
            HistoryPeriod("current", "2026-07-19", "2026-08-18", [curr_30_0]),
            HistoryPeriod("prior", "2026-06-19", "2026-07-18", [prior_camp]),
        ]
        res2 = analyst.analyze(snap2, hist2)
        assert any("CPA rose 30% (₹100 → ₹130)" in s for s in res2["decay_signals"])

        # Case 3: 100.0% rise (CPA = 200.0 INR) -> SEVERE SURGE
        curr_100_0 = MetricRow(
            campaign_id="cmp_cpa_test",
            campaign_name="CPA Test",
            platform=Platform.GOOGLE_ADS,
            spend_inr=20000.0,
            impressions=50000,
            clicks=2000,
            conversions=100,
            roas=2.5,
            cpa_inr=200.0,
            ctr=4.0,
        )
        snap3 = CampaignSnapshot(["acc_1"], Platform.GOOGLE_ADS, [curr_100_0], 20000.0, 2.5)
        hist3 = [
            HistoryPeriod("current", "2026-07-19", "2026-08-18", [curr_100_0]),
            HistoryPeriod("prior", "2026-06-19", "2026-07-18", [prior_camp]),
        ]
        res3 = analyst.analyze(snap3, hist3)
        assert any("CPA rose 100% (₹100 → ₹200)" in s for s in res3["decay_signals"])

    def test_full_synthetic_pipeline_growth_and_fatigue_analysis(self, tmp_path: Path, monkeypatch):
        """Verify full synthetic pipeline detects fatigued Gold ETF and scales Search winner."""
        test_db = str(tmp_path / "synthetic_pipeline.sqlite")
        monkeypatch.setattr("services.api.db.synthetic_sqlite.SQLITE_SYNTHETIC_DB_PATH", test_db)

        generate_synthetic_scenario("growth_and_fatigue", days=60)
        snapshot = load_synthetic_snapshot(lookback_days=30)
        history = load_synthetic_history(lookback_days=30)

        analyst = AdOpsAnalyst()
        findings = analyst.analyze(snapshot, history)

        # 1. Decay detection for fatigued campaign
        decay_text = " ".join(findings["decay_signals"])
        assert "Gold ETF Broad Audience is decaying" in decay_text
        assert "CTR fell" in decay_text
        assert "CPA rose" in decay_text

        # 2. Winning campaign identified
        assert len(findings["what_works"]) >= 1
        assert any("High-Intent Search" in w or "Performance Max" in w for w in findings["what_works"])

        # 3. Actionable recommendations
        scale_recs = [r for r in findings["recommendations"] if r["action"] == "SCALE"]
        reduce_recs = [r for r in findings["recommendations"] if r["action"] == "REDUCE_OR_REFRESH"]
        assert len(scale_recs) >= 1
        assert len(reduce_recs) >= 1
        assert any(r["campaign_id"] == "cmp_meta_gold_etf_fatigued" for r in reduce_recs)

        # 4. Proposed campaign drafts
        drafts = findings["campaign_drafts"]
        assert len(drafts) == 2
        assert any("Scale Test v2" in d["name"] for d in drafts)
        assert any("Expansion" in d["name"] for d in drafts)
