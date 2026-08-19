"""Ad-Platform Connector Protocol and live-platform implementation.

This is the SOLE module that talks to ad platforms. It delegates to the
dependency-light REST clients in `google_ads_client` / `meta_ads_client`.

Design rules enforced here:
- Real platform calls are built from `HelmSecretStore` credentials (Google
  Cloud Console OAuth client + refresh token for Google, Graph API access
  token for Meta). Credentials never leave server-side custody.
- Data is always labelled honestly: `live` only when it actually came from a
  platform API; `synthetic` for the built-in dev dataset; `byod` for imported
  files; `degraded` when a live fetch failed.
- Live writes either dispatch for real or fail with success=False.
  Nothing ever fabricates an "APPLIED" response.
"""

from __future__ import annotations

import logging

import httpx
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

from modules.ads.contracts import (
    BudgetShift,
    CampaignDraft,
    CampaignSnapshot,
    CreativeVariant,
    ExecutionResult,
    HistoryPeriod,
    MetricRow,
    Platform,
)
from modules.ads.google_ads_client import GoogleAdsClient
from modules.ads.meta_ads_client import META_BASE, MetaAdsClient, MetaAdsError
from services.api.auth.secret_store import HelmSecretStore

logger = logging.getLogger(__name__)

@runtime_checkable
class Connector(Protocol):
    """Protocol for ad platform interactions."""

    def fetch_campaigns(self) -> CampaignSnapshot:
        """Ingest campaign metrics snapshot."""
        ...

    def fetch_history(self, lookback_days: int = 30) -> list[HistoryPeriod]:
        """Fetch current + prior period performance for trend analysis."""
        ...

    def apply_budget(self, shift: BudgetShift, dry_run: bool = True) -> ExecutionResult:
        """Apply approved budget change."""
        ...

    def deploy_creative(self, variant: CreativeVariant, dry_run: bool = True) -> ExecutionResult:
        """Deploy approved creative variant."""
        ...

    def create_campaign(self, draft: CampaignDraft, dry_run: bool = True) -> ExecutionResult:
        """Create an approved new campaign (PAUSED by default)."""
        ...


