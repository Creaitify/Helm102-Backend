"""Tests for GatewayService, Ledger, Ratecard, and Policy."""

import pytest
from services.api.gateway.contracts import (
    CompletionRequest,
    Message,
    Role,
    TaskKind,
)
from services.api.gateway.errors import BudgetExceededError, KillSwitchActiveError
from services.api.gateway.policy import GatewayPolicy
from services.api.gateway.service import GatewayService


@pytest.mark.asyncio
async def test_gateway_replay_generate():
    service = GatewayService(replay_mode=True)
    req = CompletionRequest(
        task=TaskKind.ANALYST_ANSWER,
        messages=[Message(role=Role.USER, content="Summarize ROAS.")],
    )
    resp = await service.generate(req)
    assert resp.content.startswith("[Replay response")
    assert resp.usage.cost_microdollars > 0
    assert service.ledger.spent_today_microdollars == resp.usage.cost_microdollars


@pytest.mark.asyncio
async def test_gateway_budget_ceiling_enforcement():
    policy = GatewayPolicy(daily_spend_limit_microdollars=100)
    service = GatewayService(policy=policy, replay_mode=True)

    # Request with estimated cost exceeding 100 microdollars
    req = CompletionRequest(
        task=TaskKind.ANALYST_ANSWER,
        messages=[Message(role=Role.USER, content="Test limit")],
        max_tokens=1000,
    )
    with pytest.raises(BudgetExceededError):
        await service.generate(req)


@pytest.mark.asyncio
async def test_gateway_kill_switch():
    policy = GatewayPolicy(kill_switch_active=True)
    service = GatewayService(policy=policy, replay_mode=True)

    req = CompletionRequest(
        task=TaskKind.CREATIVE_VARIANTS,
        messages=[Message(role=Role.USER, content="Generate ad")],
    )
    with pytest.raises(KillSwitchActiveError):
        await service.generate(req)


def test_gemini_ratecard_and_pricing():
    from services.api.gateway.contracts import ModelRef, Usage
    from services.api.gateway.ratecard import calculate_cost_microdollars

    model = ModelRef(provider="gemini", model="gemini-2.5-flash")
    usage = Usage(input_tokens=1000, output_tokens=500)
    cost = calculate_cost_microdollars(model, usage)
    # 1000 * 1 + 500 * 3 = 2500 microdollars ($0.0025)
    assert cost == 2500


