"""Adversarial and Stress Tests for Gemini 2.5 Model Gateway, Ratecard, and Budget Ledger.

Empirically challenges:
1. GeminiAdapter direct payload generation, JSON mode schema triggers, finishReason mapping, HTTP error recovery, and safety refusals.
2. Ratecard micro-dollar reconciliation across all models, cache tokens, zero/extreme token volumes, and fallback policies.
3. BudgetLedger reservation concurrency, daily spend ceiling enforcement, reservation release safety, and dynamic emergency kill switch.
4. GatewayService end-to-end reservation lifecycle under success and failure modes.
"""

import asyncio
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.api.gateway.adapters.gemini import GeminiAdapter
from services.api.gateway.contracts import (
    CompletionRequest,
    CompletionResponse,
    Message,
    ModelRef,
    Role,
    StopReason,
    TaskKind,
    Usage,
)
from services.api.gateway.errors import (
    AdapterError,
    BudgetExceededError,
    KillSwitchActiveError,
    ProviderRefusalError,
)
from services.api.gateway.ledger import BudgetLedger
from services.api.gateway.policy import GatewayPolicy
from services.api.gateway.ratecard import (
    _RATE_CARD,
    ModelPrice,
    calculate_cost_microdollars,
)
from services.api.gateway.service import GatewayService


