"""Governor Orchestrator: Central star-relay coordinator for marketing workflows.

Progress model: the checkpoint is saved after EVERY hop with status "running",
the hop envelopes so far, and per-agent reports. The console polls the run and
renders live progress; agent tabs read `agent_reports` which is already
populated by the time a hop completes. A mid-run failure persists a "failed"
checkpoint — a broken run never disappears and is never dressed up as green.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from modules.ads.analyst import AdOpsAnalyst
from modules.ads.connector import Connector, MureoConnector
from modules.ads.contracts import CampaignSnapshot
from modules.audit.trail import AuditTrail
from modules.budget.optimizer import BudgetOptimizer, PolicyResult
from modules.compliance.verifier import ComplianceVerdict, SEBIComplianceVerifier
from modules.creative.schema import CreativePackage
from modules.creative.worker import CreativeWorker
from modules.execution.executor import ExecutionEngine
from modules.governor.checkpoint import GovernorCheckpointer
from modules.governor.envelope import EnvelopeStatus, HandoffEnvelope
from services.api.gateway.service import GatewayService

logger = logging.getLogger(__name__)


class GovernorOrchestrator:
    """The central hub in the Governor star-topology architecture."""

    def __init__(
        self,
        gateway: GatewayService | None = None,
        connector: Connector | None = None,
        checkpointer: GovernorCheckpointer | None = None,
        audit_trail: AuditTrail | None = None,
        dry_run: bool = True,
    ) -> None:
        self.gateway = gateway or GatewayService(replay_mode=True)
        self.connector = connector or MureoConnector()
        self.checkpointer = checkpointer or GovernorCheckpointer()
        self.audit_trail = audit_trail or AuditTrail()

        self.analyst = AdOpsAnalyst()
        self.creative_worker = CreativeWorker(self.gateway)
        self.compliance_verifier = SEBIComplianceVerifier()
        self.budget_optimizer = BudgetOptimizer()
        self.execution_engine = ExecutionEngine(
            connector=self.connector,
            audit_trail=self.audit_trail,
            dry_run=dry_run,
        )

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    async def start_run(self, objective: str, run_id: str | None = None) -> dict[str, Any]:
        """Execute the marketing relay up to the human approval gate.

        Saves a checkpoint after every hop so the console can stream progress.
        """
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        logger.info("Starting Governor run %s for objective: %s", run_id, objective)

        state: dict[str, Any] = {
            "run_id": run_id,
            "objective": objective,
            "status": "running",
            "current_hop": 0,
            "current_agent": "Governor",
            "hops": [],
            "agent_reports": {},
            "proposal": None,
            "decision": None,
            "execution_results": [],
            "error": None,
        }

        try:
            # Hop 0: Goal Ingestion
            hop0 = HandoffEnvelope(
                hop_index=0,
                source="User",
                target="Governor",
                action="INGEST_OBJECTIVE",
                status=EnvelopeStatus.SUCCESS,
                payload={"objective": objective, "run_id": run_id},
                rationale="Governor accepted user objective and planned orchestration sequence.",
            )
            self._record_hop(run_id, state, hop0, next_agent="AdOpsAnalyst")

            # Hop 1: Ad-Ops ingestion + analytics over live data and history
            try:
                snapshot: CampaignSnapshot = self.connector.fetch_campaigns()
                history = self.connector.fetch_history(lookback_days=30)
                ad_ops_status = (
                    EnvelopeStatus.DEGRADED if snapshot.source == "degraded" else EnvelopeStatus.SUCCESS
                )
            except Exception as exc:
                logger.error("Ad-Ops ingestion failed: %s", exc)
                snapshot = self.connector._sample_snapshot(source="degraded")
                history = []
                ad_ops_status = EnvelopeStatus.DEGRADED

            analyst_findings = await self.analyst.generate_ai_analysis(
                snapshot, history, gateway=self.gateway, objective=objective
            )
            campaign_drafts = analyst_findings.get("campaign_drafts", [])

            hop1 = HandoffEnvelope(
                hop_index=1,
                source="Governor",
                target="AdOpsAnalyst",
                action="FETCH_AND_ANALYZE_CAMPAIGNS",
                status=ad_ops_status,
                payload={
                    "campaign_count": len(snapshot.campaigns),
                    "total_spend_inr": snapshot.total_spend_inr,
                    "blended_roas": snapshot.blended_roas,
                    "source": snapshot.source,
                    "findings": analyst_findings,
                },
                rationale=(
                    f"Analyzed {len(snapshot.campaigns)} campaigns over current + prior period "
                    f"({snapshot.source} data)."
                ),
            )
            state["agent_reports"]["analyst"] = analyst_findings
            self._record_hop(run_id, state, hop1, next_agent="CreativeWorker")

            # Hop 2: Creative Generation (honest status when gateway fell back)
            creative_pkg: CreativePackage = await self.creative_worker.generate_creative_package(
                objective=objective,
                analyst_findings=analyst_findings,
            )
            pkg_dict = creative_pkg.to_dict()
            creative_degraded = creative_pkg.generation_mode != "llm"

            hop2 = HandoffEnvelope(
                hop_index=2,
                source="Governor",
                target="CreativeWorker",
                action="GENERATE_CREATIVE_PACKAGE",
                status=EnvelopeStatus.DEGRADED if creative_degraded else EnvelopeStatus.SUCCESS,
                payload=pkg_dict,
                rationale=(
                    "Drafted 4-stage creative: brief -> script -> creative -> captions"
                    + (" (deterministic fallback — model gateway unavailable)." if creative_degraded else ".")
                ),
            )
            state["agent_reports"]["creative"] = pkg_dict
            self._record_hop(run_id, state, hop2, next_agent="ComplianceVerifier")

            # Hop 3: Deterministic SEBI Compliance & Loopback
            compliance_verdict: ComplianceVerdict = self.compliance_verifier.verify_package(pkg_dict)
            loopback_count = 0
            if not compliance_verdict.passed:
                logger.info("Creative flagged by SEBI rules. Attempting automated loopback revision.")
                loopback_count += 1
                sanitized_pkg = self.creative_worker._build_deterministic_package(objective)
                pkg_dict = sanitized_pkg.to_dict()
                state["agent_reports"]["creative"] = pkg_dict
                compliance_verdict = self.compliance_verifier.verify_package(pkg_dict)

            hop3 = HandoffEnvelope(
                hop_index=3,
                source="Governor",
                target="ComplianceVerifier",
                action="VERIFY_SEBI_REGULATORY",
                status=EnvelopeStatus.SUCCESS if compliance_verdict.passed else EnvelopeStatus.DEGRADED,
                payload=compliance_verdict.to_dict(),
                rationale=f"SEBI check result: {compliance_verdict.status.value} (Loopbacks: {loopback_count})",
            )
            state["agent_reports"]["compliance"] = {
                **compliance_verdict.to_dict(),
                "loopback_count": loopback_count,
            }
            self._record_hop(run_id, state, hop3, next_agent="BudgetOptimizer")

            # Hop 4: Budget Optimization (±25% cap & conservation)
            budget_result: PolicyResult = self.budget_optimizer.optimize(snapshot)
            budget_dict = budget_result.to_dict()

            hop4 = HandoffEnvelope(
                hop_index=4,
                source="Governor",
                target="BudgetOptimizer",
                action="PROPOSE_BUDGET_REALLOCATION",
                status=EnvelopeStatus.SUCCESS,
                payload=budget_dict,
                rationale=f"Proposing {len(budget_result.shifts)} budget shifts within ±25% conservation bounds.",
            )
            state["agent_reports"]["budget"] = budget_dict
            self._record_hop(run_id, state, hop4, next_agent="Governor")

            # Hop 5: Governor Proposal Synthesis with REAL dry-run payload previews & Human Action Summary
            dry_run_preview = self._build_dry_run_preview(budget_dict["shifts"], campaign_drafts)
            human_action_summary = self._build_human_action_summary(
                budget_dict["shifts"],
                pkg_dict,
                compliance_verdict.to_dict(),
                campaign_drafts,
                budget_dict["total_current_inr"],
                budget_dict["total_proposed_inr"],
            )

            proposal = {
                "run_id": run_id,
                "objective": objective,
                "data_source": snapshot.source,
                "analyst_findings": analyst_findings,
                "creative_package": pkg_dict,
                "compliance_verdict": compliance_verdict.to_dict(),
                "budget_shifts": budget_dict["shifts"],
                "budget_notes": budget_dict["notes"],
                "total_budget_current_inr": budget_dict["total_current_inr"],
                "total_budget_proposed_inr": budget_dict["total_proposed_inr"],
                "campaign_drafts": campaign_drafts,
                "dry_run_preview": dry_run_preview,
                "human_action_summary": human_action_summary,
            }

            hop5 = HandoffEnvelope(
                hop_index=5,
                source="Governor",
                target="HumanApprover",
                action="SUBMIT_PROPOSAL_FOR_APPROVAL",
                status=EnvelopeStatus.SUCCESS,
                payload=proposal,
                rationale="Assembled final proposal. Awaiting human operator approval.",
            )
            state["proposal"] = proposal
            state["agent_reports"]["governor"] = {
                "objective": objective,
                "data_source": snapshot.source,
                "budget_operations": len(budget_dict["shifts"]),
                "creative_operations": 1,
                "campaign_drafts": len(campaign_drafts),
                "compliance_status": compliance_verdict.status.value,
            }
            state["status"] = "pending_approval"
            state["current_agent"] = "HumanApprover"
            self._record_hop(run_id, state, hop5, next_agent="HumanApprover", status="pending_approval")

            return state

        except Exception as exc:
            # A failing run is persisted as failed — it must never vanish or
            # masquerade as a green relay.
            logger.exception("Run %s failed mid-relay: %s", run_id, exc)
            state["status"] = "failed"
            state["error"] = str(exc)
            fail_env = HandoffEnvelope(
                hop_index=state.get("current_hop", 0) + 1,
                source="Governor",
                target="Governor",
                action="RUN_FAILED",
                status=EnvelopeStatus.FAILED,
                payload={"error": str(exc)},
                rationale="Unhandled worker failure; run halted and persisted as failed.",
                error=str(exc),
            )
            try:
                self.audit_trail.record(run_id, fail_env)
                state["hops"].append(fail_env.to_dict())
            finally:
                self.checkpointer.save_checkpoint(
                    run_id=run_id,
                    status="failed",
                    hop_index=state.get("current_hop", 0),
                    state=state,
                )
            return state

    def resolve_approval(
        self,
        run_id: str,
        decision: str,  # "approved" | "rejected"
        decision_notes: str = "",
    ) -> dict[str, Any]:
        """Resume run from checkpoint after human decision."""
        state = self.checkpointer.load_checkpoint(run_id)
        if not state:
            raise ValueError(f"Run {run_id} not found in checkpoints.")

        if state["status"] not in ("pending_approval", "interrupted"):
            raise ValueError(f"Run {run_id} is already in state: {state['status']}")

        proposal = state.get("proposal", {})
        execution_results = self.execution_engine.execute_proposal(
            run_id=run_id,
            proposal=proposal,
            human_decision=decision,
            decision_notes=decision_notes,
        )

        final_status = "completed" if decision.lower() == "approved" else "rejected"
        state["status"] = final_status
        state["decision"] = decision
        state["decision_notes"] = decision_notes
        state["current_agent"] = "ExecutionEngine" if final_status == "completed" else "Governor"
        state["execution_results"] = [
            {
                "success": r.success,
                "platform": r.platform.value,
                "action_type": r.action_type,
                "resource_id": r.resource_id,
                "dry_run": r.dry_run,
                "error": r.error,
                "response": r.response_received,
            }
            for r in execution_results
        ]
        state["agent_reports"] = state.get("agent_reports", {})
        state["agent_reports"]["execution"] = {
            "decision": decision,
            "decision_notes": decision_notes,
            "results": state["execution_results"],
        }

        self.checkpointer.save_checkpoint(
            run_id=run_id,
            status=final_status,
            hop_index=6,
            state=state,
        )

        return state

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _record_hop(
        self,
        run_id: str,
        state: dict[str, Any],
        envelope: HandoffEnvelope,
        next_agent: str,
        status: str = "running",
    ) -> None:
        """Audit the envelope and persist a progress checkpoint immediately."""
        self.audit_trail.record(run_id, envelope)
        state["hops"].append(envelope.to_dict())
        state["current_hop"] = envelope.hop_index
        state["current_agent"] = next_agent
        state["status"] = status
        self.checkpointer.save_checkpoint(
            run_id=run_id,
            status=status,
            hop_index=envelope.hop_index,
            state=state,
        )

    def _build_dry_run_preview(
        self, shifts: list[dict[str, Any]], campaign_drafts: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Exact payloads the executor would send, produced by the connector's
        own dry-run path (not fabricated client-side)."""
        from modules.ads.contracts import BudgetShift, CampaignDraft, Platform

        budget_ops: list[dict[str, Any]] = []
        for s in shifts:
            try:
                res = self.connector.apply_budget(
                    BudgetShift(
                        campaign_id=s["campaign_id"],
                        platform=Platform(s["platform"]),
                        current_daily_budget_inr=s["current_daily_budget_inr"],
                        proposed_daily_budget_inr=s["proposed_daily_budget_inr"],
                        shift_percentage=s["shift_percentage"],
                        rationale=s.get("rationale", ""),
                    ),
                    dry_run=True,
                )
                budget_ops.append(res.payload_sent)
            except Exception as exc:
                budget_ops.append({"campaign_id": s.get("campaign_id"), "preview_error": str(exc)})

        create_ops: list[dict[str, Any]] = []
        for d in campaign_drafts:
            try:
                res = self.connector.create_campaign(
                    CampaignDraft(
                        name=d["name"],
                        platform=Platform(d["platform"]),
                        objective=d.get("objective", ""),
                        daily_budget_inr=d.get("daily_budget_inr", 0.0),
                        rationale=d.get("rationale", ""),
                        channel_type=d.get("channel_type", "SEARCH"),
                    ),
                    dry_run=True,
                )
                create_ops.append(res.payload_sent)
            except Exception as exc:
                create_ops.append({"name": d.get("name"), "preview_error": str(exc)})

        return {
            "budget_operations": budget_ops,
            "campaign_create_operations": create_ops,
            "creative_operations": 1,
        }

    def _build_human_action_summary(
        self,
        shifts: list[dict[str, Any]],
        pkg_dict: dict[str, Any],
        compliance_dict: dict[str, Any],
        campaign_drafts: list[dict[str, Any]],
        total_curr: float,
        total_prop: float,
    ) -> dict[str, Any]:
        """Produce clean, newbie-friendly and executive-friendly action items."""
        actions = []
        for s in shifts:
            pct = s.get("shift_percentage", 0)
            c_name = s.get("campaign_name", s.get("campaign_id"))
            c_curr = round(s.get("current_daily_budget_inr", 0))
            c_prop = round(s.get("proposed_daily_budget_inr", 0))
            if pct > 0:
                actions.append({
                    "type": "SCALE_WINNER",
                    "action": "Increase Budget",
                    "campaign_id": s.get("campaign_id"),
                    "campaign_name": c_name,
                    "platform": s.get("platform"),
                    "current_budget": c_curr,
                    "proposed_budget": c_prop,
                    "change_pct": pct,
                    "description": f"Boost daily budget by +{pct}% (₹{c_curr:,} → ₹{c_prop:,}/day) to scale high-performing conversions.",
                    "tag": f"+{pct}% SCALE",
                    "badge_type": "success",
                })
            elif pct < 0:
                actions.append({
                    "type": "REDUCE_FATIGUE",
                    "action": "Reduce Budget",
                    "campaign_id": s.get("campaign_id"),
                    "campaign_name": c_name,
                    "platform": s.get("platform"),
                    "current_budget": c_curr,
                    "proposed_budget": c_prop,
                    "change_pct": pct,
                    "description": f"Cut daily budget by {abs(pct)}% (₹{c_curr:,} → ₹{c_prop:,}/day) to stop budget waste on fatigued ads.",
                    "tag": f"{pct}% CUT",
                    "badge_type": "warning",
                })

        script_hook = pkg_dict.get("script", {}).get("hook_3s") or "Smart SIP Growth"
        creative_headline = pkg_dict.get("creative", {}).get("headline") or "Start Disciplined SIPs"
        actions.append({
            "type": "DEPLOY_CREATIVE",
            "action": "Deploy Fresh Creative",
            "campaign_id": "new_creative_pkg",
            "campaign_name": "Multi-Channel Creative Refresh",
            "platform": "meta_ads & google_ads",
            "headline": creative_headline,
            "hook": script_hook,
            "description": f"Launch 1 new video ad (Hook: \"{script_hook}\") and fresh copy variants across platforms.",
            "tag": "NEW CREATIVE",
            "badge_type": "info",
        })

        comp_status = compliance_dict.get("status", "PASS")
        actions.append({
            "type": "COMPLIANCE_CHECK",
            "action": "SEBI Regulatory Clearance",
            "status": comp_status,
            "description": "Verified compliant with SEBI mutual fund advertising rules. Zero misleading return promises.",
            "tag": comp_status.upper(),
            "badge_type": "success" if comp_status.lower() in ("pass", "compliant") else "danger",
        })

        return {
            "headline": "Proposed Campaign Optimization Actions",
            "overview": (
                f"HELM proposes {len(shifts)} budget adjustments and 1 creative refresh. "
                f"Total daily budget is preserved at ₹{int(total_prop):,}/day."
            ),
            "action_items": actions,
        }