def test_provider_switching_and_keys(monkeypatch):
    from services.api.gateway.keys import (
        get_active_provider,
        get_model_for_provider,
        has_gemini_api_key,
    )

    # Fake key via monkeypatch — the suite must never depend on a real key.
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    assert has_gemini_api_key() is True

    # Test Gemini routing
    monkeypatch.setenv("HELM_LLM_PROVIDER", "gemini")
    assert get_active_provider() == "gemini"
    assert get_model_for_provider("gemini") == "gemini-2.5-flash"

    # Test Anthropic routing. HELM pins the strongest model for every task —
    # its outputs drive real budget decisions, so nothing gets a cheap tier.
    monkeypatch.setenv("HELM_LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    assert get_active_provider() == "anthropic"
    assert get_model_for_provider("anthropic") == "claude-opus-5"
    # There is no downgraded "fast" tier: every task routes to the same model.
    assert get_model_for_provider("anthropic", fast=True) == "claude-opus-5"


@pytest.mark.asyncio
async def test_gemini_adapter_payload_generation_and_success():
    from unittest.mock import AsyncMock, MagicMock, patch
    from services.api.gateway.adapters.gemini import GeminiAdapter
    from services.api.gateway.contracts import ModelRef, StopReason

    adapter = GeminiAdapter(api_key="test-gemini-key")
    req = CompletionRequest(
        task=TaskKind.CREATIVE_VARIANTS,
        messages=[
            Message(role=Role.USER, content="Generate 3 headlines for index funds."),
            Message(role=Role.ASSISTANT, content="Here are initial thoughts."),
            Message(role=Role.USER, content="Refine for Instagram."),
        ],
        system_cacheable="You are a SEBI-compliant copywriter.",
        system_volatile="Current year is 2026.",
        max_tokens=1024,
        request_id="req-gemini-123",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": '{"headline": "Grow with Index Funds"}'}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 200,
            "candidatesTokenCount": 80,
        },
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        model = ModelRef(provider="gemini", model="gemini-2.5-flash")
        resp = await adapter.generate(req, model)

        assert resp.content == '{"headline": "Grow with Index Funds"}'
        assert resp.stop_reason == StopReason.END_TURN
        assert resp.model == model
        assert resp.usage.input_tokens == 200
        assert resp.usage.output_tokens == 80
        # Ratecard for gemini-2.5-flash: 200 * 1 + 80 * 3 = 440 microdollars
        assert resp.usage.cost_microdollars == 440
        assert resp.request_id == "req-gemini-123"

        # Inspect generated payload
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert payload["generationConfig"]["maxOutputTokens"] == 1024
        assert "You are a SEBI-compliant copywriter." in payload["systemInstruction"]["parts"][0]["text"]
        assert "Current year is 2026." in payload["systemInstruction"]["parts"][0]["text"]
        assert len(payload["contents"]) == 3
        assert payload["contents"][0]["role"] == "user"
        assert payload["contents"][1]["role"] == "model"


@pytest.mark.asyncio
async def test_gemini_adapter_governor_plan_json_mode():
    from unittest.mock import AsyncMock, MagicMock, patch
    from services.api.gateway.adapters.gemini import GeminiAdapter
    from services.api.gateway.contracts import ModelRef

    adapter = GeminiAdapter(api_key="test-gemini-key")
    req = CompletionRequest(
        task=TaskKind.GOVERNOR_PLAN,
        messages=[Message(role=Role.USER, content="Formulate orchestration plan.")],
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {"parts": [{"text": '{"plan": "step 1"}'}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 20},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        resp = await adapter.generate(req, ModelRef(provider="gemini", model="gemini-2.5-flash"))
        payload = mock_post.call_args[1]["json"]
        assert payload["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.asyncio
async def test_gemini_adapter_safety_refusal():
    from unittest.mock import AsyncMock, MagicMock, patch
    from services.api.gateway.adapters.gemini import GeminiAdapter
    from services.api.gateway.contracts import ModelRef
    from services.api.gateway.errors import ProviderRefusalError

    adapter = GeminiAdapter(api_key="test-gemini-key")
    req = CompletionRequest(
        task=TaskKind.ANALYST_ANSWER,
        messages=[Message(role=Role.USER, content="Risky query")],
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {"parts": []},
                "finishReason": "SAFETY",
            }
        ],
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ProviderRefusalError, match="blocked by safety filters"):
            await adapter.generate(req, ModelRef(provider="gemini", model="gemini-2.5-flash"))


@pytest.mark.asyncio
async def test_gemini_adapter_http_error_handling():
    from unittest.mock import AsyncMock, MagicMock, patch
    from services.api.gateway.adapters.gemini import GeminiAdapter
    from services.api.gateway.contracts import ModelRef
    from services.api.gateway.errors import AdapterError

    adapter = GeminiAdapter(api_key="test-gemini-key")
    req = CompletionRequest(
        task=TaskKind.ANALYST_ANSWER,
        messages=[Message(role=Role.USER, content="Hello")],
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(AdapterError, match="Gemini API returned HTTP 503"):
            await adapter.generate(req, ModelRef(provider="gemini", model="gemini-2.5-flash"))


@pytest.mark.asyncio
async def test_gemini_adapter_missing_api_key(monkeypatch):
    from services.api.gateway.adapters.gemini import GeminiAdapter
    from services.api.gateway.contracts import ModelRef
    from services.api.gateway.errors import AdapterError

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    adapter = GeminiAdapter(api_key=None)
    req = CompletionRequest(
        task=TaskKind.ANALYST_ANSWER,
        messages=[Message(role=Role.USER, content="Hello")],
    )
    with pytest.raises(AdapterError, match="Gemini API key is not configured"):
        await adapter.generate(req, ModelRef(provider="gemini", model="gemini-2.5-flash"))


