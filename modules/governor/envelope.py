"""Typed Handoff Envelope for star-relay orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class EnvelopeStatus(StrEnum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"
    NEEDS_REVISION = "needs_revision"


@dataclass(frozen=True, slots=True)
class HandoffEnvelope:
    """Standardized envelope passed between Governor and workers."""

    hop_index: int
    source: str
    target: str
    action: str
    status: EnvelopeStatus
    payload: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "hop_index": self.hop_index,
            "source": self.source,
            "target": self.target,
            "action": self.action,
            "status": self.status.value,
            "payload": self.payload,
            "rationale": self.rationale,
            "error": self.error,
            "timestamp": self.timestamp,
        }
