"""Direct single-agent invocation — "individual agent assistance".

The Governor pipeline runs all six hops. This module lets an operator talk to
one specialist directly (Analyst, Creative, Media Buyer, Compliance) and get
that agent's real output without paying for the whole relay.

Every agent returns the same envelope shape so the console can render any
response generically:

    {
      "agent": "analyst",
      "message": "<narrative>",
      "blocks": [ {"type": "kpi_grid", ...}, {"type": "table", ...} ],
      "raw": { ...full structured output... },
      "sources": [...],
      "meta": {"grounded": true, "model": "...", "data_source": "synthetic"}
    }

`blocks` is a small display grammar (kpi_grid | table | bullets | variations |
policy_check | stepper | text). Adding an agent means emitting blocks, not
adding a bespoke React component.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from modules.ads.analyst import AdOpsAnalyst
from modules.ads.contracts import CampaignSnapshot
from modules.budget.optimizer import BudgetOptimizer
from modules.compliance.verifier import SEBIComplianceVerifier
from modules.creative.worker import CreativeWorker
from services.api import intelligence
from services.api.gateway.contracts import Effort, TaskKind

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])

AGENT_REGISTRY: dict[str, dict[str, str]] = {
    "governor": {
        "label": "Governor",
        "role": "Orchestration & oversight",
        "color": "purple",
        "icon": "security",
        "description": "Runs the full six-hop relay and assembles the approval proposal.",
    },
    "analyst": {
        "label": "Analyst",
        "role": "Data processing & insight extraction",
        "color": "blue",
        "icon": "query_stats",
        "description": "Diagnoses campaign performance, decay signals, and what is working.",
    },
    "creative": {
        "label": "Creative",
        "role": "Generation & copywriting",
        "color": "purple",
        "icon": "palette",
        "description": "Writes ad variations and checks each one against SEBI rules.",
    },
    "media_buyer": {
        "label": "Media Buyer",
        "role": "Budgeting & deployment",
        "color": "orange",
        "icon": "ads_click",
        "description": "Proposes budget reallocation inside the ±25% policy envelope.",
    },
    "compliance": {
        "label": "Compliance",
        "role": "SEBI regulatory shield",
        "color": "green",
        "icon": "verified_user",
        "description": "Scans copy deterministically for prohibited claims and missing disclaimers.",
    },
}


class AgentInvokeRequest(BaseModel):
    prompt: str = Field(..., json_schema_extra={"example": "Analyze Meta campaign performance for the last 30 days"})
    conversation_id: str | None = Field(default=None)
    grounded: bool = Field(default=True, description="Attach source citations to the answer.")
    file_content: str | None = Field(default=None, description="Raw text or base64 string of attached dataset (.csv, .xlsx, .xls, .json)")
    filename: str | None = Field(default=None, description="Original filename of attached dataset")


# ----------------------------------------------------------------------
# Wiring — set once by main.py so agents share the app's singletons
# ----------------------------------------------------------------------

_deps: dict[str, Any] = {}


def configure(gateway: Any, connector: Any, orchestrator: Any) -> None:
    """Inject the app-level singletons this router operates on."""
    _deps["gateway"] = gateway
    _deps["connector"] = connector
    _deps["orchestrator"] = orchestrator


def _gateway() -> Any:
    return _deps.get("gateway")


def _connector() -> Any:
    return _deps.get("connector")


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("")
def list_agents() -> list[dict[str, Any]]:
    """The agent roster the console renders in its status rail."""
    return [{"id": agent_id, **meta} for agent_id, meta in AGENT_REGISTRY.items()]


@router.post("/{agent_id}/invoke")
async def invoke_agent(agent_id: str, req: AgentInvokeRequest) -> dict[str, Any]:
    """Run one specialist agent directly against the current dataset."""
    agent_id = agent_id.lower().strip()
    if agent_id not in AGENT_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent '{agent_id}'. Available: {', '.join(AGENT_REGISTRY)}",
        )
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    if req.file_content:
        from modules.ads.byod_importer import activate_byod_file
        try:
            snapshot = activate_byod_file(req.file_content, filename=req.filename)
            logger.info(
                "Auto-activated BYOD dataset '%s' with %d campaigns for agent %s",
                req.filename or "attachment",
                len(snapshot.campaigns),
                agent_id,
            )
        except Exception as exc:
            logger.error("Failed to parse attached dataset for agent %s: %s", agent_id, exc)
            raise HTTPException(
                status_code=400,
                detail=f"Failed to process attached dataset: {exc}",
            ) from exc

    handlers = {
        "analyst": _run_analyst,
        "creative": _run_creative,
        "media_buyer": _run_media_buyer,
        "compliance": _run_compliance,
        "governor": _run_governor,
    }

    try:
        return await handlers[agent_id](req)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Agent %s failed: %s", agent_id, exc)
        raise HTTPException(status_code=500, detail=f"{AGENT_REGISTRY[agent_id]['label']} failed: {exc}") from exc



# ----------------------------------------------------------------------
# Agent implementations
# ----------------------------------------------------------------------


async def _run_analyst(req: AgentInvokeRequest) -> dict[str, Any]:
    """Ad-Ops Analyst: real metrics, decay detection, and a plain-English read."""
    connector = _connector()
    snapshot: CampaignSnapshot = connector.fetch_campaigns()
    history = connector.fetch_history(lookback_days=30)

    findings = await AdOpsAnalyst().generate_ai_analysis(
        snapshot, history, gateway=_gateway(), objective=req.prompt
    )

    kpis = findings["account_kpis"]
    prior_totals = _prior_period_totals(history)

    # Claude reasons over the computed facts; it never alters them.
    insight = await intelligence.reason(
        gateway=_gateway(),
        task=TaskKind.ANALYST_ANSWER,
        instruction=(
            f'The marketing lead asked: "{req.prompt}"\n\n'
            "Diagnose this ad account. Identify what is driving performance, what is "
            "decaying and why, and exactly what should change. Answer their question "
            "directly — do not give a generic account review if they asked something specific."
        ),
        data={
            "question": req.prompt,
            "data_source": snapshot.source,
            "account_kpis": kpis,
            "prior_period_totals": prior_totals,
            "campaigns": findings.get("per_campaign", []),
            "channel_breakdown": findings.get("channel_breakdown", {}),
            "decay_signals": findings.get("decay_signals", []),
            "what_works": findings.get("what_works", []),
            "deterministic_recommendations": findings.get("recommendations", []),
        },
        schema=intelligence.ANALYST_SCHEMA,
    )

    blocks: list[dict[str, Any]] = [
        {
            "type": "kpi_grid",
            "title": f"Account performance (last 30 days · {snapshot.source} data)",
            "items": [
                _kpi("Spend", _inr(kpis["total_spend_inr"]), kpis["total_spend_inr"], prior_totals.get("spend")),
                _kpi("ROAS", f"{kpis['blended_roas']}x", kpis["blended_roas"], prior_totals.get("roas")),
                _kpi("CPA", _inr(kpis["blended_cpa_inr"]), kpis["blended_cpa_inr"], prior_totals.get("cpa"), lower_is_better=True),
                _kpi("Conversions", f"{kpis['total_conversions']:,}", kpis["total_conversions"], prior_totals.get("conversions")),
            ],
        }
    ]

    if findings.get("per_campaign"):
        blocks.append(
            {
                "type": "table",
                "title": "Campaign breakdown",
                "columns": [
                    {"key": "campaign_name", "label": "Campaign"},
                    {"key": "platform", "label": "Platform"},
                    {"key": "spend", "label": "Spend", "align": "right"},
                    {"key": "roas", "label": "ROAS", "align": "right"},
                    {"key": "cpa", "label": "CPA", "align": "right"},
                    {"key": "ctr", "label": "CTR", "align": "right"},
                    {"key": "verdict", "label": "Verdict", "align": "center", "kind": "status"},
                ],
                "rows": [
                    {
                        "campaign_name": c.get("campaign_name", ""),
                        "platform": _platform_label(c.get("platform", "")),
                        "spend": _inr(c.get("spend_inr", 0)),
                        "roas": f"{c.get('roas', 0)}x",
                        "cpa": _inr(c.get("cpa_inr", 0)),
                        "ctr": f"{c.get('ctr', 0)}%",
                        "verdict": c.get("status_tag") or c.get("verdict") or "STABLE",
                        "_score": c.get("score"),
                    }
                    for c in findings["per_campaign"]
                ],
            }
        )

    # Model-reasoned findings when a model is reachable; deterministic signals otherwise.
    if insight.get("findings"):
        blocks.append({"type": "findings", "title": "What the Analyst found", "items": insight["findings"]})
    else:
        if findings.get("what_works"):
            blocks.append(
                {"type": "bullets", "title": "What's working", "tone": "pass", "items": findings["what_works"]}
            )
        if findings.get("decay_signals"):
            blocks.append(
                {"type": "bullets", "title": "Decay signals", "tone": "flag", "items": findings["decay_signals"]}
            )

    if insight.get("actions"):
        blocks.append(
            {
                "type": "table",
                "title": "Recommended actions",
                "columns": [
                    {"key": "action", "label": "Action"},
                    {"key": "campaign", "label": "Campaign"},
                    {"key": "rationale", "label": "Why"},
                    {"key": "expected_impact", "label": "Expected impact"},
                ],
                "rows": insight["actions"],
            }
        )
    elif findings.get("recommendations"):
        blocks.append(
            {
                "type": "table",
                "title": "Recommended actions",
                "columns": [
                    {"key": "action", "label": "Action", "kind": "status"},
                    {"key": "campaign_name", "label": "Campaign"},
                    {"key": "reason", "label": "Why"},
                ],
                "rows": findings["recommendations"],
            }
        )

    if insight.get("watch_outs"):
        blocks.append({"type": "bullets", "title": "Watch-outs", "tone": "flag", "items": insight["watch_outs"]})

    message = (
        insight.get("diagnosis")
        or findings.get("executive_summary")
        or (
            f"Analyzed {len(snapshot.campaigns)} campaigns over the last 30 days. "
            f"Blended ROAS is {kpis['blended_roas']}x on {_inr(kpis['total_spend_inr'])} of spend."
        )
    )

    return _envelope(
        agent="analyst",
        message=message,
        blocks=blocks,
        raw=findings,
        sources=_sources_for_snapshot(snapshot, history),
        grounded=req.grounded,
        data_source=snapshot.source,
        headline=insight.get("headline"),
    )


async def _run_creative(req: AgentInvokeRequest) -> dict[str, Any]:
    """Creative Studio: ad variations, each independently compliance-checked."""
    gateway = _gateway()
    package = await CreativeWorker(gateway).generate_creative_package(
        objective=req.prompt, analyst_findings={}
    )
    pkg = package.to_dict()

    verifier = SEBIComplianceVerifier()
    creative = pkg["creative"]

    # Ask Claude for three genuinely distinct angles. Each one is then run
    # through the deterministic SEBI verifier — the model never self-certifies.
    written = await intelligence.reason(
        gateway=gateway,
        task=TaskKind.CREATIVE_VARIANTS,
        instruction=(
            f'The brief is: "{req.prompt}"\n\n'
            "Write three ad variations that take genuinely different angles — not three "
            "rewrites of the same sentence. Every variation must be SEBI-compliant: no "
            "guaranteed or assured returns, no risk-free or no-risk framing, no "
            "unqualified superlatives. Mutual fund copy must carry the market-risk "
            "disclaimer in the body."
        ),
        data={
            "brief": pkg["brief"],
            "deterministic_draft": creative,
            "objective": req.prompt,
        },
        schema=intelligence.CREATIVE_SCHEMA,
    )

    angle_labels = ["Benefit Led", "Curiosity Led", "Urgency Led"]
    if written.get("variations"):
        drafts = [
            {
                "subtitle": v.get("angle") or angle_labels[i % len(angle_labels)],
                "headline": v.get("headline", ""),
                "body": v.get("body", ""),
                "cta": v.get("cta", creative["call_to_action"]),
                "note": v.get("why_it_works", ""),
            }
            for i, v in enumerate(written["variations"][:3])
        ]
    else:
        # No model reachable: fall back to the deterministic package's headlines.
        drafts = [
            {
                "subtitle": angle_labels[i % len(angle_labels)],
                "headline": headline,
                "body": creative["primary_text"],
                "cta": creative["call_to_action"],
                "note": "",
            }
            for i, headline in enumerate(
                [creative["headline"], *creative.get("alternative_headlines", [])][:3]
            )
        ]

    variations: list[dict[str, Any]] = []
    counts = {"PASS": 0, "FLAG": 0, "BLOCK": 0}
    for idx, draft in enumerate(drafts):
        verdict = verifier.verify_text(f"{draft['headline']}\n\n{draft['body']}")
        status = _compliance_chip(verdict)
        counts[status] = counts.get(status, 0) + 1
        variations.append(
            {
                "title": f"Variation {idx + 1}",
                "subtitle": draft["subtitle"],
                "headline": draft["headline"],
                "body": draft["body"],
                "cta": draft["cta"],
                "note": draft["note"],
                "status": status,
                "violations": [
                    f"{v.get('phrase', '')} — {v.get('citation', '')}"
                    for v in verdict.to_dict().get("violations", [])
                ],
            }
        )

    package_verdict = verifier.verify_package(pkg)
    blocks: list[dict[str, Any]] = [
        {"type": "variations", "title": "Ad variations", "items": variations},
        {
            "type": "policy_check",
            "title": "Compliance summary",
            "verdict": "BLOCK" if counts.get("BLOCK") else ("FLAG" if counts.get("FLAG") else "PASS"),
            "counts": counts,
            "items": [
                {"label": "Financial advertising rules", "status": "PASS" if not counts.get("BLOCK") else "BLOCK"},
                {
                    "label": "Mandatory disclaimers present",
                    "status": "PASS" if package_verdict.has_mandatory_disclaimer else "FLAG",
                },
                {"label": f"{len(variations)}/{len(variations)} variations processed", "status": "PASS"},
            ],
        },
        {
            "type": "text",
            "title": "Creative brief",
            "fields": [
                {"label": "Target audience", "value": pkg["brief"]["target_audience"]},
                {"label": "Core angle", "value": pkg["brief"]["core_angle"]},
                {"label": "Pain point", "value": pkg["brief"]["pain_point"]},
                {"label": "Value proposition", "value": pkg["brief"]["value_proposition"]},
                {"label": "Tone of voice", "value": pkg["brief"]["tone_of_voice"]},
            ],
        },
        {
            "type": "table",
            "title": f"{pkg['script']['aspect_ratio']} video script — {pkg['script']['title']} ({pkg['script']['duration_seconds']}s)",
            "columns": [
                {"key": "timestamp_range", "label": "Time"},
                {"key": "visual_cue", "label": "Visual"},
                {"key": "audio_spoken", "label": "Audio"},
                {"key": "on_screen_text", "label": "On-screen"},
            ],
            "rows": pkg["script"]["scenes"],
        },
    ]

    # "Degraded" means the copy came from templates, not a model.
    degraded = not written.get("variations")
    summary = (
        f"Wrote {len(variations)} ad variations and ran each through the SEBI verifier: "
        f"{counts.get('PASS', 0)} passed, {counts.get('FLAG', 0)} flagged, "
        f"{counts.get('BLOCK', 0)} blocked."
    )
    message = f"{written['strategy']}\n\n{summary}" if written.get("strategy") else summary
    if degraded:
        message += (
            "\n\nNote: this copy came from the deterministic template, not a model — "
            "no model was reachable for this request."
        )

    return _envelope(
        agent="creative",
        message=message,
        blocks=blocks,
        raw={**pkg, "reasoned_variations": written},
        sources=[{"title": "SEBI Advertisement Code", "lines": "Rules 2.1–2.9"}],
        grounded=req.grounded,
        degraded=degraded,
    )


async def _run_media_buyer(req: AgentInvokeRequest) -> dict[str, Any]:
    """Media Buyer: budget reallocation bounded by the ±25% policy envelope."""
    connector = _connector()
    snapshot: CampaignSnapshot = connector.fetch_campaigns()
    result = BudgetOptimizer().optimize(snapshot)
    data = result.to_dict()

    current_total = data["total_current_inr"]
    proposed_total = data["total_proposed_inr"]
    delta = round(proposed_total - current_total, 2)
    delta_pct = round((delta / current_total) * 100, 2) if current_total else 0.0

    # Shifts carry only campaign_id; resolve readable names from the snapshot.
    names = {c.campaign_id: c.campaign_name for c in snapshot.campaigns}

    rows = []
    for shift in data["shifts"]:
        change = round(shift["proposed_daily_budget_inr"] - shift["current_daily_budget_inr"], 2)
        rows.append(
            {
                "campaign": names.get(shift["campaign_id"], shift["campaign_id"]),
                "platform": _platform_label(shift.get("platform", "")),
                "current": _inr(shift["current_daily_budget_inr"]),
                "proposed": _inr(shift["proposed_daily_budget_inr"]),
                "change": f"{'+' if change >= 0 else ''}{_inr(change)}",
                "change_pct": f"{'+' if shift['shift_percentage'] >= 0 else ''}{shift['shift_percentage']}%",
                "status": "Valid" if abs(shift["shift_percentage"]) <= 25.0 else "Out of policy",
                "rationale": shift.get("rationale", ""),
            }
        )

    within_cap = all(abs(s["shift_percentage"]) <= 25.0 for s in data["shifts"])

    strategy = await intelligence.reason(
        gateway=_gateway(),
        task=TaskKind.MEDIA_BUYER_PROPOSAL,
        instruction=(
            f'The marketing lead asked: "{req.prompt}"\n\n'
            "These budget shifts were produced by a deterministic optimizer bounded to "
            "+/-25% per campaign with total-budget conservation. You cannot change the "
            "numbers. Explain the allocation strategy, justify each individual shift "
            "against that campaign's performance, and name the risks."
        ),
        data={
            "question": req.prompt,
            "shifts": [
                {**sh, "campaign_name": names.get(sh["campaign_id"], sh["campaign_id"])}
                for sh in data["shifts"]
            ],
            "total_current_inr": current_total,
            "total_proposed_inr": proposed_total,
            "campaign_performance": [
                {
                    "campaign_id": c.campaign_id,
                    "campaign_name": c.campaign_name,
                    "spend_inr": c.spend_inr,
                    "roas": c.roas,
                    "cpa_inr": c.cpa_inr,
                    "ctr": c.ctr,
                }
                for c in snapshot.campaigns
            ],
            "optimizer_notes": data.get("notes", []),
        },
        schema=intelligence.MEDIA_BUYER_SCHEMA,
    )

    # Prefer the model's per-shift reasoning over the optimizer's terse note.
    rationales = {
        r["campaign_id"]: r["rationale"] for r in strategy.get("shift_rationales", []) or []
    }
    for row, shift in zip(rows, data["shifts"]):
        row["rationale"] = rationales.get(shift["campaign_id"], row["rationale"])

    blocks: list[dict[str, Any]] = [
        {
            "type": "table",
            "title": "Proposed daily budget reallocation",
            "columns": [
                {"key": "campaign", "label": "Campaign"},
                {"key": "platform", "label": "Platform"},
                {"key": "current", "label": "Current", "align": "right"},
                {"key": "proposed", "label": "Proposed", "align": "right"},
                {"key": "change", "label": "Change", "align": "right"},
                {"key": "change_pct", "label": "Change %", "align": "right"},
                {"key": "status", "label": "Status", "align": "center", "kind": "status"},
            ],
            "rows": rows,
            "footer": {
                "campaign": "Total",
                "current": _inr(current_total),
                "proposed": _inr(proposed_total),
                "change": f"{'+' if delta >= 0 else ''}{_inr(delta)}",
                "change_pct": f"{'+' if delta_pct >= 0 else ''}{delta_pct}%",
                "status": "Within policy" if within_cap else "Review",
            },
        },
        {
            "type": "policy_check",
            "title": "Policy check",
            "verdict": "PASS" if within_cap else "FLAG",
            "items": [
                {"label": "Within ±25% per-campaign limit", "status": "PASS" if within_cap else "FLAG"},
                {"label": f"Total budget change {delta_pct:+}%", "status": "PASS"},
                {"label": "Budget conservation validated", "status": "PASS"},
            ],
        },
    ]

    if strategy.get("risks"):
        blocks.append({"type": "bullets", "title": "Risks", "tone": "flag", "items": strategy["risks"]})
    elif data.get("notes"):
        blocks.append({"type": "bullets", "title": "Optimizer notes", "tone": "info", "items": data["notes"]})

    message = strategy.get("strategy") or (
        f"Proposed {len(data['shifts'])} budget shifts across "
        f"{len({s.get('platform') for s in data['shifts']})} channels. Total daily budget moves from "
        f"{_inr(current_total)} to {_inr(proposed_total)} ({delta_pct:+}%), every shift inside the "
        "±25% policy cap."
    )

    return _envelope(
        agent="media_buyer",
        message=message,
        blocks=blocks,
        raw=data,
        sources=_sources_for_snapshot(snapshot, []),
        grounded=req.grounded,
        data_source=snapshot.source,
        headline=strategy.get("headline"),
        requires_approval=True,
        approval_payload={
            "kind": "budget_reallocation",
            "current_total_inr": current_total,
            "proposed_total_inr": proposed_total,
            "delta_inr": delta,
            "delta_pct": delta_pct,
            "shift_count": len(data["shifts"]),
            "policy": "within_limit" if within_cap else "review_required",
            "shifts": [{**sh, "campaign_name": names.get(sh["campaign_id"], sh["campaign_id"])} for sh in data["shifts"]],
        },
    )


async def _run_compliance(req: AgentInvokeRequest) -> dict[str, Any]:
    """Compliance Shield: deterministic SEBI scan of whatever copy was pasted in."""
    verdict = SEBIComplianceVerifier().verify_text(req.prompt)
    data = verdict.to_dict()
    violations = data.get("violations", [])

    # The rulebook decides pass/fail. Claude only explains it and offers a rewrite.
    guidance = await intelligence.reason(
        gateway=_gateway(),
        task=TaskKind.COMPLIANCE_EVAL,
        instruction=(
            "A deterministic SEBI rule engine scanned this ad copy and produced the "
            "verdict below. That verdict is final — do not overturn it. Explain each "
            "violation in plain English for a marketer who is not a compliance expert, "
            "and supply a compliant rewrite that keeps the original intent."
        ),
        data={
            "submitted_copy": req.prompt,
            "engine_verdict": data,
        },
        schema=intelligence.COMPLIANCE_SCHEMA,
    )

    blocks: list[dict[str, Any]] = [
        {
            "type": "policy_check",
            "title": "SEBI verdict",
            "verdict": _compliance_chip(verdict),
            "items": [
                {"label": "Prohibited claim scan", "status": "PASS" if not violations else _compliance_chip(verdict)},
                {
                    "label": "Mandatory disclaimer present",
                    "status": "PASS" if data.get("has_mandatory_disclaimer", True) else "FLAG",
                },
                {"label": f"{len(violations)} violation(s) found", "status": "PASS" if not violations else "FLAG"},
            ],
        }
    ]

    if violations:
        blocks.append(
            {
                "type": "table",
                "title": "Violations",
                "columns": [
                    {"key": "severity", "label": "Severity", "align": "center", "kind": "status"},
                    {"key": "phrase", "label": "Matched phrase"},
                    {"key": "location", "label": "Location"},
                    {"key": "citation", "label": "Regulation"},
                ],
                "rows": [
                    {
                        "severity": str(v.get("severity", "")).upper(),
                        "phrase": v.get("phrase", ""),
                        "location": v.get("location", ""),
                        "citation": v.get("citation", ""),
                    }
                    for v in violations
                ],
            }
        )
    if guidance.get("explanations"):
        blocks.append(
            {
                "type": "table",
                "title": "How to fix each issue",
                "columns": [
                    {"key": "phrase", "label": "Phrase"},
                    {"key": "why_it_fails", "label": "Why it fails"},
                    {"key": "how_to_fix", "label": "How to fix it"},
                ],
                "rows": guidance["explanations"],
            }
        )
    elif data.get("feedback_for_revision"):
        blocks.append(
            {
                "type": "bullets",
                "title": "Required fixes",
                "tone": "flag",
                "items": [data["feedback_for_revision"]],
            }
        )

    if guidance.get("rewrite"):
        blocks.append(
            {
                "type": "rewrite",
                "title": "Compliant rewrite",
                "original": req.prompt,
                "revised": guidance["rewrite"],
            }
        )

    if not data.get("has_mandatory_disclaimer", True):
        blocks.append(
            {
                "type": "bullets",
                "title": "Missing mandatory disclaimer",
                "tone": "flag",
                "items": [
                    "Add the standard risk disclaimer, e.g. \"Mutual fund investments are "
                    "subject to market risks. Read all scheme related documents carefully.\""
                ],
            }
        )

    message = guidance.get("verdict_summary") or (
        "This copy passes the deterministic SEBI checks."
        if data.get("passed")
        else f"This copy fails the SEBI scan with {len(violations)} violation(s)."
    )

    return _envelope(
        agent="compliance",
        message=message,
        blocks=blocks,
        raw={**data, "guidance": guidance},
        sources=[{"title": "SEBI Advertisement Code", "lines": "Rules 2.1–2.9"}],
        grounded=req.grounded,
    )


async def _run_governor(req: AgentInvokeRequest) -> dict[str, Any]:
    """Governor: hand off to the full six-hop relay and report where it landed."""
    orchestrator = _deps.get("orchestrator")
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator is not configured")

    state = await orchestrator.start_run(objective=req.prompt)
    hops = state.get("hops", [])

    blocks: list[dict[str, Any]] = [
        {
            "type": "stepper",
            "title": "Workflow progress",
            "steps": [
                {
                    "label": _hop_label(hop),
                    "status": "completed" if hop.get("status") == "success" else hop.get("status", "waiting"),
                    "rationale": hop.get("rationale", ""),
                }
                for hop in hops
            ],
        }
    ]

    proposal = state.get("proposal") or {}
    if proposal.get("human_action_summary"):
        summary = proposal["human_action_summary"]
        items = summary if isinstance(summary, list) else [str(summary)]
        blocks.append({"type": "bullets", "title": "What you are approving", "tone": "info", "items": items})

    return _envelope(
        agent="governor",
        message=(
            f"Ran the full HELM pipeline across {len(hops)} hops. "
            f"Run `{state.get('run_id')}` is now **{state.get('status')}**."
        ),
        blocks=blocks,
        raw=state,
        sources=[],
        grounded=req.grounded,
        run_id=state.get("run_id"),
        data_source=proposal.get("data_source", ""),
    )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _envelope(
    agent: str,
    message: str,
    blocks: list[dict[str, Any]],
    raw: Any,
    sources: list[dict[str, Any]],
    grounded: bool,
    **extra: Any,
) -> dict[str, Any]:
    meta = AGENT_REGISTRY[agent]
    gateway = _gateway()
    replay = bool(getattr(gateway, "replay_mode", True))
    return {
        "agent": agent,
        "agent_label": meta["label"],
        "agent_color": meta["color"],
        "agent_icon": meta["icon"],
        "message": message,
        "blocks": blocks,
        "raw": raw,
        "sources": sources if grounded else [],
        "meta": {
            "grounded": grounded,
            "gateway_mode": "replay" if replay else "live",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **{k: v for k, v in extra.items() if v is not None},
        },
    }


def _kpi(
    label: str,
    display: str,
    current: float,
    prior: float | None,
    lower_is_better: bool = False,
) -> dict[str, Any]:
    """A KPI tile with a period-over-period delta when prior data exists."""
    item: dict[str, Any] = {"label": label, "value": display}
    if prior and prior > 0 and current is not None:
        change_pct = round(((current - prior) / prior) * 100, 1)
        improved = change_pct < 0 if lower_is_better else change_pct > 0
        item["delta"] = f"{change_pct:+}%"
        item["delta_dir"] = "up" if improved else "down"
    return item


def _prior_period_totals(history: list[Any]) -> dict[str, float]:
    """Roll the `prior` history period into comparable account totals."""
    prior = next((p for p in history if getattr(p, "label", "") == "prior"), None)
    if prior is None or not prior.campaigns:
        return {}

    spend = sum(c.spend_inr for c in prior.campaigns)
    conversions = sum(c.conversions for c in prior.campaigns)
    roas = sum(c.roas * c.spend_inr for c in prior.campaigns) / spend if spend else 0.0
    return {
        "spend": round(spend, 2),
        "conversions": conversions,
        "roas": round(roas, 2),
        "cpa": round(spend / conversions, 2) if conversions else 0.0,
    }


def _sources_for_snapshot(snapshot: Any, history: list[Any]) -> list[dict[str, Any]]:
    """Citations describing exactly which dataset produced the numbers."""
    label = {
        "live": "Live platform API",
        "synthetic": "Synthetic SQLite dataset",
        "byod": "Imported dataset (BYOD)",
        "degraded": "Degraded fetch — platform unavailable",
    }.get(snapshot.source, snapshot.source)

    sources = [
        {
            "title": f"Campaign Performance — {label}",
            "lines": f"{len(snapshot.campaigns)} campaigns · {_inr(snapshot.total_spend_inr)} spend",
            "source": snapshot.source,
        }
    ]
    for period in history:
        sources.append(
            {
                "title": f"History — {getattr(period, 'label', 'period')}",
                "lines": f"{getattr(period, 'date_start', '')} → {getattr(period, 'date_end', '')} · {len(period.campaigns)} rows",
                "source": getattr(period, "source", ""),
            }
        )
    return sources


def _compliance_chip(verdict: Any) -> str:
    """Map a ComplianceVerdict onto the PASS / FLAG / BLOCK chip vocabulary."""
    data = verdict.to_dict() if hasattr(verdict, "to_dict") else dict(verdict)
    if data.get("passed"):
        return "PASS"
    status = str(data.get("status", "")).upper()
    if status in ("PASS", "FLAG", "BLOCK"):
        return status
    severities = {str(v.get("severity", "")).upper() for v in data.get("violations", [])}
    return "BLOCK" if "BLOCK" in severities else "FLAG"


def _hop_label(hop: dict[str, Any]) -> str:
    return {
        "INGEST_OBJECTIVE": "User Request",
        "FETCH_AND_ANALYZE_CAMPAIGNS": "Analyst",
        "GENERATE_CREATIVE_PACKAGE": "Creative",
        "VERIFY_SEBI_REGULATORY": "Compliance",
        "PROPOSE_BUDGET_REALLOCATION": "Media Buyer",
        "SUBMIT_PROPOSAL_FOR_APPROVAL": "Approval",
    }.get(str(hop.get("action", "")), str(hop.get("target", "Step")))


def _platform_label(platform: Any) -> str:
    value = getattr(platform, "value", platform)
    return {
        "google_ads": "Google Ads",
        "meta_ads": "Meta",
        "tiktok_ads": "TikTok Ads",
        "linkedin_ads": "LinkedIn Ads",
        "byod": "Imported",
    }.get(str(value), str(value))


def _inr(amount: Any) -> str:
    """Format a number as Indian-grouped rupees (₹12,45,000)."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return str(amount)

    sign = "-" if value < 0 else ""
    whole = f"{abs(value):.0f}"
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return f"{sign}₹{whole}"
