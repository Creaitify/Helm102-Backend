"""Unit tests for SQLAlchemy database models, session management, and repositories."""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from modules.governor.envelope import EnvelopeStatus, HandoffEnvelope
from services.api.db.models import AuditEventModel, Base, CampaignModel, RunModel
from services.api.db.repository import AuditRepository, CampaignRepository, RunRepository
from services.api.db.session import (
    close_db,
    create_engine_and_sessionmaker,
    get_db_session,
    init_db,
    normalize_db_url,
)


@pytest_asyncio.fixture
async def test_db():
    """Create an isolated in-memory SQLite database for testing."""
    engine, session_factory = create_engine_and_sessionmaker(
        db_url="sqlite+aiosqlite:///:memory:",
    )
    await init_db(engine)

    async with session_factory() as session:
        yield session, engine

    await close_db(engine)


@pytest.mark.asyncio
async def test_init_db_and_metadata(test_db):
    """Verify tables are created in metadata and schema initialization succeeds."""
    session, engine = test_db
    assert "runs" in Base.metadata.tables
    assert "audit_events" in Base.metadata.tables
    assert "campaigns" in Base.metadata.tables


@pytest.mark.asyncio
async def test_run_model_and_repository(test_db):
    """Test full CRUD and query operations for RunRepository and RunModel."""
    session, _ = test_db
    repo = RunRepository(session)

    # 1. Create Run
    proposal_data = {
        "budget_shifts": [{"campaign_id": "c1", "shift_percentage": 10.0}],
        "creative_variants": [],
    }
    run = await repo.create_run(
        run_id="run-001",
        objective="Scale mutual funds retargeting",
        tenant_id="tenant-alpha",
        status="pending_approval",
        proposal=proposal_data,
        execution_results=[],
    )
    await session.commit()

    assert run.run_id == "run-001"
    assert run.tenant_id == "tenant-alpha"
    assert run.status == "pending_approval"
    assert run.objective == "Scale mutual funds retargeting"
    assert run.proposal == proposal_data
    assert run.execution_results == []
    assert run.created_at is not None
    assert run.updated_at is not None

    # Test to_dict
    d = run.to_dict()
    assert d["run_id"] == "run-001"
    assert d["tenant_id"] == "tenant-alpha"
    assert d["proposal"] == proposal_data

    # 2. Get Run
    fetched = await repo.get_run("run-001")
    assert fetched is not None
    assert fetched.run_id == "run-001"

    # Scoped tenant check
    assert await repo.get_run("run-001", tenant_id="tenant-beta") is None
    assert await repo.get_run("run-001", tenant_id="tenant-alpha") is not None

    # 3. Update Run
    exec_results = [{"success": True, "action": "budget_update", "platform": "google_ads"}]
    updated = await repo.update_run(
        run_id="run-001",
        status="completed",
        execution_results=exec_results,
    )
    await session.commit()

    assert updated is not None
    assert updated.status == "completed"
    assert updated.execution_results == exec_results

    # Update non-existent run returns None
    assert await repo.update_run("run-nonexistent", status="failed") is None

    # 4. Upsert Run (Existing & New)
    upserted_existing = await repo.upsert_run(
        run_id="run-001",
        objective="Scale mutual funds retargeting (updated)",
        tenant_id="tenant-alpha",
        status="completed_success",
    )
    await session.commit()
    assert upserted_existing.status == "completed_success"
    assert upserted_existing.objective == "Scale mutual funds retargeting (updated)"

    upserted_new = await repo.upsert_run(
        run_id="run-002",
        objective="Test second run",
        tenant_id="tenant-alpha",
        status="executing",
    )
    await session.commit()
    assert upserted_new.run_id == "run-002"

    # 5. List Runs with filters
    # Create another run in tenant-beta
    await repo.create_run(
        run_id="run-003",
        objective="Tenant Beta run",
        tenant_id="tenant-beta",
        status="failed",
    )
    await session.commit()

    all_runs = await repo.list_runs()
    assert len(all_runs) == 3

    alpha_runs = await repo.list_runs(tenant_id="tenant-alpha")
    assert len(alpha_runs) == 2

    failed_runs = await repo.list_runs(status="failed")
    assert len(failed_runs) == 1
    assert failed_runs[0].run_id == "run-003"

    paginated = await repo.list_runs(limit=1, offset=0)
    assert len(paginated) == 1

    # 6. Delete Run
    deleted = await repo.delete_run("run-002")
    await session.commit()
    assert deleted is True
    assert await repo.get_run("run-002") is None

    deleted_fake = await repo.delete_run("run-002")
    assert deleted_fake is False


