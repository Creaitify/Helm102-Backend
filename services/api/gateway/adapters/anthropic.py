"""Anthropic provider adapter — Claude Opus 5 via the official SDK.

Written against the current Messages API surface, which matters because several
older patterns are now hard errors on Opus 5:

  * `temperature` / `top_p` / `top_k` are removed — sending any of them is a 400.
  * `thinking.budget_tokens` is removed — adaptive thinking replaces it.
  * Assistant prefill is rejected.

So this adapter sends `thinking={"type": "adaptive"}` plus
`output_config={"effort": ...}`, and streams every request so large `max_tokens`
values can't trip an HTTP timeout mid-generation.
"""

from __future__ import annotations

import logging
from typing import Any

from services.api.gateway.contracts import (
    CompletionRequest,
    CompletionResponse,
    Effort,
    ModelRef,
    Role,
    StopReason,
    Usage,
)
from services.api.gateway.errors import AdapterError, ProviderRefusalError
from services.api.gateway.keys import get_anthropic_api_key
from services.api.gateway.ratecard import calculate_cost_microdollars

logger = logging.getLogger(__name__)

# Models that reject `temperature` and `thinking.budget_tokens`, and that run
# adaptive thinking instead. Prefix match covers the whole family.
_ADAPTIVE_THINKING_PREFIXES = (
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
    "claude-fable-5",
    "claude-mythos-5",
)

_EFFORT_VALUES = {"low", "medium", "high", "xhigh", "max"}


def _is_adaptive_model(model_id: str) -> bool:
    return any(model_id.startswith(prefix) for prefix in _ADAPTIVE_THINKING_PREFIXES)


class AnthropicAdapter:
    """Adapter for Anthropic Claude models using the official SDK."""

    def __init__(self, api_key: str | None = None) -> None:
        self._explicit_key = api_key

    @property
    def api_key(self) -> str | None:
        """Resolved lazily so a key added after boot is picked up."""
        return self._explicit_key or get_anthropic_api_key()

    async def generate(self, request: CompletionRequest, model: ModelRef) -> CompletionResponse:
        """Call the Anthropic Messages API and normalize the response."""
        if not self.api_key:
            raise AdapterError("Anthropic API key is not configured.")

        try:
            import anthropic
        except ImportError as exc:
            raise AdapterError(f"anthropic package not installed: {exc}") from exc

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # System turns are hoisted out of `messages` into the `system` field.
        messages: list[dict[str, Any]] = []
        inline_system: list[str] = []
        for msg in request.messages:
            if msg.role == Role.SYSTEM:
                inline_system.append(msg.content)
                continue
            messages.append({"role": msg.role.value, "content": msg.content})

        if not messages:
            raise AdapterError("Anthropic requires at least one user or assistant message.")

        # Stable instructions first (cached), volatile context after.
        system_blocks: list[dict[str, Any]] = []
        cacheable = "\n\n".join(filter(None, [request.system_cacheable, *inline_system])).strip()
        if cacheable:
            system_blocks.append(
                {
                    "type": "text",
                    "text": cacheable,
                    "cache_control": {"type": "ephemeral"},
                }
            )
        if request.system_volatile:
            system_blocks.append({"type": "text", "text": request.system_volatile})

        kwargs: dict[str, Any] = {
            "model": model.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        if system_blocks:
            kwargs["system"] = system_blocks

        output_config: dict[str, Any] = {}
        effort = getattr(request.effort, "value", str(request.effort or "high"))
        if effort in _EFFORT_VALUES:
            output_config["effort"] = effort

        if _is_adaptive_model(model.model):
            # Adaptive thinking; `budget_tokens` and `temperature` are 400s here.
            kwargs["thinking"] = {"type": "adaptive"}
        elif request.effort in (Effort.HIGH, Effort.XHIGH, Effort.MAX):
            # Older models still take an explicit thinking budget.
            budget = max(1024, min(request.max_tokens - 1, 4096))
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}

        if request.json_schema:
            # Structured outputs go through output_config.format, not the
            # deprecated top-level output_format parameter.
            output_config["format"] = {
                "type": "json_schema",
                "schema": dict(request.json_schema),
            }

        if output_config:
            kwargs["output_config"] = output_config

        try:
            # Streaming keeps long generations from hitting the request timeout.
            async with client.messages.stream(**kwargs) as stream:
                raw = await stream.get_final_message()
        except anthropic.APIStatusError as exc:
            raise AdapterError(
                f"Anthropic API error ({exc.status_code}): {getattr(exc, 'message', str(exc))}"
            ) from exc
        except Exception as exc:
            raise AdapterError(f"Anthropic API call failed: {exc}") from exc

        text_content = "".join(
            block.text for block in raw.content if getattr(block, "type", "") == "text"
        )

        stop_reason = {
            "end_turn": StopReason.END_TURN,
            "max_tokens": StopReason.MAX_TOKENS,
            "tool_use": StopReason.TOOL_USE,
            "refusal": StopReason.REFUSAL,
        }.get(raw.stop_reason or "end_turn", StopReason.END_TURN)

        if stop_reason == StopReason.REFUSAL:
            details = getattr(raw, "stop_details", None)
            category = getattr(details, "category", None) or "unspecified"
            raise ProviderRefusalError(f"Model declined this request (category: {category}).")

        raw_usage = getattr(raw, "usage", None)
        input_tokens = int(getattr(raw_usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(raw_usage, "output_tokens", 0) or 0)
        cache_read = int(getattr(raw_usage, "cache_read_input_tokens", 0) or 0)
        cache_write = int(getattr(raw_usage, "cache_creation_input_tokens", 0) or 0)

        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
        )
        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
            cost_microdollars=calculate_cost_microdollars(model, usage),
        )

        return CompletionResponse(
            content=text_content,
            stop_reason=stop_reason,
            model=model,
            usage=usage,
            request_id=request.request_id,
            raw_response={"id": getattr(raw, "id", ""), "model": getattr(raw, "model", "")},
        )
