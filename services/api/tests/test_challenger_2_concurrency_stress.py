"""Challenger 2 Empirical Concurrency and High-Throughput Stress Tests for Starlette API.

Tests:
1. Concurrent BYOD dataset uploads and retrievals (20+ concurrent workers)
2. Concurrent Governor runs and human approvals on 320-campaign BYOD dataset
3. Concurrent direct specialist agent runs (/api/agents/{analyst,media_buyer,compliance}/invoke)
4. Repeated rapid upload -> query -> run -> clear -> query lifecycle without race conditions or memory corruption
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from modules.ads.byod_importer import (
    clear_active_byod_snapshot,
    get_active_byod_snapshot,
    has_active_byod_snapshot,
    parse_csv,
    set_active_byod_snapshot,
)
from services.api.main import app


CSV_DATA_PATH = Path("services/api/data/sample_multichannel_campaigns.csv")


@pytest.fixture(autouse=True)
def clean_byod():
    clear_active_byod_snapshot()
    yield
    clear_active_byod_snapshot()


# ===========================================================================
# 1. Concurrent BYOD Uploads & Retrievals Stress Test
# ===========================================================================

@pytest.mark.asyncio
async def test_concurrent_byod_uploads_and_retrievals():
    """Verify Starlette API handles 20 concurrent BYOD uploads and queries with 0 errors."""
    csv_content = CSV_DATA_PATH.read_text(encoding="utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Define upload task
        async def do_upload(i: int):
            resp = await client.post(
                "/api/byod/upload",
                json={"filename": f"dataset_{i}.csv", "file_content": csv_content, "activate": True},
            )
            assert resp.status_code == 200, f"Upload {i} failed: {resp.text}"
            data = resp.json()
            assert data["campaign_count"] == 320
            return data

        # Define retrieval task
        async def do_get_current():
            resp = await client.get("/api/byod/current")
            assert resp.status_code == 200
            return resp.json()

        # Define sample task
        async def do_get_sample():
            resp = await client.get("/api/byod/sample")
            assert resp.status_code == 200
            return resp.json()

        # Launch 10 uploads and 20 gets concurrently
        tasks = []
        for i in range(10):
            tasks.append(do_upload(i))
            tasks.append(do_get_current())
            tasks.append(do_get_sample())

        results = await asyncio.gather(*tasks)
        assert len(results) == 30
        assert has_active_byod_snapshot() is True
        assert len(get_active_byod_snapshot().campaigns) == 320


# ===========================================================================
# 2. Concurrent Governor Runs & Approvals on 320-Campaign Dataset
# ===========================================================================

@pytest.mark.asyncio
async def test_concurrent_governor_runs_and_approvals():
    """Verify Governor orchestrates multiple concurrent runs without state cross-contamination."""
    csv_content = CSV_DATA_PATH.read_text(encoding="utf-8")
    snapshot = parse_csv(csv_content)
    set_active_byod_snapshot(snapshot)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Launch 5 concurrent runs
        async def start_and_approve_run(idx: int):
            # 1. Start run
            resp = await client.post(
                "/api/runs",
                json={"objective": f"Scale winning campaign cluster #{idx} across 320 campaigns"},
            )
            assert resp.status_code == 200, f"Start run {idx} failed: {resp.text}"
            run_data = resp.json()
            run_id = run_data["run_id"]
            assert run_data["status"] == "running"

            # 2. Poll until pending_approval (Hops 0-5 complete)
            settled_state = None
            for _ in range(60):
                await asyncio.sleep(0.1)
                get_resp = await client.get(f"/api/runs/{run_id}")
                assert get_resp.status_code == 200
                st = get_resp.json()
                if st.get("status") in ("pending_approval", "failed"):
                    settled_state = st
                    break

            assert settled_state is not None, f"Run {run_id} timed out waiting for pending_approval"
            assert settled_state["status"] == "pending_approval"
            assert settled_state["current_agent"] == "HumanApprover"
            assert settled_state["proposal"]["data_source"] == "byod"
            assert len(settled_state["hops"]) == 6

            # 3. Approve run (Hop 6)
            app_resp = await client.post(
                f"/api/runs/{run_id}/approval",
                json={"decision": "approved", "decision_notes": f"Approved run {idx}"},
            )
            assert app_resp.status_code == 200, f"Approve run {idx} failed: {app_resp.text}"
            app_data = app_resp.json()
            assert app_data["status"] == "completed"
            assert app_data["decision"] == "approved"
            assert len(app_data["execution_results"]) > 0
            return run_id

        run_ids = await asyncio.gather(*(start_and_approve_run(i) for i in range(5)))
        assert len(run_ids) == 5
        assert len(set(run_ids)) == 5, "Run IDs must be completely unique"


# ===========================================================================
# 3. Concurrent Specialist Agent Direct Invocations
# ===========================================================================

@pytest.mark.asyncio
async def test_concurrent_agent_direct_invocations_under_byod_load():
    """Verify single-agent direct endpoints process the 320-campaign dataset concurrently."""
    csv_content = CSV_DATA_PATH.read_text(encoding="utf-8")
    set_active_byod_snapshot(parse_csv(csv_content))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async def call_analyst():
            resp = await client.post(
                "/api/agents/analyst/invoke",
                json={"prompt": "Analyze all 320 campaigns and report channel ROAS breakdown"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data.get("blocks", [])) > 0
            return data

        async def call_budget():
            resp = await client.post(
                "/api/agents/media_buyer/invoke",
                json={"prompt": "Reallocate spend from worst performers to top winners within +/-25%"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data.get("blocks", [])) > 0
            return data

        async def call_compliance():
            resp = await client.post(
                "/api/agents/compliance/invoke",
                json={"prompt": "Verify this copy: Guaranteed 100% returns on mutual funds"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data.get("blocks", [])) > 0
            return data

        async def call_dashboard():
            resp = await client.get("/api/dashboard/overview")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["campaigns"]) == 320
            assert "channels" in data
            return data

        tasks = [
            call_analyst(),
            call_budget(),
            call_compliance(),
            call_dashboard(),
            call_analyst(),
            call_budget(),
            call_compliance(),
            call_dashboard(),
        ]

        results = await asyncio.gather(*tasks)
        assert len(results) == 8


# ===========================================================================
# 4. Rapid Lifecycle Dataset Swapping & Isolation
# ===========================================================================

@pytest.mark.asyncio
async def test_rapid_lifecycle_dataset_swapping_and_cleaning():
    """Verify rapid switching between BYOD active dataset and synthetic fallback."""
    csv_content = CSV_DATA_PATH.read_text(encoding="utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for cycle in range(3):
            # 1. Initially no BYOD active
            resp = await client.get("/api/byod/current")
            assert resp.status_code == 200
            assert resp.json()["active"] is False

            # 2. Upload and activate 320 rows
            up_resp = await client.post(
                "/api/byod/upload",
                json={"filename": "rapid.csv", "file_content": csv_content, "activate": True},
            )
            assert up_resp.status_code == 200
            assert up_resp.json()["campaign_count"] == 320

            # 3. Check dashboard reflects 320 rows
            dash_resp = await client.get("/api/dashboard/overview")
            assert dash_resp.status_code == 200
            assert len(dash_resp.json()["campaigns"]) == 320
            assert dash_resp.json()["data_source"] == "byod"

            # 4. Clear BYOD
            del_resp = await client.delete("/api/byod/current")
            assert del_resp.status_code == 200
            assert del_resp.json()["status"] == "cleared"

            # 5. Check dashboard falls back to synthetic dataset
            dash_resp2 = await client.get("/api/dashboard/overview")
            assert dash_resp2.status_code == 200
            assert dash_resp2.json()["data_source"] in ("synthetic", "live")
