"""Empirical Adversarial Stress Tests for Governor Star Relay & Checkpointer.

Verifies:
1. Checkpoint persistence across all 6 hops (Hops 0, 1, 2, 3, 4, 5, 6).
2. Rejection flow (operator rejects proposal -> state becomes 'rejected', execution results empty, no ad platform actions dispatched, audit trail logs rejection).
3. Unapproved execution strictly blocked (calling ExecutionEngine without approved status, or calling resolve_approval on completed/rejected runs).
4. Mid-run failure persistence (unhandled worker exceptions are persisted as 'failed' checkpoints, never lost or disguised as green).
5. Loopback retry logic when initial creative generation fails compliance.
"""

import pytest
import sqlite3
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from modules.ads.contracts import Platform
from modules.audit.trail import AuditTrail
from modules.compliance.verifier import ComplianceStatus, SEBIComplianceVerifier
from modules.creative.schema import (
    AdCreative,
    CreativeBrief,
    CreativePackage,
    PlatformCaptions,
    SceneCue,
    VideoScript,
)
from modules.execution.executor import ExecutionEngine
from modules.governor.checkpoint import GovernorCheckpointer
from modules.governor.orchestrator import GovernorOrchestrator
from services.api.gateway.service import GatewayService


class TestGovernorStarRelayAdversarial:
    """Stress testing Governor Star Relay, Checkpointer, and Execution Security."""

    @pytest.mark.asyncio
    async def test_checkpoint_persistence_across_all_hops(self, tmp_path: Path):
        """Verify checkpoint SQLite database stores durable state across every single hop."""
        db_path = tmp_path / "relay_checkpoints.sqlite"
        audit_db = tmp_path / "relay_audit.sqlite"

        checkpointer = GovernorCheckpointer(db_path=db_path)
        audit_trail = AuditTrail(db_path=audit_db)
        gateway = GatewayService(replay_mode=True)

        orchestrator = GovernorOrchestrator(
            gateway=gateway,
            checkpointer=checkpointer,
            audit_trail=audit_trail,
            dry_run=True,
        )

        run_state = await orchestrator.start_run(objective="Scale high-performing search campaigns")
        run_id = run_state["run_id"]

        # Directly query SQLite database table to verify persistence
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT run_id, status, current_hop_index, state_json FROM checkpoints WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            assert row is not None
            c_run_id, c_status, c_hop, c_state_json = row
            assert c_run_id == run_id
            assert c_status == "pending_approval"
            assert c_hop == 5
            saved_state = json.loads(c_state_json)
            assert len(saved_state["hops"]) == 6  # Hops 0, 1, 2, 3, 4, 5
            assert "analyst" in saved_state["agent_reports"]
            assert "creative" in saved_state["agent_reports"]
            assert "compliance" in saved_state["agent_reports"]
            assert "budget" in saved_state["agent_reports"]
            assert "governor" in saved_state["agent_reports"]

        # Resolve with human approval -> Hop 6
        final_state = orchestrator.resolve_approval(
            run_id=run_id,
            decision="approved",
            decision_notes="Approved by Investment Committee",
        )
        assert final_state["status"] == "completed"

        # Verify SQLite checkpoint updated to completed at hop 6
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, current_hop_index FROM checkpoints WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            assert row[0] == "completed"
            assert row[1] == 6

    @pytest.mark.asyncio
    async def test_rejection_flow_strictly_prevents_execution(self, tmp_path: Path):
        """Verify operator rejection marks run rejected, leaves executions empty, and records audit trail."""
        db_path = tmp_path / "reject_checkpoints.sqlite"
        audit_db = tmp_path / "reject_audit.sqlite"

        checkpointer = GovernorCheckpointer(db_path=db_path)
        audit_trail = AuditTrail(db_path=audit_db)
        orchestrator = GovernorOrchestrator(
            gateway=GatewayService(replay_mode=True),
            checkpointer=checkpointer,
            audit_trail=audit_trail,
            dry_run=True,
        )

        run_state = await orchestrator.start_run(objective="Test risky campaign scaling")
        run_id = run_state["run_id"]

        rejected_state = orchestrator.resolve_approval(
            run_id=run_id,
            decision="rejected",
            decision_notes="Budget exceeds quarterly threshold",
        )

        assert rejected_state["status"] == "rejected"
        assert rejected_state["decision"] == "rejected"
        assert rejected_state["decision_notes"] == "Budget exceeds quarterly threshold"
        assert len(rejected_state["execution_results"]) == 0

        # Audit trail must have REJECTED_BY_OPERATOR
        trail = audit_trail.get_trail(run_id)
        assert any(e["action"] == "REJECTED_BY_OPERATOR" for e in trail)

    def test_unapproved_execution_blocked(self, tmp_path: Path):
        """Verify ExecutionEngine directly blocks any dispatch without approved human decision."""
        audit_db = tmp_path / "exec_audit.sqlite"
        audit_trail = AuditTrail(db_path=audit_db)
        engine = ExecutionEngine(audit_trail=audit_trail, dry_run=True)

        proposal = {
            "budget_shifts": [
                {
                    "campaign_id": "cmp_1",
                    "platform": "meta_ads",
                    "current_daily_budget_inr": 1000.0,
                    "proposed_daily_budget_inr": 1250.0,
                    "shift_percentage": 25.0,
                    "rationale": "scale",
                }
            ]
        }

        # Decisions that MUST be blocked
        blocked_decisions = ["rejected", "pending", "denied", "unknown", "", "none", "CANCELLED"]
        for decision in blocked_decisions:
            results = engine.execute_proposal(
                run_id=f"run_blocked_{decision}",
                proposal=proposal,
                human_decision=decision,
                decision_notes="Unauthorized attempt",
            )
            assert len(results) == 0, f"Execution was NOT blocked for decision='{decision}'"

    @pytest.mark.asyncio
    async def test_cannot_resolve_already_resolved_or_missing_run(self, tmp_path: Path):
        """Verify double-resolution or non-existent run raises ValueError."""
        db_path = tmp_path / "double_res.sqlite"
        checkpointer = GovernorCheckpointer(db_path=db_path)
        orchestrator = GovernorOrchestrator(
            gateway=GatewayService(replay_mode=True),
            checkpointer=checkpointer,
            dry_run=True,
        )

        # 1. Non-existent run
        with pytest.raises(ValueError, match="not found in checkpoints"):
            orchestrator.resolve_approval("run_does_not_exist", "approved")

        # 2. Start valid run and approve it
        state = await orchestrator.start_run(objective="Normal test run")
        run_id = state["run_id"]
        orchestrator.resolve_approval(run_id, "approved")

        # 3. Attempt to approve again -> must raise ValueError
        with pytest.raises(ValueError, match="already in state: completed"):
            orchestrator.resolve_approval(run_id, "approved")

    @pytest.mark.asyncio
    async def test_mid_run_failure_persists_as_failed_checkpoint(self, tmp_path: Path):
        """Verify unhandled worker exception halts relay and durably saves status='failed'."""
        db_path = tmp_path / "fail_checkpoints.sqlite"
        audit_db = tmp_path / "fail_audit.sqlite"

        checkpointer = GovernorCheckpointer(db_path=db_path)
        audit_trail = AuditTrail(db_path=audit_db)
        orchestrator = GovernorOrchestrator(
            gateway=GatewayService(replay_mode=True),
            checkpointer=checkpointer,
            audit_trail=audit_trail,
            dry_run=True,
        )

        # Inject a simulated crash in creative_worker
        with patch.object(
            orchestrator.creative_worker,
            "generate_creative_package",
            side_effect=RuntimeError("Simulated LLM Gateway crash"),
        ):
            failed_state = await orchestrator.start_run(objective="Crash test")
            run_id = failed_state["run_id"]

            assert failed_state["status"] == "failed"
            assert "Simulated LLM Gateway crash" in failed_state["error"]

            # Verify SQLite checkpoint persisted as failed
            loaded = checkpointer.load_checkpoint(run_id)
            assert loaded is not None
            assert loaded["status"] == "failed"
            assert "Simulated LLM Gateway crash" in loaded["error"]

            # Verify audit trail recorded failure
            trail = audit_trail.get_trail(run_id)
            assert any(e["action"] == "RUN_FAILED" for e in trail)

    @pytest.mark.asyncio
    async def test_loopback_retry_on_flagged_creative(self, tmp_path: Path):
        """Verify Governor automatically triggers loopback revision when creative violates SEBI rules."""
        db_path = tmp_path / "loopback_checkpoints.sqlite"
        audit_db = tmp_path / "loopback_audit.sqlite"

        checkpointer = GovernorCheckpointer(db_path=db_path)
        audit_trail = AuditTrail(db_path=audit_db)
        orchestrator = GovernorOrchestrator(
            gateway=GatewayService(replay_mode=True),
            checkpointer=checkpointer,
            audit_trail=audit_trail,
            dry_run=True,
        )

        # Create a non-compliant initial creative package (e.g. contains "guaranteed return")
        bad_creative = CreativePackage(
            brief=CreativeBrief("Audience", "Angle", "Pain", "Value", "Tone", []),
            script=VideoScript("Title", 30, "9:16", "Hook", "Problem", "CTA", []),
            creative=AdCreative(
                headline="Get 25% Guaranteed Return with SIP",
                primary_text="Risk-free wealth generation without any losses.",
                call_to_action="Invest",
                alternative_headlines=[],
            ),
            captions=PlatformCaptions("Meta", "Insta", "LinkedIn", []),
            generation_mode="llm",
        )

        with patch.object(
            orchestrator.creative_worker,
            "generate_creative_package",
            new=AsyncMock(return_value=bad_creative),
        ):
            run_state = await orchestrator.start_run(objective="Loopback test")
            assert run_state["status"] == "pending_approval"
            
            # Check compliance report recorded loopback revision
            compliance_report = run_state["agent_reports"]["compliance"]
            assert compliance_report["loopback_count"] == 1
            # After loopback sanitization, the proposal creative should be compliant
            assert compliance_report["passed"] is True
            assert compliance_report["status"] == "pass"
            assert "guaranteed return" not in run_state["proposal"]["creative_package"]["creative"]["headline"].lower()
