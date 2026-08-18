"""Replay adapter returning deterministic responses for tests and dry-runs."""

from __future__ import annotations

import json
from services.api.gateway.contracts import (
    CompletionRequest,
    CompletionResponse,
    ModelRef,
    StopReason,
    Usage,
)


class ReplayAdapter:
    """Mock/replay adapter producing structured responses deterministically."""

    def __init__(self, canned_response: str | None = None) -> None:
        self.canned_response = canned_response

    async def generate(self, request: CompletionRequest, model: ModelRef) -> CompletionResponse:
        """Return deterministic replay response."""
        content = self.canned_response or f"[Replay response for task {request.task.value}]"
        
        usage = Usage(
            input_tokens=100,
            output_tokens=50,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            cost_microdollars=150,
        )

        return CompletionResponse(
            content=content,
            stop_reason=StopReason.END_TURN,
            model=model,
            usage=usage,
            request_id=request.request_id,
        )
