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

    # Task -> ModelRef routing table
    task_routing: dict[TaskKind, ModelRef] = None

    def __post_init__(self) -> None:
        if self.task_routing is None:
            active_provider = get_active_provider()
            primary_model = get_model_for_provider(active_provider, fast=False)
            fast_model = get_model_for_provider(active_provider, fast=True)

            default_routing = {
                TaskKind.ANALYST_ANSWER: ModelRef(provider=active_provider, model=primary_model),
                TaskKind.ANALYST_ROUTE: ModelRef(provider=active_provider, model=fast_model),
                TaskKind.MEDIA_BUYER_PROPOSAL: ModelRef(provider=active_provider, model=primary_model),
                TaskKind.CREATIVE_VARIANTS: ModelRef(provider=active_provider, model=primary_model),
                TaskKind.GOVERNOR_PLAN: ModelRef(provider=active_provider, model=primary_model),
                TaskKind.COMPLIANCE_EVAL: ModelRef(provider=active_provider, model=primary_model),
            }
            object.__setattr__(self, "task_routing", default_routing)

    def route_task(self, task: TaskKind, replay_mode: bool = False) -> ModelRef:
        """Resolve a task to a provider and model."""
        if replay_mode:
            return ModelRef(provider="replay", model="mock-fast")
        active_provider = get_active_provider()
        primary_model = get_model_for_provider(active_provider, fast=False)
        return self.task_routing.get(task, ModelRef(provider=active_provider, model=primary_model))