@pytest.mark.asyncio
async def test_audit_repository_and_model(test_db):
    """Test recording and querying chronological immutable audit events."""
    session, _ = test_db
    audit_repo = AuditRepository(session)

    # 1. Record raw event
    event1 = await audit_repo.record_event(
        run_id="run-audit-1",
        hop_index=1,
        source="governor",
        target="analyst",
        action="fetch_snapshot",
        status="success",
        payload_json={"accounts": ["act-1", "act-2"]},
        rationale="Ingest ad performance data",
    )
    await session.commit()

    assert event1.id is not None
    assert event1.run_id == "run-audit-1"
    assert event1.hop_index == 1
    assert event1.status == "success"
    assert event1.payload_json == {"accounts": ["act-1", "act-2"]}

    d = event1.to_dict()
    assert d["source"] == "governor"
    assert d["target"] == "analyst"
    assert d["payload"] == {"accounts": ["act-1", "act-2"]}

    # 2. Record from HandoffEnvelope
    envelope = HandoffEnvelope(
        hop_index=2,
        source="analyst",
        target="governor",
        action="analysis_findings",
        status=EnvelopeStatus.SUCCESS,
        payload={"roas": 3.4, "top_campaign": "camp-123"},
        rationale="Analyst detected high performing campaign",
    )
    event2 = await audit_repo.record_envelope("run-audit-1", envelope)

    # Record a degraded/error envelope
    envelope_error = HandoffEnvelope(
        hop_index=3,
        source="compliance",
        target="governor",
        action="sebi_verification",
        status=EnvelopeStatus.DEGRADED,
        payload={"violations": ["Missing disclaimer"]},
        rationale="SEBI rule 4.2 violation caught",
        error="SEBI compliance check failed",
    )
    event3 = await audit_repo.record_envelope("run-audit-1", envelope_error)
    await session.commit()

    # 3. Retrieve Chronological Audit Trail
    trail = await audit_repo.get_trail("run-audit-1")
    assert len(trail) == 3
    assert trail[0].hop_index == 1
    assert trail[1].hop_index == 2
    assert trail[2].hop_index == 3
    assert trail[2].status == "degraded"
    assert trail[2].error == "SEBI compliance check failed"

    # 4. List Events
    events = await audit_repo.list_events(run_id="run-audit-1", limit=2)
    assert len(events) == 2

    empty_trail = await audit_repo.get_trail("nonexistent-run")
    assert empty_trail == []


@pytest.mark.asyncio
async def test_campaign_repository_and_model(test_db):
    """Test CampaignModel and CampaignRepository CRUD operations."""
    session, _ = test_db
    repo = CampaignRepository(session)

    # 1. Upsert Campaign
    c1 = await repo.upsert_campaign(
        campaign_id="cmp-google-101",
        name="SIP Direct Growth Search",
        platform="google_ads",
        spend=45000.0,
        roas=4.2,
        cpa=320.0,
        status="ENABLED",
        tenant_id="tenant-1",
    )
    await session.commit()

    assert c1.campaign_id == "cmp-google-101"
    assert c1.spend == 45000.0
    assert c1.roas == 4.2
    assert c1.cpa == 320.0

    d = c1.to_dict()
    assert d["campaign_id"] == "cmp-google-101"
    assert d["platform"] == "google_ads"

    # 2. Update existing campaign via upsert
    c1_updated = await repo.upsert_campaign(
        campaign_id="cmp-google-101",
        name="SIP Direct Growth Search",
        platform="google_ads",
        spend=52000.0,
        roas=4.5,
        cpa=310.0,
        status="ENABLED",
        tenant_id="tenant-1",
    )
    await session.commit()
    assert c1_updated.spend == 52000.0
    assert c1_updated.roas == 4.5

    # 3. Get Campaign
    fetched = await repo.get_campaign("cmp-google-101", tenant_id="tenant-1")
    assert fetched is not None
    assert fetched.spend == 52000.0

    assert await repo.get_campaign("cmp-google-101", tenant_id="tenant-other") is None

    # 4. Bulk Upsert
    bulk_data = [
        {
            "campaign_id": "cmp-meta-201",
            "name": "Retargeting Video Reels",
            "platform": "meta_ads",
            "spend": 28000.0,
            "roas": 3.8,
            "cpa": 280.0,
            "status": "ENABLED",
        },
        {
            "campaign_id": "cmp-meta-202",
            "name": "Lookalike 1% Top Spenders",
            "platform": "meta_ads",
            "spend": 35000.0,
            "roas": 2.9,
            "cpa": 410.0,
            "status": "PAUSED",
        },
    ]
    upserted_list = await repo.bulk_upsert(bulk_data, tenant_id="tenant-1")
    await session.commit()
    assert len(upserted_list) == 2

    # 5. List Campaigns with filters
    tenant1_campaigns = await repo.list_campaigns(tenant_id="tenant-1")
    assert len(tenant1_campaigns) == 3

    meta_campaigns = await repo.list_campaigns(platform="meta_ads", tenant_id="tenant-1")
    assert len(meta_campaigns) == 2

    paused_meta = await repo.list_campaigns(
        platform="meta_ads",
        status="PAUSED",
        tenant_id="tenant-1",
    )
    assert len(paused_meta) == 1
    assert paused_meta[0].campaign_id == "cmp-meta-202"

    # 6. Delete Campaign
    deleted = await repo.delete_campaign("cmp-meta-202", tenant_id="tenant-1")
    await session.commit()
    assert deleted is True
    assert await repo.get_campaign("cmp-meta-202", tenant_id="tenant-1") is None


@pytest.mark.asyncio
async def test_session_helpers_and_url_normalization():
    """Test URL normalizer and session dependency generator."""
    assert normalize_db_url("sqlite:///app.db") == "sqlite+aiosqlite:///app.db"
    assert normalize_db_url("postgresql://user:pass@localhost/db") == "postgresql+asyncpg://user:pass@localhost/db"
    assert normalize_db_url("postgres://user:pass@localhost/db") == "postgresql+asyncpg://user:pass@localhost/db"
    assert normalize_db_url("sqlite+aiosqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"

    # Test get_db_session async generator
    async for session in get_db_session():
        assert isinstance(session, AsyncSession)
        break
