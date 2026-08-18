"""Google Gemini provider adapter."""

from __future__ import annotations

import json
from typing import Any
import httpx

from services.api.gateway.contracts import (
    CompletionRequest,
    CompletionResponse,
    ModelRef,
    Role,
    StopReason,
    TaskKind,
    Usage,
)
from services.api.gateway.errors import AdapterError, ProviderRefusalError
from services.api.gateway.keys import get_gemini_api_key
from services.api.gateway.ratecard import calculate_cost_microdollars

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAdapter:
    """Adapter for Google Gemini models using direct REST API / GenAI endpoints."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or get_gemini_api_key()

    async def generate(self, request: CompletionRequest, model: ModelRef) -> CompletionResponse:
        """Call Gemini generateContent API."""
        if not self.api_key:
            raise AdapterError("Gemini API key is not configured.")

        # Build contents payload
        contents: list[dict[str, Any]] = []
        for msg in request.messages:
            if msg.role == Role.SYSTEM:
                continue
            role = "model" if msg.role == Role.ASSISTANT else "user"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        # Build system instruction
        system_texts = []
        if request.system_cacheable:
            system_texts.append(request.system_cacheable)
        if request.system_volatile:
            system_texts.append(request.system_volatile)

        generation_config: dict[str, Any] = {
            "maxOutputTokens": request.max_tokens or 2048,
            "temperature": 0.2,
        }
        # Enable structured JSON mode for creative and structured tasks
        if request.task in (TaskKind.CREATIVE_VARIANTS, TaskKind.GOVERNOR_PLAN):
            generation_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        if system_texts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_texts)}],
            }

        # Model name normalization
        model_name = model.model
        if not model_name.startswith("gemini-"):
            model_name = "gemini-2.5-flash"

        url = f"{_GEMINI_BASE_URL}/{model_name}:generateContent?key={self.api_key}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
            except Exception as exc:
                raise AdapterError(f"Gemini HTTP connection failed: {exc}") from exc

        if resp.status_code != 200:
            err_msg = f"Gemini API returned HTTP {resp.status_code}: {resp.text}"
            raise AdapterError(err_msg)

        data = resp.json()

        # Extract generated content
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderRefusalError(f"No candidates returned by Gemini: {data}")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "STOP")
        parts = candidate.get("content", {}).get("parts", [])
        text_content = "".join(p.get("text", "") for p in parts)

        # Map finish reason
        if finish_reason == "SAFETY":
            raise ProviderRefusalError(f"Gemini generation blocked by safety filters: {candidate}")
        elif finish_reason == "MAX_TOKENS":
            stop_reason = StopReason.MAX_TOKENS
        else:
            stop_reason = StopReason.END_TURN

        # Extract usage metadata
        usage_meta = data.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", 0)
        candidates_tokens = usage_meta.get("candidatesTokenCount", 0)

        usage = Usage(
            input_tokens=prompt_tokens,
            output_tokens=candidates_tokens,
        )
        cost = calculate_cost_microdollars(model, usage)
        usage = Usage(
            input_tokens=prompt_tokens,
            output_tokens=candidates_tokens,
            cost_microdollars=cost,
        )

        return CompletionResponse(
            content=text_content,
            stop_reason=stop_reason,
            model=model,
            usage=usage,
            request_id=request.request_id,
        )
