"""Direct Meta (Facebook) Marketing API client — plain `httpx`, no vendor SDK.

Reads campaign insights from `/{ad_account_id}/insights` and writes daily
budget updates to `/{campaign_id}`. Credentials expected in the secret store
under `meta_ads`: `access_token`, `ad_account_id` (the `act_...` form).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from modules.ads.contracts import CampaignSnapshot, MetricRow, Platform

logger = logging.getLogger(__name__)

META_API_VERSION = "v21.0"
META_BASE = f"https://graph.facebook.com/{META_API_VERSION}"

# Action types that count as a conversion, best first.
_CONVERSION_ACTIONS = (
    "offsite_conversion.fb_pixel_purchase",
    "purchase",
    "offsite_conversion.fb_pixel_lead",
    "lead",
    "offsite_conversion.fb_pixel_complete_registration",
    "omni_purchase",
)

_DATE_PAIR = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*(?:,|\.\.)\s*(\d{4}-\d{2}-\d{2})$")


class MetaAdsError(RuntimeError):
    """Raised when the Meta Graph API rejects a request or credentials are unusable."""


def normalize_account_id(raw: str) -> str:
    """Ensure the ad account id carries the `act_` prefix Graph expects."""
    value = str(raw or "").strip()
    if not value:
        return ""
    return value if value.startswith("act_") else f"act_{re.sub(r'[^0-9]', '', value)}"


class MetaAdsClient:
    """Minimal Meta Marketing API client covering the reads and writes HELM needs."""

    def __init__(self, access_token: str, ad_account_id: str, timeout: float = 60.0) -> None:
        self.access_token = access_token
        self.ad_account_id = normalize_account_id(ad_account_id)
        self.timeout = timeout

    @classmethod
    def from_credentials(cls, creds: dict[str, Any], timeout: float = 60.0) -> "MetaAdsClient":
        missing = [k for k in ("access_token", "ad_account_id") if not creds.get(k)]
        if missing:
            raise MetaAdsError(
                "Meta Ads credentials incomplete. Missing: "
                + ", ".join(missing)
                + ". Connect the account under Settings -> Connections."
            )
        return cls(
            access_token=str(creds["access_token"]),
            ad_account_id=str(creds["ad_account_id"]),
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "access_token": self.access_token}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{META_BASE}/{path.lstrip('/')}", params=params)
        if resp.status_code != 200:
            raise MetaAdsError(f"Meta API GET {path} failed ({resp.status_code}): {_summarize(resp)}")
        return resp.json()

    def fetch_campaign_metrics(self, date_range: str = "last_30d") -> list[MetricRow]:
        """Fetch campaign-level insights as `MetricRow`s.

        `date_range` accepts a Meta preset (`last_30d`) or `YYYY-MM-DD,YYYY-MM-DD`.
        """
        params: dict[str, Any] = {
            "level": "campaign",
            "fields": "campaign_id,campaign_name,spend,impressions,clicks,ctr,actions,action_values",
            "limit": 500,
        }
        pair = _DATE_PAIR.match((date_range or "").strip())
        if pair:
            params["time_range"] = f'{{"since":"{pair.group(1)}","until":"{pair.group(2)}"}}'
        else:
            params["date_preset"] = (date_range or "last_30d").strip() or "last_30d"

        payload = self._get(f"{self.ad_account_id}/insights", params)
        rows: list[MetricRow] = []

        for item in payload.get("data", []) or []:
            spend = float(item.get("spend", 0) or 0)
            impressions = int(float(item.get("impressions", 0) or 0))
            clicks = int(float(item.get("clicks", 0) or 0))
            conversions = _sum_actions(item.get("actions"))
            conv_value = _sum_actions(item.get("action_values"))

            rows.append(
                MetricRow(
                    campaign_id=str(item.get("campaign_id", "")),
                    campaign_name=str(item.get("campaign_name", "Unnamed Campaign")),
                    platform=Platform.META_ADS,
                    spend_inr=round(spend, 2),
                    impressions=impressions,
                    clicks=clicks,
                    conversions=int(round(conversions)),
                    roas=round(conv_value / spend, 2) if spend > 0 else 0.0,
                    cpa_inr=round(spend / conversions, 2) if conversions > 0 else 0.0,
                    ctr=round(float(item.get("ctr", 0) or 0), 2),
                    status="ENABLED",
                )
            )

        rows.sort(key=lambda r: r.spend_inr, reverse=True)
        return rows

    def fetch_snapshot(self, date_range: str = "last_30d") -> CampaignSnapshot:
        rows = self.fetch_campaign_metrics(date_range=date_range)
        total_spend = round(sum(r.spend_inr for r in rows), 2)
        blended = (
            round(sum(r.roas * r.spend_inr for r in rows) / total_spend, 2) if total_spend > 0 else 0.0
        )
        return CampaignSnapshot(
            account_ids=[self.ad_account_id],
            platform=Platform.META_ADS,
            campaigns=rows,
            total_spend_inr=total_spend,
            blended_roas=blended,
            source="live",
            timestamp=datetime.now(timezone.utc).isoformat(),
            notes=f"Meta ad account {self.ad_account_id}, range {date_range}",
        )

    def verify(self) -> dict[str, Any]:
        """Connectivity probe for the Settings screen."""
        payload = self._get(self.ad_account_id, {"fields": "name,account_status,currency,timezone_name"})
        return {
            "connected": True,
            "ad_account_id": self.ad_account_id,
            "name": payload.get("name", ""),
            "currency": payload.get("currency", ""),
            "time_zone": payload.get("timezone_name", ""),
        }

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def update_campaign_budget(self, campaign_id: str, new_daily_budget: float) -> dict[str, Any]:
        """Set a campaign daily budget. Meta takes minor currency units (paise for INR)."""
        minor_units = int(round(float(new_daily_budget) * 100))
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{META_BASE}/{campaign_id}",
                data={"daily_budget": minor_units, "access_token": self.access_token},
            )
        if resp.status_code != 200:
            raise MetaAdsError(
                f"Meta campaign budget update failed ({resp.status_code}): {_summarize(resp)}"
            )
        return resp.json()


def _sum_actions(actions: Any) -> float:
    """Sum the best-matching conversion action bucket from a Meta actions array."""
    if not isinstance(actions, list):
        return 0.0
    by_type = {
        str(a.get("action_type", "")): float(a.get("value", 0) or 0)
        for a in actions
        if isinstance(a, dict)
    }
    for action_type in _CONVERSION_ACTIONS:
        if action_type in by_type:
            return by_type[action_type]
    return 0.0


def _summarize(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except Exception:
        return resp.text[:400]
    error = data.get("error", data) if isinstance(data, dict) else data
    if isinstance(error, dict):
        return str(error.get("message") or error)[:400]
    return str(error)[:400]
