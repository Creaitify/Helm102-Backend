"""End-to-end tests for Governor star orchestration and HITL flow."""

import pytest
from pathlib import Path
from modules.governor.checkpoint import GovernorCheckpointer
from modules.governor.orchestrator import GovernorOrchestrator
from modules.audit.trail import AuditTrail
from services.api.gateway.service import GatewayService


@pytest.mark.asyncio
async def test_governor_end_to_end_approval_flow(tmp_path: Path):
    db_path = tmp_path / "test_checkpoints.sqlite"
    audit_db = tmp_path / "test_audit.sqlite"

    checkpointer = GovernorCheckpointer(db_path=db_path)
    audit_trail = AuditTrail(db_path=audit_db)
    gateway = GatewayService(replay_mode=True)

    orchestrator = GovernorOrchestrator(
        gateway=gateway,
        checkpointer=checkpointer,
        audit_trail=audit_trail,
        dry_run=True,
    )

    # 1. Start Run -> executes through all specialists and pauses at approval gate
    run_state = await orchestrator.start_run(objective="Reduce cost per acquisition on SIP campaigns")
    run_id = run_state["run_id"]

    assert run_state["status"] == "pending_approval"
    proposal = run_state["proposal"]
    assert "creative_package" in proposal
    assert "budget_shifts" in proposal
    assert "compliance_verdict" in proposal
    assert proposal["compliance_verdict"]["status"] == "pass"

    # Verify checkpointer saved state
    loaded_state = checkpointer.load_checkpoint(run_id)
    assert loaded_state is not None
    assert loaded_state["status"] == "pending_approval"

    # Verify audit trail has 6 recorded hops (0 through 5)
    trail = audit_trail.get_trail(run_id)
    assert len(trail) >= 6
    assert trail[0]["action"] == "INGEST_OBJECTIVE"
    assert trail[1]["action"] == "FETCH_AND_ANALYZE_CAMPAIGNS"
    assert trail[2]["action"] == "GENERATE_CREATIVE_PACKAGE"
    assert trail[3]["action"] == "VERIFY_SEBI_REGULATORY"
    assert trail[4]["action"] == "PROPOSE_BUDGET_REALLOCATION"
    assert trail[5]["action"] == "SUBMIT_PROPOSAL_FOR_APPROVAL"

    # 2. Human Approval Decision -> Resumes and executes approved payload
    completed_state = orchestrator.resolve_approval(
        run_id=run_id,
        decision="approved",
        decision_notes="Approved by Investment Operations Lead.",
    )

    assert completed_state["status"] == "completed"
    assert len(completed_state["execution_results"]) > 0
    assert completed_state["execution_results"][0]["dry_run"] is True

    # Check updated audit trail
    trail_after = audit_trail.get_trail(run_id)
    assert len(trail_after) > len(trail)


@pytest.mark.asyncio
async def test_governor_rejection_flow(tmp_path: Path):
    db_path = tmp_path / "test_checkpoints2.sqlite"
    audit_db = tmp_path / "test_audit2.sqlite"

    orchestrator = GovernorOrchestrator(
        gateway=GatewayService(replay_mode=True),
        checkpointer=GovernorCheckpointer(db_path=db_path),
        audit_trail=AuditTrail(db_path=audit_db),
        dry_run=True,
    )

    run_state = await orchestrator.start_run(objective="Scale Gold ETF campaign")
    run_id = run_state["run_id"]

    # Reject proposal
    rejected_state = orchestrator.resolve_approval(
        run_id=run_id,
        decision="rejected",
        decision_notes="Current market conditions unfavorable for gold.",
    )

    assert rejected_state["status"] == "rejected"
    assert len(rejected_state["execution_results"]) == 0
