"""Anthropic provider adapter."""

from __future__ import annotations

import json
from typing import Any
from services.api.gateway.contracts import (
    CompletionRequest,
    CompletionResponse,
    ModelRef,
    Role,
    StopReason,
    Usage,
)
from services.api.gateway.errors import AdapterError, ProviderRefusalError
from services.api.gateway.keys import get_anthropic_api_key
from services.api.gateway.ratecard import calculate_cost_microdollars


class AnthropicAdapter:
    """Adapter for Anthropic Claude models using the official SDK."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or get_anthropic_api_key()

    async def generate(self, request: CompletionRequest, model: ModelRef) -> CompletionResponse:
        """Call Anthropic API."""
        if not self.api_key:
            raise AdapterError("Anthropic API key is not configured.")

        try:
            import anthropic
        except ImportError as exc:
            raise AdapterError(f"anthropic package not installed: {exc}") from exc

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # Build messages payload
        messages = []
        for msg in request.messages:
            if msg.role == Role.SYSTEM:
                continue
            messages.append({"role": msg.role.value, "content": msg.content})

        # Build system prompt with prompt caching support
        system_blocks: list[dict[str, Any]] = []
        if request.system_cacheable:
            system_blocks.append({
                "type": "text",
                "text": request.system_cacheable,
                "cache_control": {"type": "ephemeral"},
            })
        if request.system_volatile:
            system_blocks.append({
                "type": "text",
                "text": request.system_volatile,
            })

        kwargs: dict[str, Any] = {
            "model": model.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        if system_blocks:
            kwargs["system"] = system_blocks

        try:
            raw = await client.messages.create(**kwargs)
        except Exception as exc:
            raise AdapterError(f"Anthropic API call failed: {exc}") from exc

        # Extract content
        text_content = ""
        for block in raw.content:
            if hasattr(block, "text"):
                text_content += block.text

        stop_reason_map = {
            "end_turn": StopReason.END_TURN,
            "max_tokens": StopReason.MAX_TOKENS,
            "tool_use": StopReason.TOOL_USE,
            "refusal": StopReason.REFUSAL,
        }
        stop_reason = stop_reason_map.get(raw.stop_reason or "end_turn", StopReason.END_TURN)

        if stop_reason == StopReason.REFUSAL:
            raise ProviderRefusalError(f"Model refused generation: {text_content}")

        raw_usage = getattr(raw, "usage", None)
        input_tokens = getattr(raw_usage, "input_tokens", 0) if raw_usage else 0
        output_tokens = getattr(raw_usage, "output_tokens", 0) if raw_usage else 0
        cache_read = getattr(raw_usage, "cache_read_input_tokens", 0) if raw_usage else 0
        cache_write = getattr(raw_usage, "cache_creation_input_tokens", 0) if raw_usage else 0

        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
        )
        cost = calculate_cost_microdollars(model, usage)
        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
            cost_microdollars=cost,
        )

        return CompletionResponse(
            content=text_content,
            stop_reason=stop_reason,
            model=model,
            usage=usage,
            request_id=request.request_id,
        )
