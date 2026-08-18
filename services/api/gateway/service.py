"""Gateway service providing controlled LLM egress."""

from __future__ import annotations

import uuid
from typing import Any
from services.api.gateway.adapters.anthropic import AnthropicAdapter
from services.api.gateway.adapters.base import ModelAdapter
from services.api.gateway.adapters.gemini import GeminiAdapter
from services.api.gateway.adapters.replay import ReplayAdapter
from services.api.gateway.contracts import (
    CompletionRequest,
    CompletionResponse,
    ModelRef,
)
from services.api.gateway.errors import AdapterError
from services.api.gateway.ledger import BudgetLedger
from services.api.gateway.policy import GatewayPolicy


class GatewayService:
    """The single point of egress for all model invocations in HELM02."""

    def __init__(
        self,
        policy: GatewayPolicy | None = None,
        adapters: dict[str, ModelAdapter] | None = None,
        replay_mode: bool = False,
    ) -> None:
        self.policy = policy or GatewayPolicy()
        self.ledger = BudgetLedger(self.policy)
        self.replay_mode = replay_mode
        self._adapters: dict[str, ModelAdapter] = adapters or {
            "gemini": GeminiAdapter(),
            "anthropic": AnthropicAdapter(),
            "replay": ReplayAdapter(),
        }


    def register_adapter(self, provider: str, adapter: ModelAdapter) -> None:
        self._adapters[provider] = adapter

    async def generate(self, request: CompletionRequest) -> CompletionResponse:
        """Reserve budget, route task, call provider adapter, reconcile cost."""
        req_id = request.request_id or f"req_{uuid.uuid4().hex[:12]}"
        model = self.policy.route_task(request.task, replay_mode=self.replay_mode)

        # Estimate reservation cost based on max_tokens
        estimated_cost = request.max_tokens * 15  # worst-case micro-dollars estimation
        await self.ledger.reserve(req_id, estimated_cost)

        adapter = self._adapters.get(model.provider)
        if not adapter:
            await self.ledger.release(req_id)
            raise AdapterError(f"No adapter registered for provider: {model.provider}")

        try:
            response = await adapter.generate(request, model)
            await self.ledger.reconcile(req_id, response.usage.cost_microdollars)
            return response
        except Exception:
            await self.ledger.release(req_id)
            raise
