"""Rate card in integer micro-dollars per token.

1 USD = 1,000,000 micro-dollars.
"""

from __future__ import annotations

from dataclasses import dataclass
from services.api.gateway.contracts import ModelRef, Usage


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Pricing per million tokens in USD, stored as micro-dollars per 1 token."""

    input_micro_per_token: int
    output_micro_per_token: int
    cache_read_micro_per_token: int = 0
    cache_write_micro_per_token: int = 0


# Rate card definitions in micro-dollars per 1 token
_RATE_CARD: dict[str, ModelPrice] = {
    "claude-3-5-sonnet-20241022": ModelPrice(
        input_micro_per_token=3,
        output_micro_per_token=15,
        cache_read_micro_per_token=1,
        cache_write_micro_per_token=4,
    ),
    "claude-3-5-haiku-20241022": ModelPrice(
        input_micro_per_token=1,
        output_micro_per_token=5,
        cache_read_micro_per_token=1,
        cache_write_micro_per_token=1,
    ),
    "claude-3-opus-20240229": ModelPrice(
        input_micro_per_token=15,
        output_micro_per_token=75,
        cache_read_micro_per_token=4,
        cache_write_micro_per_token=19,
    ),
    "gemini-2.5-flash": ModelPrice(
        input_micro_per_token=1,
        output_micro_per_token=3,
        cache_read_micro_per_token=1,
        cache_write_micro_per_token=1,
    ),
    "gemini-2.5-pro": ModelPrice(
        input_micro_per_token=2,
        output_micro_per_token=5,
        cache_read_micro_per_token=1,
        cache_write_micro_per_token=1,
    ),
    "gemini-2.0-flash": ModelPrice(
        input_micro_per_token=1,
        output_micro_per_token=3,
        cache_read_micro_per_token=1,
        cache_write_micro_per_token=1,
    ),
    "gemini-1.5-pro": ModelPrice(
        input_micro_per_token=2,
        output_micro_per_token=5,
        cache_read_micro_per_token=1,
        cache_write_micro_per_token=1,
    ),
    "gemini-1.5-flash": ModelPrice(
        input_micro_per_token=1,
        output_micro_per_token=3,
        cache_read_micro_per_token=1,
        cache_write_micro_per_token=1,
    ),
    "mock-fast": ModelPrice(
        input_micro_per_token=1,
        output_micro_per_token=1,
    ),
}


def calculate_cost_microdollars(model: ModelRef, usage: Usage) -> int:
    """Calculate the cost of an invocation in integer micro-dollars."""
    pricing = _RATE_CARD.get(model.model, _RATE_CARD["mock-fast"])
    
    cost = (
        usage.input_tokens * pricing.input_micro_per_token
        + usage.output_tokens * pricing.output_micro_per_token
        + usage.cache_read_input_tokens * pricing.cache_read_micro_per_token
        + usage.cache_creation_input_tokens * pricing.cache_write_micro_per_token
    )
    return cost
