"""The reasoning layer that makes HELM's agents smart.

Division of responsibility, deliberately strict:

  * **Deterministic code owns the facts and the guardrails.** Metrics, decay
    detection, the ±25% budget cap, conservation, and the SEBI rulebook are
    computed in Python. A model never gets to move a number or clear a policy.
  * **Claude owns the judgement.** Given those facts, it explains what is
    happening, why it matters, what to do, and what the risk is.

That split is what lets the console show model-written strategy without ever
letting a hallucination reach an ad account.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from services.api.gateway.contracts import (
    CompletionRequest,
    Effort,
    Message,
    Role,
    TaskKind,
)

logger = logging.getLogger(__name__)

HOUSE_STYLE = """You are a senior specialist inside HELM, an autonomous marketing
operations control plane used by an Indian financial-services advertiser (mutual
funds, SIPs, ELSS). Your audience is a marketing lead who is sharp but not an
ad-ops specialist.

How you write:
- Lead with the decision or the finding, never with preamble.
- Quantify. "CPA rose 285% to Rs 648" beats "CPA increased significantly".
- Name specific campaigns. Never say "some campaigns".
- Explain the mechanism, not just the metric: why did this happen?
- Currency is INR. Write it as Rs 12,45,000 (Indian digit grouping).
- No hedging, no filler, no restating the question.
- Never invent a number. Every figure must come from the data you were given.