class TestGeminiAdapterAdversarial:
    """Stress testing GeminiAdapter payload formatting, schema triggers, and error paths."""

    @pytest.mark.asyncio
    async def test_payload_generation_all_task_kinds_and_json_mode(self):
        """Verify structured JSON mode is enabled for CREATIVE_VARIANTS & GOVERNOR_PLAN and disabled for others."""
        adapter = GeminiAdapter(api_key="test-api-key")

        # 1. CREATIVE_VARIANTS -> responseMimeType: application/json
        req_creative = CompletionRequest(
            task=TaskKind.CREATIVE_VARIANTS,
            messages=[Message(role=Role.USER, content="Generate 3 headlines")],
            system_cacheable="Cacheable instructions",
            system_volatile="Volatile context",
            max_tokens=2048,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"variants": []}'}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 150, "candidatesTokenCount": 50},
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = await adapter.generate(req_creative, ModelRef("gemini", "gemini-2.5-flash"))
            payload = mock_post.call_args[1]["json"]

            assert payload["generationConfig"]["responseMimeType"] == "application/json"
            assert payload["generationConfig"]["maxOutputTokens"] == 2048
            assert payload["generationConfig"]["temperature"] == 0.2
            assert len(payload["contents"]) == 1
            assert payload["contents"][0]["role"] == "user"
            assert payload["contents"][0]["parts"][0]["text"] == "Generate 3 headlines"
            assert "Cacheable instructions\n\nVolatile context" in payload["systemInstruction"]["parts"][0]["text"]
            assert resp.usage.cost_microdollars == (150 * 1 + 50 * 3)  # 300 microdollars

        # 2. GOVERNOR_PLAN -> responseMimeType: application/json
        req_gov = CompletionRequest(
            task=TaskKind.GOVERNOR_PLAN,
            messages=[Message(role=Role.USER, content="Plan relay")],
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            await adapter.generate(req_gov, ModelRef("gemini", "gemini-2.5-pro"))
            payload = mock_post.call_args[1]["json"]
            assert payload["generationConfig"]["responseMimeType"] == "application/json"

        # 3. ANALYST_ANSWER -> no responseMimeType (regular text)
        req_analyst = CompletionRequest(
            task=TaskKind.ANALYST_ANSWER,
            messages=[Message(role=Role.USER, content="Analyze CTR")],
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            await adapter.generate(req_analyst, ModelRef("gemini", "gemini-2.5-flash"))
            payload = mock_post.call_args[1]["json"]
            assert "responseMimeType" not in payload["generationConfig"]

    @pytest.mark.asyncio
    async def test_model_name_normalization_and_fallback(self):
        """Verify model names normalize to valid Gemini endpoints or fallback safely."""
        adapter = GeminiAdapter(api_key="test-api-key")
        req = CompletionRequest(
            task=TaskKind.ANALYST_ANSWER,
            messages=[Message(role=Role.USER, content="Test")],
        )

        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            # gemini-2.5-pro
            await adapter.generate(req, ModelRef("gemini", "gemini-2.5-pro"))
            url1 = mock_post.call_args[0][0]
            assert "gemini-2.5-pro:generateContent" in url1

            # Non-gemini model name -> fallback to gemini-2.5-flash
            await adapter.generate(req, ModelRef("gemini", "claude-custom-name"))
            url2 = mock_post.call_args[0][0]
            assert "gemini-2.5-flash:generateContent" in url2

    @pytest.mark.asyncio
    async def test_candidate_finish_reason_and_refusal_handling(self):
        """Verify handling of finishReason (STOP, MAX_TOKENS, SAFETY) and missing candidates."""
        adapter = GeminiAdapter(api_key="test-api-key")
        req = CompletionRequest(
            task=TaskKind.ANALYST_ANSWER,
            messages=[Message(role=Role.USER, content="Test")],
        )

        # 1. MAX_TOKENS finish reason
        mock_resp_max = MagicMock(status_code=200)
        mock_resp_max.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Truncated..."}]}, "finishReason": "MAX_TOKENS"}],
            "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 100},
        }
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp_max
            resp = await adapter.generate(req, ModelRef("gemini", "gemini-2.5-flash"))
            assert resp.stop_reason == StopReason.MAX_TOKENS
            assert resp.content == "Truncated..."

        # 2. SAFETY block finish reason
        mock_resp_safety = MagicMock(status_code=200)
        mock_resp_safety.json.return_value = {
            "candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}],
        }
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp_safety
            with pytest.raises(ProviderRefusalError, match="blocked by safety filters"):
                await adapter.generate(req, ModelRef("gemini", "gemini-2.5-flash"))

        # 3. Empty candidates array
        mock_resp_empty = MagicMock(status_code=200)
        mock_resp_empty.json.return_value = {"candidates": []}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp_empty
            with pytest.raises(ProviderRefusalError, match="No candidates returned"):
                await adapter.generate(req, ModelRef("gemini", "gemini-2.5-flash"))

    @pytest.mark.asyncio
    async def test_http_error_statuses_and_connection_failures(self):
        """Verify all non-200 HTTP statuses and network exceptions raise AdapterError with diagnostic messages."""
        adapter = GeminiAdapter(api_key="test-api-key")
        req = CompletionRequest(
            task=TaskKind.ANALYST_ANSWER,
            messages=[Message(role=Role.USER, content="Test")],
        )

        error_statuses = [400, 401, 403, 429, 500, 502, 503, 504]
        for status in error_statuses:
            mock_resp = MagicMock(status_code=status, text=f"HTTP {status} Failure")
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                with pytest.raises(AdapterError, match=f"Gemini API returned HTTP {status}"):
                    await adapter.generate(req, ModelRef("gemini", "gemini-2.5-flash"))

        # Connection exception
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=TimeoutError("Request timed out")):
            with pytest.raises(AdapterError, match="Gemini HTTP connection failed"):
                await adapter.generate(req, ModelRef("gemini", "gemini-2.5-flash"))


