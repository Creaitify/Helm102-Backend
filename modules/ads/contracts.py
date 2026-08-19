"""Ad-Platform contracts and data models for HELM02."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Platform(StrEnum):
    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"
    TIKTOK_ADS = "tiktok_ads"
    LINKEDIN_ADS = "linkedin_ads"
    BYOD = "byod"


@dataclass(frozen=True, slots=True)
class MetricRow:
    """Standardized performance metrics for a campaign or ad set."""

    campaign_id: str
    campaign_name: str
    platform: Platform
    spend_inr: float
    impressions: int
    clicks: int
    conversions: int
    roas: float
    cpa_inr: float
    ctr: float
    status: str = "ENABLED"


@dataclass(frozen=True, slots=True)
class CampaignSnapshot:
    """Full snapshot of ingested ad accounts."""

    account_ids: list[str]
    platform: Platform
    campaigns: list[MetricRow]
    total_spend_inr: float
    blended_roas: float
    source: str = "live"  # "live" | "byod" | "synthetic" | "degraded"
    timestamp: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class HistoryPeriod:
    """Performance metrics for one labelled past period (for trend analysis)."""

    label: str  # e.g. "last_30d" | "prior_30d"
    date_start: str  # YYYY-MM-DD
    date_end: str  # YYYY-MM-DD
    campaigns: list[MetricRow]
    source: str = "live"


@dataclass(frozen=True, slots=True)
class CampaignDraft:
    """A proposed NEW campaign, created only after human approval (PAUSED by default)."""

    name: str
    platform: Platform
    objective: str  # Meta objective (OUTCOME_TRAFFIC, ...) or Google intent note
    daily_budget_inr: float
    rationale: str
    channel_type: str = "SEARCH"  # google_ads only: SEARCH | DISPLAY
    status: str = "PAUSED"


@dataclass(frozen=True, slots=True)
class BudgetShift:
    """Proposed budget change."""

    campaign_id: str
    platform: Platform
    current_daily_budget_inr: float
    proposed_daily_budget_inr: float
    shift_percentage: float
    rationale: str


@dataclass(frozen=True, slots=True)
class CreativeVariant:
    """Ad creative copy and media to deploy."""

    campaign_id: str
    platform: Platform
    headline: str
    primary_text: str
    call_to_action: str
    video_url: str | None = None
    image_url: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Outcome of platform dispatch."""

    success: bool
    platform: Platform
    action_type: str
    resource_id: str
    payload_sent: dict[str, Any]
    response_received: dict[str, Any]
    dry_run: bool = True
    error: str | None = None