Regulatory context: SEBI prohibits guaranteed/assured return claims, risk-free
framing, and unqualified superlatives in financial advertising. Mutual fund
creatives require the market-risk disclaimer."""


async def reason(
    gateway: Any,
    task: TaskKind,
    instruction: str,
    data: dict[str, Any],
    schema: dict[str, Any],
    effort: Effort = Effort.HIGH,
    max_tokens: int = 8000,
) -> dict[str, Any]:
    """Ask Claude to reason over already-computed facts and return structured JSON.

    Returns `{}` when no model is reachable (replay mode, missing key, provider
    error). Callers must treat an empty dict as "no narrative available" and
    still render their deterministic output — the console degrades to facts
    without commentary rather than failing.
    """
    if gateway is None or getattr(gateway, "replay_mode", True):
        return {}

    prompt = (
        f"{instruction}\n\n"
        "Here is the verified data. These numbers are computed and authoritative — "
        "use them exactly, do not recompute or adjust them:\n\n"
        f"```json\n{json.dumps(data, indent=2, default=str)}\n```\n\n"
        "Respond with JSON matching the required schema. No prose outside the JSON."
    )

    request = CompletionRequest(
        task=task,
        messages=[Message(role=Role.USER, content=prompt)],
        system_cacheable=HOUSE_STYLE,
        max_tokens=max_tokens,
        effort=effort,
        json_schema=schema,
    )

    try:
        response = await gateway.generate(request)
    except Exception as exc:
        logger.warning("Reasoning pass failed for %s; falling back to deterministic output: %s", task, exc)
        return {}

    parsed = _parse_json(response.content)
    if not isinstance(parsed, dict):
        logger.warning("Reasoning pass for %s returned non-object JSON; ignoring.", task)
        return {}
    return parsed


def _parse_json(content: str) -> Any:
    """Parse a model response that may be bare JSON or fenced in markdown."""
    text = (content or "").strip()
    if not text:
        return None

    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Salvage the outermost JSON object if the model wrapped it in prose.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    logger.warning("Could not parse reasoning response as JSON (%d chars).", len(text))
    return None


# ----------------------------------------------------------------------
# Schemas — one per agent, shaping exactly what the console renders
# ----------------------------------------------------------------------


def _array_of_strings(description: str, max_items: int = 6) -> dict[str, Any]:
    """A string array. Cardinality lives in the description — `maxItems` is
    rejected by structured outputs."""
    return {
        "type": "array",
        "description": f"{description} At most {max_items} items.",
        "items": {"type": "string"},
    }


ANALYST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "diagnosis", "findings", "actions", "watch_outs"],
    "properties": {
        "headline": {
            "type": "string",
            "description": "One sentence stating the single most important thing about this account right now.",
        },
        "diagnosis": {
            "type": "string",
            "description": "2-4 sentences explaining account health and the mechanism behind it.",
        },
        "findings": {
            "type": "array",
            "description": "3-5 findings, most important first.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "detail", "severity"],
                "properties": {
                    "title": {"type": "string", "description": "Short label, max 8 words."},
                    "detail": {"type": "string", "description": "What is happening and why, with numbers."},
                    "severity": {"type": "string", "enum": ["critical", "warning", "opportunity", "healthy"]},
                },
            },
        },
        "actions": {
            "type": "array",
            "description": "Up to 5 concrete actions, highest impact first.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["action", "campaign", "rationale", "expected_impact"],
                "properties": {
                    "action": {"type": "string", "description": "Imperative, e.g. 'Cut budget 25%'."},
                    "campaign": {"type": "string", "description": "Exact campaign name from the data."},
                    "rationale": {"type": "string"},
                    "expected_impact": {"type": "string", "description": "Quantified where possible."},
                },
            },
        },
        "watch_outs": _array_of_strings("Risks or caveats the marketing lead should know.", 4),
    },
}


MEDIA_BUYER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "strategy", "shift_rationales", "risks"],
    "properties": {
        "headline": {"type": "string", "description": "One sentence summarizing the reallocation."},
        "strategy": {
            "type": "string",
            "description": "2-4 sentences on the allocation logic and what it should achieve.",
        },
        "shift_rationales": {
            "type": "array",
            "description": "One entry per budget shift in the data.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["campaign_id", "rationale"],
                "properties": {
                    "campaign_id": {"type": "string", "description": "Must match a campaign_id in the data."},
                    "rationale": {"type": "string", "description": "Why this specific move, with numbers."},
                },
            },
        },
        "risks": _array_of_strings("What could go wrong with this reallocation.", 4),
    },
}


COMPLIANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict_summary", "explanations", "rewrite"],
    "properties": {
        "verdict_summary": {
            "type": "string",
            "description": "One or two sentences on whether this copy can run and why.",
        },
        "explanations": {
            "type": "array",
            "description": "One entry per violation found by the rule engine.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["phrase", "why_it_fails", "how_to_fix"],
                "properties": {
                    "phrase": {"type": "string", "description": "The exact offending phrase from the copy."},
                    "why_it_fails": {"type": "string", "description": "Plain-English regulatory reasoning."},
                    "how_to_fix": {"type": "string", "description": "Concrete replacement wording."},
                },
            },
        },
        "rewrite": {
            "type": "string",
            "description": "A compliant rewrite of the submitted copy, preserving its intent and including the market-risk disclaimer where required. Empty string if the copy already passes.",
        },
    },
}


CREATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["strategy", "variations"],
    "properties": {
        "strategy": {
            "type": "string",
            "description": "2-3 sentences on the creative angle and who it targets.",
        },
        "variations": {
            "type": "array",
            "description": "Exactly 3 variations, each a distinct angle.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["angle", "headline", "body", "cta", "why_it_works"],
                "properties": {
                    "angle": {"type": "string", "description": "e.g. 'Benefit led', 'Curiosity led', 'Urgency led'."},
                    "headline": {"type": "string", "description": "Max 12 words. SEBI-compliant."},
                    "body": {
                        "type": "string",
                        "description": "2-3 sentences. Must include the market-risk disclaimer for mutual fund copy.",
                    },
                    "cta": {"type": "string", "description": "Max 4 words."},
                    "why_it_works": {"type": "string", "description": "One sentence on the psychology."},
                },
            },
        },
    },
}


GOVERNOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["executive_summary", "decision_points", "recommendation"],
    "properties": {
        "executive_summary": {
            "type": "string",
            "description": "3-5 sentences a marketing lead can read before approving.",
        },
        "decision_points": {
            "type": "array",
            "description": "3-6 points the approver must weigh.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["point", "detail"],
                "properties": {
                    "point": {"type": "string", "description": "What is being decided, max 10 words."},
                    "detail": {"type": "string", "description": "The concrete change and its rationale."},
                },
            },
        },
        "recommendation": {
            "type": "string",
            "enum": ["approve", "approve_with_changes", "reject"],
            "description": "What the Governor advises the human approver to do.",
        },
    },
}
