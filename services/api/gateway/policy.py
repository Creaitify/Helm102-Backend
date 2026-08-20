"""Routing table, model whitelist, and daily spend limits."""

from __future__ import annotations

from dataclasses import dataclass
from services.api.gateway.contracts import ModelRef, TaskKind
from services.api.gateway.keys import get_active_provider, get_model_for_provider


@dataclass(frozen=True, slots=True)
class GatewayPolicy:
    """Configured limits and model routing."""

    daily_spend_limit_microdollars: int = 50_000_000  # $50 USD
    max_tokens_per_request: int = 8192
    kill_switch_active: bool = False

    # Task -> ModelRef routing table (optional custom override)
    task_routing: dict[TaskKind, ModelRef] | None = None

    def route_task(self, task: TaskKind, replay_mode: bool = False) -> ModelRef:
        """Resolve a task to a provider and model."""
        if replay_mode:
            return ModelRef(provider="replay", model="mock-fast")
        if self.task_routing and task in self.task_routing:
            return self.task_routing[task]
        active_provider = get_active_provider()
        is_fast = task == TaskKind.ANALYST_ROUTE
        model_name = get_model_for_provider(active_provider, fast=is_fast)
        return ModelRef(provider=active_provider, model=model_name)

