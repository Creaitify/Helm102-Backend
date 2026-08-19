"""Creative Worker: Generates copy, video scripts, and multi-platform captions via Model Gateway."""

from __future__ import annotations

import json
import logging
from typing import Any
from modules.creative.schema import (
    CREATIVE_PACKAGE_SCHEMA,
    AdCreative,
    CreativeBrief,
    CreativePackage,
    PlatformCaptions,
    SceneCue,
    VideoScript,
)
from services.api.gateway.contracts import (
    CompletionRequest,
    Message,
    Role,
    TaskKind,
)
from services.api.gateway.service import GatewayService

logger = logging.getLogger(__name__)


def _s(value: Any, default: str) -> str:
    """Coerce an LLM-provided value to a plain string.

    Live models sometimes return nested objects where the schema expects a
    string; downstream verifiers call `.lower()` on these fields, so anything
    non-string must be flattened here rather than crashing the run.
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        parts = [f"{k}: {_s(v, '')}" for k, v in value.items()]
        return "; ".join(p for p in parts if p) or default
    if isinstance(value, list):
        return " ".join(_s(v, "") for v in value) or default
    return str(value)


def _slist(value: Any, default: list[str]) -> list[str]:
    """Coerce an LLM-provided value to a list of strings."""
    if isinstance(value, list):
        coerced = [_s(v, "") for v in value]
        return [c for c in coerced if c] or default
    if isinstance(value, str) and value:
        return [value]
    return default


def _i(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class CreativeWorker:
    """Worker responsible for creative generation conforming to the 4-stage pipeline."""

    def __init__(self, gateway: GatewayService) -> None:
        self.gateway = gateway

    async def generate_creative_package(
        self,
        objective: str,
        analyst_findings: dict[str, Any] | None = None,
    ) -> CreativePackage:
        """Generate structured 4-stage creative package."""
        findings_context = json.dumps(analyst_findings or {}, indent=2)

        prompt = (
            f"Generate a 4-stage marketing creative package for objective: '{objective}'.\n"
            f"Performance Insights:\n{findings_context}\n\n"
            "Return a strictly valid JSON object matching the 4 stages:\n"
            "1. brief (target_audience, core_angle, pain_point, value_proposition, tone_of_voice, mandatory_disclaimers)\n"
            "2. script (title, duration_seconds, aspect_ratio, hook_3s, problem_solution, call_to_action, scenes)\n"
            "3. creative (headline, primary_text, call_to_action, alternative_headlines, image_prompt)\n"
            "4. captions (meta_caption, instagram_caption, linkedin_caption, hashtags)\n"
        )

        request = CompletionRequest(
            task=TaskKind.CREATIVE_VARIANTS,
            messages=[
                Message(role=Role.SYSTEM, content="You are an expert financial and growth marketing copywriter. Never make guaranteed return claims. Always include standard SEBI disclaimers."),
                Message(role=Role.USER, content=prompt),
            ],
            system_cacheable="Brand Voice: Modern, trustworthy, transparent, high-converting.",
            # Structured outputs plus a real budget. Without both, adaptive
            # thinking consumed the old 4096-token default and truncated the
            # JSON mid-object, silently demoting every run to the template.
            max_tokens=16000,
            json_schema=CREATIVE_PACKAGE_SCHEMA,
        )

        try:
            response = await self.gateway.generate(request)
        except Exception as exc:
            logger.warning(
                "Creative generation fell back to the deterministic package "
                "— gateway call failed: %s",
                exc,
            )
            return self._build_deterministic_package(objective)

        package = self._parse_or_fallback(response.content, objective)
        if package.generation_mode != "llm":
            logger.warning(
                "Creative generation fell back to the deterministic package "
                "— unparseable model output (stop_reason=%s, %d chars).",
                getattr(response.stop_reason, "value", response.stop_reason),
                len(response.content or ""),
            )
        return package

    def _parse_or_fallback(self, content: str, objective: str) -> CreativePackage:
        """Parse LLM JSON output or fallback to structured default."""
        try:
            # Strip markdown fence if present
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            parsed = json.loads(cleaned.strip())
            
            b = parsed.get("brief", {}) if isinstance(parsed.get("brief"), dict) else {}
            brief = CreativeBrief(
                target_audience=_s(b.get("target_audience"), "Retail Investors 25-45"),
                core_angle=_s(b.get("core_angle"), "Disciplined Long-term Wealth via Systematic Investing"),
                pain_point=_s(b.get("pain_point"), "High inflation eroding cash savings"),
                value_proposition=_s(b.get("value_proposition"), "Automated SIPs with low expense ratio funds"),
                tone_of_voice=_s(b.get("tone_of_voice"), "Educational, clear, empowering"),
                mandatory_disclaimers=_slist(b.get("mandatory_disclaimers"), ["Mutual fund investments are subject to market risks."]),
            )

            s = parsed.get("script", {}) if isinstance(parsed.get("script"), dict) else {}
            raw_scenes = s.get("scenes", []) if isinstance(s.get("scenes"), list) else []
            scenes = [
                SceneCue(
                    timestamp_range=_s(sc.get("timestamp_range"), "0-3s"),
                    visual_cue=_s(sc.get("visual_cue"), "Close up on phone with portfolio growth chart"),
                    audio_spoken=_s(sc.get("audio_spoken"), "Still keeping all your savings in a low-interest account?"),
                    on_screen_text=_s(sc.get("on_screen_text"), "Make your money work for you"),
                )
                for sc in raw_scenes
                if isinstance(sc, dict)
            ] or [
                SceneCue("0-3s", "Split screen showing inflation vs compounding", "Is your savings account losing value every year?", "Beat Inflation"),
                SceneCue("3-15s", "UI walkthrough setting up ₹1,000 monthly SIP", "With Finnovate, automate your SIP in 60 seconds.", "Start with ₹500/mo"),
                SceneCue("15-30s", "Clean CTA screen with verified badge", "Download Finnovate and start compounding today.", "Invest Wisely · SEBI Registered"),
            ]

            script = VideoScript(
                title=_s(s.get("title"), "Smart SIP Growth"),
                duration_seconds=_i(s.get("duration_seconds"), 30),
                aspect_ratio=_s(s.get("aspect_ratio"), "9:16"),
                hook_3s=_s(s.get("hook_3s"), "Still leaving your savings idle?"),
                problem_solution=_s(s.get("problem_solution"), "Automate disciplined SIP investments with zero paperwork."),
                call_to_action=_s(s.get("call_to_action"), "Start your SIP on Finnovate today."),
                scenes=scenes,
            )

            c = parsed.get("creative", {}) if isinstance(parsed.get("creative"), dict) else {}
            creative = AdCreative(
                headline=_s(c.get("headline"), "Smart SIP Investing for Long-Term Growth"),
                primary_text=_s(c.get("primary_text"), "Build lasting wealth with disciplined monthly investments. Transparent portfolio tracking and expert asset allocation. Mutual fund investments are subject to market risks."),
                call_to_action=_s(c.get("call_to_action"), "Start SIP Now"),
                alternative_headlines=_slist(c.get("alternative_headlines"), ["Grow Your Wealth Systematically", "Automate Your Monthly SIP"]),
                image_prompt=_s(c.get("image_prompt"), "Clean financial mobile app dashboard showing steady upward compounding curve, dark blue and emerald green accents."),
            )

            cp = parsed.get("captions", {}) if isinstance(parsed.get("captions"), dict) else {}
            captions = PlatformCaptions(
                meta_caption=_s(cp.get("meta_caption"), "Turn small monthly savings into long-term financial freedom. Start a SIP with Finnovate today."),
                instagram_caption=_s(cp.get("instagram_caption"), "Compounding is the 8th wonder of the world. 📈 Automate your financial growth with disciplined SIPs. Link in bio.\n\n*Mutual fund investments are subject to market risks."),
                linkedin_caption=_s(cp.get("linkedin_caption"), "Disciplined investing beats market timing. Explore how Finnovate simplifies long-term wealth building with automated portfolio rebalancing."),
                hashtags=_slist(cp.get("hashtags"), ["#PersonalFinance", "#SIP", "#Investing", "#MutualFunds"]),
            )

            return CreativePackage(brief=brief, script=script, creative=creative, captions=captions, generation_mode="llm")
        except Exception as exc:
            logger.warning("Could not parse creative package JSON: %s", exc)
            return self._build_deterministic_package(objective)

    def _build_deterministic_package(self, objective: str) -> CreativePackage:
        brief = CreativeBrief(
            target_audience="First-time and disciplined retail investors (age 24-40)",
            core_angle="Systematic compounding beats market timing",
            pain_point="Inflation eroding purchasing power of bank deposits",
            value_proposition="Zero-commission, automated monthly index SIPs",
            tone_of_voice="Transparent, informative, professional",
            mandatory_disclaimers=["Mutual Fund investments are subject to market risks, read all scheme related documents carefully."],
        )
        script = VideoScript(
            title="The Compounding Journey (9:16 UGC)",
            duration_seconds=30,
            aspect_ratio="9:16",
            hook_3s="Inflation is quietly taking 6% of your savings every year.",
            problem_solution="Instead of letting money sit idle, put it to work in top diversified index funds with disciplined monthly SIPs.",
            call_to_action="Download the Finnovate app and start with ₹500 today.",
            scenes=[
                SceneCue("0-3s", "Person looking at grocery bill with concern", "Inflation eats away cash savings.", "Beat Inflation"),
                SceneCue("3-15s", "Graph showing 10-year compounding curve", "SIP lets you invest small amounts consistently.", "The Power of SIP"),
                SceneCue("15-30s", "App screen showing 1-click SIP setup", "Start your journey in under 2 minutes.", "Get Started on Finnovate"),
            ],
        )
        creative = AdCreative(
            headline="Start Disciplined SIPs for Long-Term Growth",
            primary_text="Build your wealth systematically with automated monthly investments in diversified index funds. Simple, transparent, and built for your future. Mutual fund investments are subject to market risks.",
            call_to_action="Start Investing",
            alternative_headlines=[
                "Automate Your Wealth with Monthly SIPs",
                "Beat Inflation with Disciplined Compounding",
            ],
            image_prompt="Modern smartphone showing clean investment portfolio with green upward trend line on minimal dark background.",
        )
        captions = PlatformCaptions(
            meta_caption="Make inflation work for you, not against you. Start disciplined SIP investing with Finnovate today.",
            instagram_caption="Small steps today lead to big results tomorrow. 📊 Start your monthly SIP with Finnovate.\n\nDisclaimer: Mutual Fund investments are subject to market risks, read all scheme related documents carefully.",
            linkedin_caption="Market volatility is unavoidable, but consistency is a choice. Learn how systematic investment plans help investors build long-term wealth without timing the market.",
            hashtags=["#WealthBuilding", "#SIP", "#InvestingTips", "#PersonalFinance"],
        )
        return CreativePackage(
            brief=brief,
            script=script,
            creative=creative,
            captions=captions,
            generation_mode="deterministic_fallback",
        )