class TestRatecardReconciliationAdversarial:
    """Stress testing ratecard micro-dollar calculations across models, tokens, and edge cases."""

    def test_all_registered_models_pricing_formula(self):
        """Verify ratecard calculation against expected integer micro-dollar values for all models."""
        expected_rates = {
            "gemini-2.5-flash": {"in": 1, "out": 3, "cr": 1, "cw": 1},
            "gemini-2.5-pro": {"in": 2, "out": 5, "cr": 1, "cw": 1},
            "gemini-2.0-flash": {"in": 1, "out": 3, "cr": 1, "cw": 1},
            "gemini-1.5-pro": {"in": 2, "out": 5, "cr": 1, "cw": 1},
            "gemini-1.5-flash": {"in": 1, "out": 3, "cr": 1, "cw": 1},
            "claude-3-5-sonnet-20241022": {"in": 3, "out": 15, "cr": 1, "cw": 4},
            "claude-3-5-haiku-20241022": {"in": 1, "out": 5, "cr": 1, "cw": 1},
            "claude-3-opus-20240229": {"in": 15, "out": 75, "cr": 4, "cw": 19},
            "mock-fast": {"in": 1, "out": 1, "cr": 0, "cw": 0},
        }

        usage = Usage(
            input_tokens=1000,
            output_tokens=500,
            cache_read_input_tokens=200,
            cache_creation_input_tokens=100,
        )

        for model_name, rates in expected_rates.items():
            model = ModelRef("test", model_name)
            cost = calculate_cost_microdollars(model, usage)
            expected_cost = (
                1000 * rates["in"]
                + 500 * rates["out"]
                + 200 * rates["cr"]
                + 100 * rates["cw"]
            )
            assert cost == expected_cost, f"Mismatch for {model_name}: got {cost}, expected {expected_cost}"

    def test_zero_and_extreme_token_reconciliation(self):
        """Verify 0 tokens = 0 microdollars, and large token volumes calculate without overflow."""
        model = ModelRef("gemini", "gemini-2.5-pro")

        # Zero tokens
        zero_usage = Usage(0, 0, 0, 0)
        assert calculate_cost_microdollars(model, zero_usage) == 0

        # 1 Million input + 500k output tokens on gemini-2.5-pro
        # (1,000,000 * 2) + (500,000 * 5) = 2,000,000 + 2,500,000 = 4,500,000 microdollars ($4.50 USD)
        large_usage = Usage(input_tokens=1_000_000, output_tokens=500_000)
        assert calculate_cost_microdollars(model, large_usage) == 4_500_000

    def test_unknown_model_fallback_ratecard(self):
        """Verify unrecognized model falls back to mock-fast ratecard without crashing."""
        model = ModelRef("unknown_provider", "non_existent_model_xyz")
        usage = Usage(input_tokens=500, output_tokens=200)
        cost = calculate_cost_microdollars(model, usage)
        # mock-fast: 500 * 1 + 200 * 1 = 700 microdollars
        assert cost == 700


