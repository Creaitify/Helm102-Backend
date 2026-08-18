"""Ad-Platform Connector Protocol and Mureo wrapper.

This is the SOLE module permitted to import `mureo`.

Design rules enforced here:
- Real platform calls go through mureo clients built from `HelmSecretStore`
  credentials (Google Cloud Console OAuth client + refresh token for Google,
  Graph API access token for Meta). No `~/.mureo/` access, ever.
- Data is always labelled honestly: `live` only when it actually came from a
  platform API; `synthetic` for the built-in dev dataset; `byod` for imported
  files; `degraded` when a live fetch failed.
- Live writes either dispatch through mureo or fail with success=False.
  Nothing ever fabricates an "APPLIED" response.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
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
from services.api.auth.secret_store import HelmSecretStore

logger = logging.getLogger(__name__)

_GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


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


def _run_async(coro: Any) -> Any:
    """Run a mureo coroutine from sync code, safe inside or outside a loop.

    mureo clients are async; the Connector protocol is sync so the Governor,
    executor, and tests stay simple. A dedicated thread with its own event
    loop avoids `asyncio.run()` blowing up when we're already inside FastAPI's
    running loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class MureoConnector:
    """Connector implementation backed by logly/mureo."""

    def __init__(self, secret_store: HelmSecretStore | None = None) -> None:
        self.secret_store = secret_store or HelmSecretStore()

    # ------------------------------------------------------------------
    # Client construction (Google Cloud Console OAuth / Meta Graph token)
    # ------------------------------------------------------------------

    def _build_google_client(self) -> Any:
        """Build mureo GoogleAdsApiClient from server-side custody credentials.

        Expected keys under `google_ads` in the secret store (all obtained
        from Google Cloud Console + Google Ads API Center):
          client_id, client_secret, refresh_token, developer_token,
          customer_id, login_customer_id (optional, for MCC accounts)
        """
        creds = self.secret_store.load("google_ads")
        required = ("client_id", "client_secret", "refresh_token", "developer_token", "customer_id")
        missing = [k for k in required if not creds.get(k)]
        if missing:
            raise ConnectionError(f"google_ads credentials incomplete, missing: {', '.join(missing)}")

        from google.oauth2.credentials import Credentials  # transitive dep of mureo's google-ads SDK
        from mureo.google_ads.client import GoogleAdsApiClient

        oauth_credentials = Credentials(
            token=None,
            refresh_token=creds["refresh_token"],
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            token_uri=_GOOGLE_TOKEN_URI,
        )
        return GoogleAdsApiClient(
            credentials=oauth_credentials,
            customer_id=str(creds["customer_id"]),
            developer_token=creds["developer_token"],
            login_customer_id=creds.get("login_customer_id") or None,
        )

    def _build_meta_client(self) -> Any:
        """Build mureo MetaAdsApiClient from server-side custody credentials.

        Expected keys under `meta_ads`: access_token, ad_account_id (act_...).
        """
        creds = self.secret_store.load("meta_ads")
        if not creds.get("access_token") or not creds.get("ad_account_id"):
            raise ConnectionError("meta_ads credentials incomplete, need access_token and ad_account_id")

        from mureo.meta_ads.client import MetaAdsApiClient

        return MetaAdsApiClient(
            access_token=creds["access_token"],
            ad_account_id=creds["ad_account_id"],
        )

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
        """Fetch campaign metrics. Live via mureo when connected, else synthetic."""
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
                        self._fetch_google_rows(f"BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'")
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
        """list_campaigns + performance report merged into MetricRows."""
        client = self._build_google_client()

        async def _fetch() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            campaigns = await client.list_campaigns(status_filter="ENABLED")
            report = await client.get_performance_report(period=period)
            return campaigns, report

        campaigns, report = _run_async(_fetch())
        perf_by_id = {str(r.get("campaign_id")): r.get("metrics", {}) for r in report}

        rows: list[MetricRow] = []
        for camp in campaigns:
            cid = str(camp.get("id") or camp.get("campaign_id") or "")
            m = perf_by_id.get(cid, {})
            spend = float(m.get("cost", 0.0))
            conversions = float(m.get("conversions", 0.0))
            cpa = round(spend / conversions, 2) if conversions > 0 else 0.0
            rows.append(
                MetricRow(
                    campaign_id=cid,
                    campaign_name=str(camp.get("name", cid)),
                    platform=Platform.GOOGLE_ADS,
                    spend_inr=spend,
                    impressions=int(m.get("impressions", 0)),
                    clicks=int(m.get("clicks", 0)),
                    conversions=int(conversions),
                    # ROAS needs conversion value; the report carries cost per
                    # conversion, so we surface conversions/cost efficiency and
                    # leave roas 0.0 until conversion value tracking is wired.
                    roas=0.0,
                    cpa_inr=cpa,
                    ctr=round(float(m.get("ctr", 0.0)) * 100, 2),
                    status=str(camp.get("status", "ENABLED")),
                )
            )
        return rows

    def _fetch_meta_rows(self, period: str) -> list[MetricRow]:
        """Meta account-level campaign insights into MetricRows."""
        client = self._build_meta_client()

        async def _fetch() -> list[dict[str, Any]]:
            try:
                return await client.get_performance_report(period=period, level="campaign")
            finally:
                await client.close()

        insights = _run_async(_fetch())

        rows: list[MetricRow] = []
        for ins in insights:
            spend = float(ins.get("spend", 0.0) or 0.0)
            clicks = int(ins.get("clicks", 0) or 0)
            impressions = int(ins.get("impressions", 0) or 0)
            conversions = _meta_action_count(ins.get("actions"), "offsite_conversion")
            cpa = round(spend / conversions, 2) if conversions > 0 else 0.0
            rows.append(
                MetricRow(
                    campaign_id=str(ins.get("campaign_id", "")),
                    campaign_name=str(ins.get("campaign_name", "")),
                    platform=Platform.META_ADS,
                    spend_inr=spend,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    roas=0.0,  # purchase ROAS requires value tracking; wired later
                    cpa_inr=cpa,
                    ctr=float(ins.get("ctr", 0.0) or 0.0),
                )
            )
        return rows

    # ------------------------------------------------------------------
    # Writes — dispatch through mureo or fail honestly. Never fabricate.
    # ------------------------------------------------------------------

    def apply_budget(self, shift: BudgetShift, dry_run: bool = True) -> ExecutionResult:
        """Execute budget shift via mureo or dry-run preview."""
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
                client = self._build_meta_client()

                async def _apply_meta() -> dict[str, Any]:
                    try:
                        # Meta daily_budget is in the currency's minor units (paise for INR)
                        return await client.update_campaign(
                            shift.campaign_id,
                            daily_budget=int(round(shift.proposed_daily_budget_inr * 100)),
                        )
                    finally:
                        await client.close()

                response = _run_async(_apply_meta())
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
                client = self._build_google_client()

                async def _apply_google() -> dict[str, Any]:
                    # Google budgets are separate resources: resolve the
                    # campaign's real budget id first — no templated ids.
                    campaigns = await client.list_campaigns()
                    budget_resource = next(
                        (
                            c.get("campaign_budget")
                            for c in campaigns
                            if str(c.get("id") or c.get("campaign_id")) == str(shift.campaign_id)
                        ),
                        None,
                    )
                    if not budget_resource:
                        raise RuntimeError(
                            f"No campaign_budget resource found for campaign {shift.campaign_id}"
                        )
                    match = re.search(r"campaignBudgets/(\d+)", str(budget_resource))
                    if not match:
                        raise RuntimeError(f"Unrecognized budget resource: {budget_resource}")
                    return await client.update_budget(
                        {"budget_id": match.group(1), "amount": shift.proposed_daily_budget_inr}
                    )

                response = _run_async(_apply_google())
                return ExecutionResult(
                    success=True,
                    platform=shift.platform,
                    action_type="UPDATE_CAMPAIGN_BUDGET",
                    resource_id=str(response.get("resource_name", shift.campaign_id)),
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
        (mureo's creatives/ads mixins). Until that is wired, the live path
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
                "Live creative deployment is not wired yet: requires ad set "
                "resolution and ad creation via mureo creatives/ads APIs."
            ),
        )

    def create_campaign(self, draft: CampaignDraft, dry_run: bool = True) -> ExecutionResult:
        """Create a new campaign (PAUSED) via mureo after human approval."""
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

                async def _create_meta() -> dict[str, Any]:
                    try:
                        return await client.create_campaign(
                            name=draft.name,
                            objective=draft.objective or "OUTCOME_TRAFFIC",
                            status="PAUSED",  # new campaigns always start paused
                            daily_budget=int(round(draft.daily_budget_inr * 100)),
                        )
                    finally:
                        await client.close()

                response = _run_async(_create_meta())
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
                client = self._build_google_client()
                response = _run_async(
                    client.create_campaign({"name": draft.name, "channel_type": draft.channel_type})
                )
                return ExecutionResult(
                    success=True,
                    platform=draft.platform,
                    action_type="CREATE_CAMPAIGN",
                    resource_id=str(response.get("resource_name", draft.name)),
                    payload_sent=payload,
                    response_received=response,
                    dry_run=False,
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


def _meta_action_count(actions: Any, action_prefix: str) -> int:
    """Sum Meta insight `actions` entries whose action_type starts with prefix."""
    if not isinstance(actions, list):
        return 0
    total = 0.0
    for entry in actions:
        if isinstance(entry, dict) and str(entry.get("action_type", "")).startswith(action_prefix):
            try:
                total += float(entry.get("value", 0))
            except (TypeError, ValueError):
                continue
    return int(total)
