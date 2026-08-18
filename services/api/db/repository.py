"""Repositories for Runs, Audit Events, and Campaigns in HELM02."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.governor.envelope import HandoffEnvelope
from services.api.db.models import AuditEventModel, CampaignModel, RunModel


class RunRepository:
    """Repository handling CRUD operations and queries for Governor orchestration runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(
        self,
        run_id: str,
        objective: str,
        tenant_id: str = "default",
        status: str = "pending",
        proposal: dict[str, Any] | None = None,
        execution_results: list[dict[str, Any]] | None = None,
    ) -> RunModel:
        """Create and persist a new orchestration run."""
        run = RunModel(
            run_id=run_id,
            tenant_id=tenant_id,
            objective=objective,
            status=status,
            proposal=proposal if proposal is not None else {},
            execution_results=execution_results if execution_results is not None else [],
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: str, tenant_id: str | None = None) -> RunModel | None:
        """Fetch a single run by run_id, optionally scoped to tenant_id."""
        stmt = select(RunModel).where(RunModel.run_id == run_id)
        if tenant_id is not None:
            stmt = stmt.where(RunModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_run(
        self,
        run_id: str,
        status: str | None = None,
        proposal: dict[str, Any] | None = None,
        execution_results: list[dict[str, Any]] | None = None,
        objective: str | None = None,
        tenant_id: str | None = None,
    ) -> RunModel | None:
        """Update existing run fields and touch updated_at."""
        run = await self.get_run(run_id, tenant_id=tenant_id)
        if not run:
            return None

        if status is not None:
            run.status = status
        if proposal is not None:
            run.proposal = proposal
        if execution_results is not None:
            run.execution_results = execution_results
        if objective is not None:
            run.objective = objective
        run.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        return run

    async def upsert_run(
        self,
        run_id: str,
        objective: str,
        tenant_id: str = "default",
        status: str = "pending",
        proposal: dict[str, Any] | None = None,
        execution_results: list[dict[str, Any]] | None = None,
    ) -> RunModel:
        """Create or update a run."""
        existing = await self.get_run(run_id, tenant_id=tenant_id)
        if existing:
            return await self.update_run(
                run_id=run_id,
                status=status,
                proposal=proposal,
                execution_results=execution_results,
                objective=objective,
                tenant_id=tenant_id,
            )  # type: ignore[return-value]
        return await self.create_run(
            run_id=run_id,
            objective=objective,
            tenant_id=tenant_id,
            status=status,
            proposal=proposal,
            execution_results=execution_results,
        )

    async def list_runs(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunModel]:
        """List runs with optional filtering by tenant and status, ordered by created_at desc."""
        stmt = select(RunModel)
        if tenant_id is not None:
            stmt = stmt.where(RunModel.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(RunModel.status == status)

        stmt = stmt.order_by(RunModel.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_run(self, run_id: str, tenant_id: str | None = None) -> bool:
        """Delete a run by run_id."""
        stmt = delete(RunModel).where(RunModel.run_id == run_id)
        if tenant_id is not None:
            stmt = stmt.where(RunModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0


class AuditRepository:
    """Repository handling append-only writes and chronological reads for audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_event(
        self,
        run_id: str,
        hop_index: int,
        source: str,
        target: str,
        action: str,
        status: str,
        payload_json: dict[str, Any] | str,
        rationale: str | None = None,
        error: str | None = None,
        timestamp: datetime | None = None,
    ) -> AuditEventModel:
        """Append a new audit event record."""
        payload = (
            json.loads(payload_json)
            if isinstance(payload_json, str)
            else payload_json
        )
        event = AuditEventModel(
            run_id=run_id,
            hop_index=hop_index,
            source=source,
            target=target,
            action=action,
            status=status,
            payload_json=payload,
            rationale=rationale,
            error=error,
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def record_envelope(self, run_id: str, envelope: HandoffEnvelope) -> AuditEventModel:
        """Append an envelope to the audit log directly from a HandoffEnvelope dataclass."""
        ts = None
        if envelope.timestamp:
            try:
                ts = datetime.fromisoformat(envelope.timestamp)
            except Exception:
                ts = None

        return await self.record_event(
            run_id=run_id,
            hop_index=envelope.hop_index,
            source=envelope.source,
            target=envelope.target,
            action=envelope.action,
            status=envelope.status.value if hasattr(envelope.status, "value") else str(envelope.status),
            payload_json=envelope.payload,
            rationale=envelope.rationale,
            error=envelope.error,
            timestamp=ts,
        )

    async def get_trail(self, run_id: str) -> list[AuditEventModel]:
        """Retrieve full chronological audit trail for a run, ordered by hop_index and id ascending."""
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.run_id == run_id)
            .order_by(AuditEventModel.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_events(
        self,
        run_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventModel]:
        """List audit events with optional run_id filter."""
        stmt = select(AuditEventModel)
        if run_id is not None:
            stmt = stmt.where(AuditEventModel.run_id == run_id)
        stmt = stmt.order_by(AuditEventModel.id.asc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CampaignRepository:
    """Repository handling CRUD and queries for Ad Campaign records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_campaign(
        self,
        campaign_id: str,
        name: str,
        platform: str,
        spend: float = 0.0,
        roas: float = 0.0,
        cpa: float = 0.0,
        status: str = "ENABLED",
        tenant_id: str = "default",
    ) -> CampaignModel:
        """Create or update a campaign."""
        stmt = select(CampaignModel).where(
            CampaignModel.campaign_id == campaign_id,
            CampaignModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        campaign = result.scalar_one_or_none()

        if campaign:
            campaign.name = name
            campaign.platform = platform
            campaign.spend = spend
            campaign.roas = roas
            campaign.cpa = cpa
            campaign.status = status
            campaign.updated_at = datetime.now(timezone.utc)
        else:
            campaign = CampaignModel(
                campaign_id=campaign_id,
                name=name,
                platform=platform,
                spend=spend,
                roas=roas,
                cpa=cpa,
                status=status,
                tenant_id=tenant_id,
            )
            self.session.add(campaign)

        await self.session.flush()
        return campaign

    async def get_campaign(self, campaign_id: str, tenant_id: str = "default") -> CampaignModel | None:
        """Fetch campaign by campaign_id and tenant_id."""
        stmt = select(CampaignModel).where(
            CampaignModel.campaign_id == campaign_id,
            CampaignModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_campaigns(
        self,
        platform: str | None = None,
        tenant_id: str = "default",
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CampaignModel]:
        """List campaigns with optional filters."""
        stmt = select(CampaignModel).where(CampaignModel.tenant_id == tenant_id)
        if platform is not None:
            stmt = stmt.where(CampaignModel.platform == platform)
        if status is not None:
            stmt = stmt.where(CampaignModel.status == status)

        stmt = stmt.order_by(CampaignModel.updated_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_upsert(
        self,
        campaigns: list[dict[str, Any]],
        tenant_id: str = "default",
    ) -> list[CampaignModel]:
        """Bulk create or update multiple campaign records."""
        results = []
        for c in campaigns:
            model = await self.upsert_campaign(
                campaign_id=c["campaign_id"],
                name=c["name"],
                platform=c["platform"],
                spend=float(c.get("spend", 0.0)),
                roas=float(c.get("roas", 0.0)),
                cpa=float(c.get("cpa", 0.0)),
                status=c.get("status", "ENABLED"),
                tenant_id=tenant_id,
            )
            results.append(model)
        return results

    async def delete_campaign(self, campaign_id: str, tenant_id: str = "default") -> bool:
        """Delete a campaign by ID and tenant_id."""
        stmt = delete(CampaignModel).where(
            CampaignModel.campaign_id == campaign_id,
            CampaignModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0