class TestBudgetLedgerAndKillSwitchAdversarial:
    """Stress testing BudgetLedger concurrency, boundary limits, and emergency kill switch."""

    @pytest.mark.asyncio
    async def test_budget_reserve_exact_ceiling_and_overflow(self):
        """Verify reservations right at the daily ceiling succeed, and 1 micro-dollar over is rejected."""
        policy = GatewayPolicy(daily_spend_limit_microdollars=10_000)
        ledger = BudgetLedger(policy)

        # 1. Reserve 6,000 micro-dollars -> active = 6,000
        res1 = await ledger.reserve("res_1", 6_000)
        assert res1.amount_microdollars == 6_000
        assert ledger.reserved_microdollars == 6_000
        assert ledger.spent_today_microdollars == 0

        # 2. Reserve exact remaining 4,000 micro-dollars -> active = 10,000
        res2 = await ledger.reserve("res_2", 4_000)
        assert res2.amount_microdollars == 4_000
        assert ledger.reserved_microdollars == 10_000

        # 3. Attempt to reserve 1 micro-dollar more -> must raise BudgetExceededError
        with pytest.raises(BudgetExceededError, match="Daily budget ceiling exceeded"):
            await ledger.reserve("res_3", 1)

        # 4. Reconcile res_1 with actual spend of 5,500 micro-dollars
        await ledger.reconcile("res_1", 5_500)
        assert ledger.reserved_microdollars == 4_000
        assert ledger.spent_today_microdollars == 5_500
        # Total committed = 5,500 + 4,000 = 9,500. Can reserve 500 more.

        res3 = await ledger.reserve("res_3", 500)
        assert res3.amount_microdollars == 500
        assert ledger.reserved_microdollars == 4_500

        # 5. Release res_2 without spend
        await ledger.release("res_2")
        assert ledger.reserved_microdollars == 500
        assert ledger.spent_today_microdollars == 5_500

    @pytest.mark.asyncio
    async def test_concurrent_reservations_thread_safety(self):
        """Verify concurrent async reserve requests do not race condition past the spend limit."""
        policy = GatewayPolicy(daily_spend_limit_microdollars=5_000)
        ledger = BudgetLedger(policy)

        successful_res = []
        failed_res = []

        async def attempt_reserve(idx: int):
            try:
                res = await ledger.reserve(f"res_{idx}", 1_000)
                successful_res.append(res)
            except BudgetExceededError:
                failed_res.append(idx)

        # Launch 10 concurrent reservation requests of 1,000 micro-dollars each (limit is 5,000)
        await asyncio.gather(*(attempt_reserve(i) for i in range(10)))

        assert len(successful_res) == 5
        assert len(failed_res) == 5
        assert ledger.reserved_microdollars == 5_000

    @pytest.mark.asyncio
    async def test_emergency_kill_switch_dynamic_toggle(self):
        """Verify emergency kill switch immediately stops all reservations and permits resumption when disabled."""
        policy_active = GatewayPolicy(daily_spend_limit_microdollars=50_000, kill_switch_active=False)
        ledger = BudgetLedger(policy_active)

        # 1. Normal reservation succeeds
        await ledger.reserve("res_normal_1", 1_000)
        assert ledger.reserved_microdollars == 1_000

        # 2. Activate emergency kill switch by updating ledger policy
        policy_killed = GatewayPolicy(daily_spend_limit_microdollars=50_000, kill_switch_active=True)
        ledger.policy = policy_killed

        with pytest.raises(KillSwitchActiveError, match="LLM Egress Kill Switch is active"):
            await ledger.reserve("res_blocked", 100)

        # 3. Existing reservations can still be released or reconciled
        await ledger.release("res_normal_1")
        assert ledger.reserved_microdollars == 0

        # 4. Deactivate emergency kill switch -> reservations resume
        ledger.policy = policy_active
        await ledger.reserve("res_resumed", 2_000)
        assert ledger.reserved_microdollars == 2_000

    def test_daily_spend_reset(self):
        """Verify reset_daily_spend completely wipes spent and active reservations."""
        policy = GatewayPolicy()
        ledger = BudgetLedger(policy)
        ledger._spent_today_microdollars = 25_000
        ledger._active_reservations["r1"] = MagicMock(amount_microdollars=5_000)

        ledger.reset_daily_spend()
        assert ledger.spent_today_microdollars == 0
        assert ledger.reserved_microdollars == 0
        assert len(ledger._active_reservations) == 0


class TestGatewayServiceLifecycleAdversarial:
    """Stress testing GatewayService reservation/reconciliation lifecycle."""

    @pytest.mark.asyncio
    async def test_gateway_service_cleans_reservation_on_adapter_failure(self, monkeypatch):
        """Verify that when an adapter raises an unhandled error, the reservation is released immediately."""
        monkeypatch.setenv("HELM_LLM_PROVIDER", "gemini")
        policy = GatewayPolicy(daily_spend_limit_microdollars=50_000)
        service = GatewayService(policy=policy, replay_mode=False)

        failing_adapter = MagicMock()
        failing_adapter.generate = AsyncMock(side_effect=RuntimeError("Provider API crashed"))
        service.register_adapter("gemini", failing_adapter)

        req = CompletionRequest(
            task=TaskKind.ANALYST_ANSWER,
            messages=[Message(role=Role.USER, content="Hello")],
            max_tokens=1000,
            request_id="req_fail_test",
        )

        with pytest.raises(RuntimeError, match="Provider API crashed"):
            await service.generate(req)

        # Ensure ledger has ZERO reservations and ZERO spend left over
        assert service.ledger.reserved_microdollars == 0
        assert service.ledger.spent_today_microdollars == 0
        assert "req_fail_test" not in service.ledger._active_reservations
