"""SQLAlchemy database models for HELM02."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class RunModel(Base):
    """Database model for Governor orchestration runs.

    Stores run state, objective, status, proposal JSON, execution results JSON,
    tenant_id, created_at, and updated_at.
    """

    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(128), default="default", index=True, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="pending", index=True, nullable=False)
    proposal: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    execution_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary representation."""
        return {
            "run_id": self.run_id,
            "tenant_id": self.tenant_id,
            "objective": self.objective,
            "status": self.status,
            "proposal": self.proposal if self.proposal is not None else {},
            "execution_results": self.execution_results if self.execution_results is not None else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AuditEventModel(Base):
    """Database model for immutable audit events across orchestration hops.

    Stores hop sequence, envelope metadata, status, payload JSON, rationale, error,
    and timestamp.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    hop_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    target: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert audit event to dictionary representation."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "hop_index": self.hop_index,
            "source": self.source,
            "target": self.target,
            "action": self.action,
            "status": self.status,
            "payload": self.payload_json,
            "payload_json": self.payload_json,
            "rationale": self.rationale,
            "error": self.error,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class CampaignModel(Base):
    """Database model for ad campaigns across platforms.

    Stores campaign_id, name, platform, spend, roas, cpa, status, tenant_id, and updated_at.
    """

    __tablename__ = "campaigns"

    campaign_id: Mapped[str] = mapped_column(String(128), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    spend: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    roas: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cpa: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="ENABLED", nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(128), default="default", index=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert campaign model to dictionary representation."""
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "platform": self.platform,
            "spend": self.spend,
            "roas": self.roas,
            "cpa": self.cpa,
            "status": self.status,
            "tenant_id": self.tenant_id,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
