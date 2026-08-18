"""Base adapter protocol and types for LLM providers."""

from __future__ import annotations

from typing import Protocol
from services.api.gateway.contracts import CompletionRequest, CompletionResponse, ModelRef


class ModelAdapter(Protocol):
    """Protocol implemented by concrete provider adapters."""

    async def generate(self, request: CompletionRequest, model: ModelRef) -> CompletionResponse:
        """Execute model generation."""
        ...
