"""Provider-neutral request, response and usage types.

This module is the model gateway boundary. It is pure: no SDK imports or vendor locks.
Money is integer micro-dollars throughout. Floating point is never used for costs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum


class TaskKind(StrEnum):
    """Logical capabilities a caller may request."""

    ANALYST_ANSWER = "analyst.answer"
    ANALYST_ROUTE = "analyst.route"
    MEDIA_BUYER_PROPOSAL = "media_buyer.proposal"
    CREATIVE_VARIANTS = "creative.variants"
    GOVERNOR_PLAN = "governor.plan"
    COMPLIANCE_EVAL = "compliance.eval"


class Role(StrEnum):
    """Conversation roles the gateway accepts."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class StopReason(StrEnum):
    """Why generation stopped."""

    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    TOOL_USE = "tool_use"
    REFUSAL = "refusal"


class Effort(StrEnum):
    """How much reasoning depth and token spend a task warrants."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


@dataclass(frozen=True, slots=True)
class Message:
    """One conversation turn."""

    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class ModelRef:
    """A concrete provider and model, resolved from a task by the routing table."""

    provider: str
    model: str


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    """A provider-neutral generation request."""

    task: TaskKind
    messages: Sequence[Message]
    system_cacheable: str = ""
    system_volatile: str = ""
    max_tokens: int = 4096
    effort: Effort = Effort.HIGH
    json_schema: Mapping[str, object] | None = None
    request_id: str = ""


@dataclass(frozen=True, slots=True)
class Usage:
    """Token consumption and costs reported by provider."""

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cost_microdollars: int = 0


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    """A provider-neutral generation response."""

    content: str
    stop_reason: StopReason
    model: ModelRef
    usage: Usage
    request_id: str
    raw_response: Mapping[str, object] = field(default_factory=dict)
