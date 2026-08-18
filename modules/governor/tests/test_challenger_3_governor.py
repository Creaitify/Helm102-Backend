"""Empirical Adversarial Stress Suite for Governor Orchestrator & Star Relay.
Authored by Challenger 3.

Covers:
- 6-Hop sequential state transitions and envelope verification
- SQLite checkpointer serialization and loading
- HITL gate security: blocking unapproved executions, operator rejection, double-resolution prevention
"""

import pytest
import sqlite3
import json
from pathlib import Path

from modules.audit.trail import AuditTrail
from modules.execution.executor import ExecutionEngine
from modules.governor.checkpoint import GovernorCheckpointer
from modules.governor.orchestrator import GovernorOrchestrator
from services.api.gateway.service import GatewayService


class TestGovernorOrchestratorChallenger3:
    """Adversarial challenge test suite for Governor Star Relay."""

    @pytest.mark.asyncio
    async def test_full_6_hop_relay_and_checkpoints(self, tmp_path: Path):
        """Test complete 6-hop relay flow with checkpoint persistence and HITL approval."""
        db_path = tmp_path / "c3_checkpoints.sqlite"
        audit_path = tmp_path / "c3_audit.sqlite"

        checkpointer = GovernorCheckpointer(db_path=db_path)
        audit_trail = AuditTrail(db_path=audit_path)
        orchestrator = GovernorOrchestrator(
            gateway=GatewayService(replay_mode=True),
            checkpointer=checkpointer,
            audit_trail=audit_trail,
            dry_run=True,
        )

        # Execute Hops 0..5
        state = await orchestrator.start_run(objective="Adversarial validation run")
        run_id = state["run_id"]

        assert state["status"] == "pending_approval"
        assert state["current_hop"] == 5
        assert len(state["hops"]) == 6

        # Verify all agent reports exist
        reports = state["agent_reports"]
        assert "analyst" in reports
        assert "creative" in reports
        assert "compliance" in reports
        assert "budget" in reports
        assert "governor" in reports

        # Check SQLite persistence
        loaded = checkpointer.load_checkpoint(run_id)
        assert loaded is not None
        assert loaded["status"] == "pending_approval"
        assert loaded["current_hop"] == 5

        # Resolve with operator approval -> Hop 6
        final_state = orchestrator.resolve_approval(run_id, decision="approved", decision_notes="Audited by Challenger 3")
        assert final_state["status"] == "completed"
        assert final_state["decision"] == "approved"
        assert final_state["current_agent"] == "ExecutionEngine"
        assert len(final_state["execution_results"]) > 0

        # Double resolution must fail
        with pytest.raises(ValueError, match="already in state"):
            orchestrator.resolve_approval(run_id, decision="approved")

    @pytest.mark.asyncio
    async def test_operator_rejection_halts_dispatch(self, tmp_path: Path):
        """Test that rejecting a proposal prevents any ad platform actions."""
        db_path = tmp_path / "c3_reject.sqlite"
        checkpointer = GovernorCheckpointer(db_path=db_path)
        orchestrator = GovernorOrchestrator(
            gateway=GatewayService(replay_mode=True),
            checkpointer=checkpointer,
            dry_run=True,
        )

        state = await orchestrator.start_run(objective="Rejection test run")
        run_id = state["run_id"]

        rejected = orchestrator.resolve_approval(run_id, decision="rejected", decision_notes="Rejected by Compliance")
        assert rejected["status"] == "rejected"
        assert len(rejected["execution_results"]) == 0

    def test_direct_execution_engine_blocks_unauthorized_decisions(self, tmp_path: Path):
        """Verify ExecutionEngine independently blocks unapproved execution requests."""
        audit_trail = AuditTrail(db_path=tmp_path / "exec_sec.sqlite")
        engine = ExecutionEngine(audit_trail=audit_trail, dry_run=True)

        proposal = {
            "budget_shifts": [
                {
                    "campaign_id": "c1",
                    "platform": "meta_ads",
                    "current_daily_budget_inr": 1000.0,
                    "proposed_daily_budget_inr": 1250.0,
                    "shift_percentage": 25.0,
                    "rationale": "scale",
                }
            ]
        }

        for dec in ["pending", "rejected", "unknown", "", "CANCELLED", None]:
            results = engine.execute_proposal(
                run_id="sec_test",
                proposal=proposal,
                human_decision=str(dec) if dec else "",
            )
            assert len(results) == 0

    def test_sqlite_connections_close_cleanly_on_windows(self, tmp_path: Path):
        """Verify that Checkpointer and AuditTrail properly close connections and allow immediate file deletion."""
        ckpt_path = tmp_path / "lock_test_ckpt.sqlite"
        audit_path = tmp_path / "lock_test_audit.sqlite"

        # Instantiate and perform operations
        cp = GovernorCheckpointer(db_path=ckpt_path)
        cp.save_checkpoint("run_lock_test", "in_progress", 1, {"test": True})
        loaded = cp.load_checkpoint("run_lock_test")
        assert loaded == {"test": True}
        cp.list_checkpoints()

        # Audit operations
        from modules.governor.envelope import HandoffEnvelope, EnvelopeStatus
        trail = AuditTrail(db_path=audit_path)
        trail.record(
            "run_lock_test",
            HandoffEnvelope(
                hop_index=1,
                source="test_src",
                target="test_tgt",
                action="TEST_ACTION",
                status=EnvelopeStatus.SUCCESS,
                payload={"data": 123},
                rationale="test",
            ),
        )
        events = trail.get_trail("run_lock_test")
        assert len(events) == 1

        # Now test that files can be unlinked immediately without WinError 32
        ckpt_path.unlink()
        assert not ckpt_path.exists()
        audit_path.unlink()
        assert not audit_path.exists()