class MureoConnector:
    """Connector implementation backed by the Google Ads and Meta REST clients."""

    def __init__(self, secret_store: HelmSecretStore | None = None) -> None:
        self.secret_store = secret_store or HelmSecretStore()

    # ------------------------------------------------------------------
    # Client construction (Google Cloud Console OAuth / Meta Graph token)
    # ------------------------------------------------------------------

    def _build_google_client(self) -> GoogleAdsClient:
        """Build the Google Ads REST client from server-side custody credentials.

        Expected keys under `google_ads` in the secret store (all obtained
        from Google Cloud Console + Google Ads API Center):
          client_id, client_secret, refresh_token, developer_token,
          customer_id, login_customer_id (optional, for MCC accounts)
        """
        return GoogleAdsClient.from_credentials(self.secret_store.load("google_ads"))

    def _build_meta_client(self) -> MetaAdsClient:
        """Build the Meta Graph client from server-side custody credentials.

        Expected keys under `meta_ads`: access_token, ad_account_id (act_...).
        """
        return MetaAdsClient.from_credentials(self.secret_store.load("meta_ads"))

    def connection_status(self) -> dict[str, Any]:
        """Which platforms have credentials stored (server-side custody)."""
        has_google = self.secret_store.has_credentials("google_ads")
        has_meta = self.secret_store.has_credentials("meta_ads")
        return {
            "google_ads": has_google,
            "meta_ads": has_meta,
            "data_source": "live" if (has_google or has_meta) else "synthetic",
        }

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def fetch_campaigns(self) -> CampaignSnapshot:
        """Fetch campaign metrics. Live from the platform APIs when connected, else synthetic."""
        has_google = self.secret_store.has_credentials("google_ads")
        has_meta = self.secret_store.has_credentials("meta_ads")

        if not has_google and not has_meta:
            logger.info("No ad platform credentials configured; querying SQLite synthetic snapshot.")
            try:
                from services.api.db.synthetic_sqlite import load_synthetic_snapshot
                return load_synthetic_snapshot(lookback_days=30)
            except Exception as exc:
                logger.warning("Could not load from SQLite synthetic store, using built-in fallback: %s", exc)
                return self._sample_snapshot(source="synthetic")

        rows: list[MetricRow] = []
        account_ids: list[str] = []
        errors: list[str] = []

        if has_google:
            try:
                rows.extend(self._fetch_google_rows("LAST_30_DAYS"))
                account_ids.append(f"cust_{self.secret_store.load('google_ads').get('customer_id', '')}")
            except Exception as exc:
                logger.warning("Google Ads fetch failed: %s", exc)
                errors.append(f"google_ads: {exc}")

        if has_meta:
            try:
                rows.extend(self._fetch_meta_rows("last_30d"))
                account_ids.append(self.secret_store.load("meta_ads").get("ad_account_id", ""))
            except Exception as exc:
                logger.warning("Meta Ads fetch failed: %s", exc)
                errors.append(f"meta_ads: {exc}")

        if not rows:
            # Credentials existed but nothing came back: this is a degraded
            # state and is labelled as such — never presented as live data.
            return CampaignSnapshot(
                account_ids=account_ids,
                platform=Platform.GOOGLE_ADS if has_google else Platform.META_ADS,
                campaigns=[],
                total_spend_inr=0.0,
                blended_roas=0.0,
                source="degraded",
                timestamp=datetime.now(timezone.utc).isoformat(),
                notes="; ".join(errors) or "platform returned no campaigns",
            )

        total_spend = sum(c.spend_inr for c in rows)
        blended = (
            round(sum(c.roas * c.spend_inr for c in rows) / total_spend, 2) if total_spend > 0 else 0.0
        )
        return CampaignSnapshot(
            account_ids=account_ids,
            platform=rows[0].platform,
            campaigns=rows,
            total_spend_inr=total_spend,
            blended_roas=blended,
            source="live",
            timestamp=datetime.now(timezone.utc).isoformat(),
            notes="; ".join(errors),
        )

    def fetch_history(self, lookback_days: int = 30) -> list[HistoryPeriod]:
        """Current period vs the period immediately before it, per campaign.

        Powers the analyst's decay/what-works detection over past data. When
        no platform is connected, returns synthetic history so the pipeline
        stays runnable in dev (clearly labelled synthetic).
        """
        has_google = self.secret_store.has_credentials("google_ads")
        has_meta = self.secret_store.has_credentials("meta_ads")

        today = date.today()
        cur_start = today - timedelta(days=lookback_days)
        prior_start = today - timedelta(days=lookback_days * 2)
        prior_end = cur_start - timedelta(days=1)

        if not has_google and not has_meta:
            try:
                from services.api.db.synthetic_sqlite import load_synthetic_history
                return load_synthetic_history(lookback_days=lookback_days)
            except Exception as exc:
                logger.warning("Could not load history from SQLite synthetic store: %s", exc)
                return self._sample_history(cur_start, today, prior_start, prior_end)

        periods: list[HistoryPeriod] = []
        for label, start, end in (
            ("current", cur_start, today),
            ("prior", prior_start, prior_end),
        ):
            rows: list[MetricRow] = []
            source = "live"
            if has_google:
                try:
                    rows.extend(
                        self._fetch_google_rows(f"{start.isoformat()},{end.isoformat()}")
                    )
                except Exception as exc:
                    logger.warning("Google history fetch (%s) failed: %s", label, exc)
                    source = "degraded"
            if has_meta:
                try:
                    rows.extend(self._fetch_meta_rows(f"{start.isoformat()}..{end.isoformat()}"))
                except Exception as exc:
                    logger.warning("Meta history fetch (%s) failed: %s", label, exc)
                    source = "degraded"
            periods.append(
                HistoryPeriod(
                    label=label,
                    date_start=start.isoformat(),
                    date_end=end.isoformat(),
                    campaigns=rows,
                    source=source if rows else "degraded",
                )
            )
        return periods

    def _fetch_google_rows(self, period: str) -> list[MetricRow]:
        """Campaign performance for a period, straight from the Google Ads API.

        `period` is a GAQL literal (`LAST_30_DAYS`) or `YYYY-MM-DD,YYYY-MM-DD`.
        Conversion value comes back in the same query, so ROAS is real.
        """
        return self._build_google_client().fetch_campaign_metrics(date_range=period)

    def _fetch_meta_rows(self, period: str) -> list[MetricRow]:
        """Campaign-level Meta insights for a period.

        `period` is a Meta preset (`last_30d`) or `YYYY-MM-DD,YYYY-MM-DD`.
        """
        return self._build_meta_client().fetch_campaign_metrics(date_range=period)

    # ------------------------------------------------------------------
    # Writes — dispatch for real or fail honestly. Never fabricate.
    # ------------------------------------------------------------------

    def apply_budget(self, shift: BudgetShift, dry_run: bool = True) -> ExecutionResult:
        """Execute budget shift against the live platform, or preview it as a dry run."""
        payload = {
            "campaign_id": shift.campaign_id,
            "platform": shift.platform.value,
            "current_daily_budget_inr": shift.current_daily_budget_inr,
            "proposed_daily_budget_inr": shift.proposed_daily_budget_inr,
            "shift_percentage": shift.shift_percentage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if dry_run:
            return ExecutionResult(
                success=True,
                platform=shift.platform,
                action_type="UPDATE_CAMPAIGN_BUDGET",
                resource_id=shift.campaign_id,
                payload_sent=payload,
                response_received={"status": "DRY_RUN_VALIDATED", "simulated": True},
                dry_run=True,
            )

        try:
            if shift.platform == Platform.META_ADS:
                response = self._build_meta_client().update_campaign_budget(
                    shift.campaign_id, shift.proposed_daily_budget_inr
                )
                return ExecutionResult(
                    success=True,
                    platform=shift.platform,
                    action_type="UPDATE_CAMPAIGN_BUDGET",
                    resource_id=shift.campaign_id,
                    payload_sent=payload,
                    response_received=response,
                    dry_run=False,
                )

            if shift.platform == Platform.GOOGLE_ADS:
                # Google budgets are separate resources: the client resolves the
                # campaign's real budget resource first — no templated ids.
                response = self._build_google_client().update_campaign_budget(
                    shift.campaign_id, shift.proposed_daily_budget_inr
                )
                results = response.get("results", []) or []
                resource_id = str(results[0].get("resourceName")) if results else shift.campaign_id
                return ExecutionResult(
                    success=True,
                    platform=shift.platform,
                    action_type="UPDATE_CAMPAIGN_BUDGET",
                    resource_id=resource_id,
                    payload_sent=payload,
                    response_received=response,
                    dry_run=False,
                )

            raise ConnectionError(f"No live write path for platform {shift.platform.value}")
        except Exception as exc:
            logger.error("Live budget dispatch failed for %s: %s", shift.campaign_id, exc)
            return ExecutionResult(
                success=False,
                platform=shift.platform,
                action_type="UPDATE_CAMPAIGN_BUDGET",
                resource_id=shift.campaign_id,
                payload_sent=payload,
                response_received={"status": "FAILED"},
                dry_run=False,
                error=str(exc),
            )

    def deploy_creative(self, variant: CreativeVariant, dry_run: bool = True) -> ExecutionResult:
        """Deploy creative variant: dry-run preview, or honest not-implemented.

        Live creative deployment needs an ad set + ad shell per platform
        plus an ad + ad-creative per platform. Until that is wired, the live path
        reports failure — it never claims a deploy happened.
        """
        payload = {
            "campaign_id": variant.campaign_id,
            "platform": variant.platform.value,
            "headline": variant.headline,
            "primary_text": variant.primary_text,
            "call_to_action": variant.call_to_action,
            "video_url": variant.video_url,
            "image_url": variant.image_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if dry_run:
            return ExecutionResult(
                success=True,
                platform=variant.platform,
                action_type="DEPLOY_AD_CREATIVE",
                resource_id=variant.campaign_id,
                payload_sent=payload,
                response_received={"status": "DRY_RUN_VALIDATED", "simulated": True},
                dry_run=True,
            )

        return ExecutionResult(
            success=False,
            platform=variant.platform,
            action_type="DEPLOY_AD_CREATIVE",
            resource_id=variant.campaign_id,
            payload_sent=payload,
            response_received={"status": "NOT_IMPLEMENTED"},
            dry_run=False,
            error=(
                "Live creative deployment is not wired yet: it requires ad set "
                "resolution plus ad + ad-creative creation on each platform. "
                "Dry-run previews the exact payload that would be dispatched."
            ),
        )

    def create_campaign(self, draft: CampaignDraft, dry_run: bool = True) -> ExecutionResult:
        """Create a new campaign (PAUSED) on the platform after human approval."""
        payload = {
            "name": draft.name,
            "platform": draft.platform.value,
            "objective": draft.objective,
            "daily_budget_inr": draft.daily_budget_inr,
            "status": draft.status,
            "channel_type": draft.channel_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if dry_run:
            return ExecutionResult(
                success=True,
                platform=draft.platform,
                action_type="CREATE_CAMPAIGN",
                resource_id=draft.name,
                payload_sent=payload,
                response_received={"status": "DRY_RUN_VALIDATED", "simulated": True},
                dry_run=True,
            )

        try:
            if draft.platform == Platform.META_ADS:
                client = self._build_meta_client()
                with httpx.Client(timeout=60.0) as http:
                    resp = http.post(
                        f"{META_BASE}/{client.ad_account_id}/campaigns",
                        data={
                            "name": draft.name,
                            "objective": draft.objective or "OUTCOME_TRAFFIC",
                            "status": "PAUSED",  # new campaigns always start paused
                            "special_ad_categories": "[]",
                            "daily_budget": int(round(draft.daily_budget_inr * 100)),
                            "access_token": client.access_token,
                        },
                    )
                if resp.status_code != 200:
                    raise MetaAdsError(
                        f"Meta campaign create failed ({resp.status_code}): {resp.text[:400]}"
                    )
                response = resp.json()
                return ExecutionResult(
                    success=True,
                    platform=draft.platform,
                    action_type="CREATE_CAMPAIGN",
                    resource_id=str(response.get("id", draft.name)),
                    payload_sent=payload,
                    response_received=response,
                    dry_run=False,
                )

            if draft.platform == Platform.GOOGLE_ADS:
                # Creating a Google campaign live requires provisioning a budget
                # resource, a bidding strategy, and ad group shells first. Until
                # those are wired, say so — never claim a campaign was created.
                raise ConnectionError(
                    "Live Google Ads campaign creation is not wired yet (needs budget "
                    "resource + bidding strategy provisioning). Budget shifts on existing "
                    "campaigns do dispatch live."
                )

            raise ConnectionError(f"No live create path for platform {draft.platform.value}")
        except Exception as exc:
            logger.error("Live campaign create failed for %s: %s", draft.name, exc)
            return ExecutionResult(
                success=False,
                platform=draft.platform,
                action_type="CREATE_CAMPAIGN",
                resource_id=draft.name,
                payload_sent=payload,
                response_received={"status": "FAILED"},
                dry_run=False,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Synthetic dev dataset (labelled synthetic — never as live)
    # ------------------------------------------------------------------

    def _sample_snapshot(self, source: str = "synthetic") -> CampaignSnapshot:
        """Structured Finnovate baseline campaigns for dev without credentials."""
        campaigns = self._sample_rows(scale=1.0)
        total_spend = sum(c.spend_inr for c in campaigns)
        blended_roas = sum(c.roas * c.spend_inr for c in campaigns) / total_spend
        return CampaignSnapshot(
            account_ids=["synthetic_dev_account"],
            platform=Platform.META_ADS,
            campaigns=campaigns,
            total_spend_inr=total_spend,
            blended_roas=round(blended_roas, 2),
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            notes="synthetic dev dataset — connect Google/Meta for live data",
        )

    def _sample_history(
        self, cur_start: date, cur_end: date, prior_start: date, prior_end: date
    ) -> list[HistoryPeriod]:
        """Synthetic two-period history exhibiting one decaying campaign."""
        return [
            HistoryPeriod(
                label="current",
                date_start=cur_start.isoformat(),
                date_end=cur_end.isoformat(),
                campaigns=self._sample_rows(scale=1.0),
                source="synthetic",
            ),
            HistoryPeriod(
                label="prior",
                date_start=prior_start.isoformat(),
                date_end=prior_end.isoformat(),
                # Prior period: fatigue campaign was healthier, top performer was smaller
                campaigns=self._sample_rows(scale=1.0, prior=True),
                source="synthetic",
            ),
        ]

    def _sample_rows(self, scale: float = 1.0, prior: bool = False) -> list[MetricRow]:
        rows = [
            MetricRow(
                campaign_id="cmp_google_search_01",
                campaign_name="Finnovate — Mutual Fund Search Intent",
                platform=Platform.GOOGLE_ADS,
                spend_inr=(38000.0 if prior else 45000.0) * scale,
                impressions=int((110000 if prior else 125000) * scale),
                clicks=int((6900 if prior else 8400) * scale),
                conversions=int((330 if prior else 420) * scale),
                roas=3.0 if prior else 3.4,
                cpa_inr=115.15 if prior else 107.14,
                ctr=6.27 if prior else 6.72,
            ),
            MetricRow(
                campaign_id="cmp_meta_prospecting_02",
                campaign_name="Finnovate — SIP Growth Retargeting",
                platform=Platform.META_ADS,
                spend_inr=(60000.0 if prior else 65000.0) * scale,
                impressions=int((320000 if prior else 340000) * scale),
                clicks=int((13500 if prior else 14200) * scale),
                conversions=int((480 if prior else 510) * scale),
                roas=2.2 if prior else 2.1,
                cpa_inr=125.0 if prior else 127.45,
                ctr=4.22 if prior else 4.17,
            ),
            MetricRow(
                campaign_id="cmp_meta_fatigue_03",
                campaign_name="Finnovate — Gold ETF Broad Audience",
                platform=Platform.META_ADS,
                spend_inr=(32000.0 if prior else 30000.0) * scale,
                impressions=int((240000 if prior else 210000) * scale),
                clicks=int((6800 if prior else 3900) * scale),
                conversions=int((190 if prior else 95) * scale),
                roas=1.9 if prior else 1.1,
                cpa_inr=168.42 if prior else 315.78,
                ctr=2.83 if prior else 1.85,
            ),
        ]
        return rows


# Preferred name for new code; `MureoConnector` stays for existing imports.
PlatformConnector = MureoConnector
