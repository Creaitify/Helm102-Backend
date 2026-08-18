"""Gated platform execution engine with dry-run support."""

from __future__ import annotations

import logging
import os
from typing import Any
from modules.ads.connector import Connector, MureoConnector
from modules.ads.contracts import (
    BudgetShift,
    CampaignDraft,
    CreativeVariant,
    ExecutionResult,
    Platform,
)
from modules.audit.trail import AuditTrail
from modules.governor.envelope import EnvelopeStatus, HandoffEnvelope

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Dispatches approved marketing actions strictly behind human approval."""

    def __init__(
        self,
        connector: Connector | None = None,
        audit_trail: AuditTrail | None = None,
        dry_run: bool | None = None,
    ) -> None:
        self.connector = connector or MureoConnector()
        self.audit_trail = audit_trail or AuditTrail()
        if dry_run is None:
            # Default to dry-run true unless explicitly disabled in env
            self.dry_run = os.environ.get("HELM_ADS_DRY_RUN", "true").lower() == "true"
        else:
            self.dry_run = dry_run

    def execute_proposal(
        self,
        run_id: str,
        proposal: dict[str, Any],
        human_decision: str,
        decision_notes: str = "",
    ) -> list[ExecutionResult]:
        """Execute proposal if approved, otherwise record rejection."""
        if human_decision.lower() != "approved":
            logger.info("Run %s rejected by human operator. Execution skipped.", run_id)
            envelope = HandoffEnvelope(
                hop_index=99,
                source="ExecutionEngine",
                target="Governor",
                action="REJECTED_BY_OPERATOR",
                status=EnvelopeStatus.SUCCESS,
                payload={"run_id": run_id, "reason": decision_notes},
                rationale="Human rejected proposal. No platform actions dispatched.",
            )
            self.audit_trail.record(run_id, envelope)
            return []

        results: list[ExecutionResult] = []
        shifts = proposal.get("budget_shifts", [])
        creative = proposal.get("creative_package", {})

        # 1. Execute Budget Shifts
        for raw_shift in shifts:
            p_val = raw_shift.get("platform", Platform.META_ADS)
            platform_enum = Platform(p_val) if isinstance(p_val, str) else p_val
            shift = BudgetShift(
                campaign_id=raw_shift["campaign_id"],
                platform=platform_enum,
                current_daily_budget_inr=raw_shift["current_daily_budget_inr"],
                proposed_daily_budget_inr=raw_shift["proposed_daily_budget_inr"],
                shift_percentage=raw_shift["shift_percentage"],
                rationale=raw_shift.get("rationale", ""),
            )
            res = self.connector.apply_budget(shift, dry_run=self.dry_run)
            results.append(res)

            p_str = res.platform.value if hasattr(res.platform, "value") else str(res.platform)
            envelope = HandoffEnvelope(
                hop_index=len(results),
                source="ExecutionEngine",
                target=f"AdPlatform:{p_str}",
                action=res.action_type,
                status=EnvelopeStatus.SUCCESS if res.success else EnvelopeStatus.FAILED,
                payload={
                    "resource_id": res.resource_id,
                    "payload_sent": res.payload_sent,
                    "response": res.response_received,
                    "dry_run": res.dry_run,
                },
                rationale=f"Applied approved budget shift for {shift.campaign_id}",
            )
            self.audit_trail.record(run_id, envelope)

        # 2. Deploy Creative if specified
        if creative and "creative" in creative:
            c = creative["creative"]
            first_shift = shifts[0] if shifts else {}
            p_val = first_shift.get("platform", Platform.META_ADS)
            platform_enum = Platform(p_val) if isinstance(p_val, str) else p_val
            variant = CreativeVariant(
                campaign_id=first_shift.get("campaign_id", "cmp_meta_prospecting_02"),
                platform=platform_enum,
                headline=c.get("headline", ""),
                primary_text=c.get("primary_text", ""),
                call_to_action=c.get("call_to_action", "Learn More"),
            )
            res = self.connector.deploy_creative(variant, dry_run=self.dry_run)
            results.append(res)

            p_str = res.platform.value if hasattr(res.platform, "value") else str(res.platform)
            envelope = HandoffEnvelope(
                hop_index=len(results),
                source="ExecutionEngine",
                target=f"AdPlatform:{p_str}",
                action=res.action_type,
                status=EnvelopeStatus.SUCCESS if res.success else EnvelopeStatus.FAILED,
                payload={
                    "resource_id": res.resource_id,
                    "payload_sent": res.payload_sent,
                    "response": res.response_received,
                    "dry_run": res.dry_run,
                },
                rationale=f"Deployed approved creative variant for {variant.campaign_id}",
            )
            self.audit_trail.record(run_id, envelope)

        # 3. Create approved new campaign drafts (always PAUSED on the platform)
        for raw_draft in proposal.get("campaign_drafts", []):
            try:
                p_val = raw_draft.get("platform", Platform.META_ADS)
                draft = CampaignDraft(
                    name=raw_draft["name"],
                    platform=Platform(p_val) if isinstance(p_val, str) else p_val,
                    objective=raw_draft.get("objective", ""),
                    daily_budget_inr=float(raw_draft.get("daily_budget_inr", 0.0)),
                    rationale=raw_draft.get("rationale", ""),
                    channel_type=raw_draft.get("channel_type", "SEARCH"),
                )
            except (KeyError, ValueError) as exc:
                logger.error("Skipping malformed campaign draft %s: %s", raw_draft, exc)
                continue

            res = self.connector.create_campaign(draft, dry_run=self.dry_run)
            results.append(res)

            p_str = res.platform.value if hasattr(res.platform, "value") else str(res.platform)
            envelope = HandoffEnvelope(
                hop_index=len(results),
                source="ExecutionEngine",
                target=f"AdPlatform:{p_str}",
                action=res.action_type,
                status=EnvelopeStatus.SUCCESS if res.success else EnvelopeStatus.FAILED,
                payload={
                    "resource_id": res.resource_id,
                    "payload_sent": res.payload_sent,
                    "response": res.response_received,
                    "dry_run": res.dry_run,
                },
                rationale=f"Created approved campaign draft '{draft.name}' (PAUSED)",
            )
            self.audit_trail.record(run_id, envelope)

        return results
