"""FastAPI backend service for HELM02 Orchestration."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from modules.ads.connector import MureoConnector
from modules.audit.trail import AuditTrail
from modules.governor.checkpoint import GovernorCheckpointer
from modules.governor.orchestrator import GovernorOrchestrator
from services.api.auth import oauth
from services.api.gateway.keys import has_anthropic_api_key
from services.api.gateway.service import GatewayService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("helm02.api")

app = FastAPI(
    title="HELM02 Orchestration API",
    version="0.1.0",
    description="Governed Marketing Orchestration System Backend",
)

# Enable CORS for web console
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate core singletons
from services.api.gateway.keys import (
    get_active_provider,
    get_anthropic_api_key,
    get_gemini_api_key,
    get_model_for_provider,
    has_anthropic_api_key,
    has_gemini_api_key,
)

gateway = GatewayService(replay_mode=not (has_gemini_api_key() or has_anthropic_api_key()))
# Share the OAuth router's secret store so credentials saved through
# /api/connections are visible to the connector without a restart.
connector = MureoConnector(secret_store=oauth.secret_store)

checkpointer = GovernorCheckpointer()

audit_trail = AuditTrail()
orchestrator = GovernorOrchestrator(
    gateway=gateway,
    connector=connector,
    checkpointer=checkpointer,
    audit_trail=audit_trail,
    dry_run=os.environ.get("HELM_ADS_DRY_RUN", "true").lower() == "true",
)

app.include_router(oauth.router)

# Conversation / agent / report surfaces used by the console.
from services.api import agents, chat, conversations, dashboard, reports

agents.configure(gateway=gateway, connector=connector, orchestrator=orchestrator)
reports.configure(gateway=gateway, connector=connector)
dashboard.configure(connector=connector, checkpointer=checkpointer)
conversations.init_db()
reports.init_db()

app.include_router(agents.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(dashboard.router)
app.include_router(reports.router)

# Keep strong references to background run tasks so they aren't GC'd mid-run.
_background_runs: set[asyncio.Task] = set()


class StartRunRequest(BaseModel):
    objective: str = Field(..., json_schema_extra={"example": "Reduce CPA and scale winning SIP retargeting ads"})
    wait: bool = Field(
        default=False,
        description="true = block until the proposal is ready; false = return run_id immediately and stream progress via GET /api/runs/{run_id}",
    )


class ApprovalRequest(BaseModel):
    decision: str = Field(..., json_schema_extra={"example": "approved"})  # "approved" | "rejected"
    decision_notes: str = Field(default="", json_schema_extra={"example": "Approved by Growth Marketing Lead"})


class SwitchProviderRequest(BaseModel):
    provider: str = Field(..., json_schema_extra={"example": "gemini"})  # "gemini" | "anthropic" | "replay"
    model: str | None = Field(default=None, json_schema_extra={"example": "gemini-2.5-flash"})


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    """Health check reporting gateway, data-source, and write-mode facets."""
    active_prov = get_active_provider()
    active_model = get_model_for_provider(active_prov)
    has_key = has_gemini_api_key() if active_prov == "gemini" else has_anthropic_api_key()
    connections = connector.connection_status()

    return {
        "status": "healthy",
        "active_provider": active_prov,
        "active_model": active_model,
        "gateway_mode": "live" if has_key else "replay",
        "has_gemini_key": has_gemini_api_key(),
        "has_anthropic_key": has_anthropic_api_key(),
        "ads_mode": "mureo-connector",
        "data_source": connections["data_source"],
        "connections": {
            "google_ads": connections["google_ads"],
            "meta_ads": connections["meta_ads"],
        },
        "dry_run": orchestrator.execution_engine.dry_run,
    }


@app.post("/api/provider/switch")
def switch_provider(req: SwitchProviderRequest) -> dict[str, Any]:
    """Switch active LLM provider and model."""
    prov = req.provider.lower()
    if prov not in ("gemini", "anthropic", "replay"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider '{prov}'. Use 'gemini', 'anthropic', or 'replay'.")

    os.environ["HELM_LLM_PROVIDER"] = prov
    if req.model:
        if prov == "gemini":
            os.environ["GEMINI_MODEL"] = req.model
        elif prov == "anthropic":
            os.environ["ANTHROPIC_MODEL"] = req.model

    # Recompute replay mode so a key added/removed after boot takes effect.
    gateway.replay_mode = prov == "replay" or not (has_gemini_api_key() or has_anthropic_api_key())

    active_model = get_model_for_provider(prov)
    return {
        "status": "switched",
        "active_provider": prov,
        "active_model": active_model,
        "gateway_mode": "replay" if gateway.replay_mode else "live",
    }



@app.post("/api/runs")
async def create_run(req: StartRunRequest) -> dict[str, Any]:
    """Start a Governor orchestration run.

    Default is non-blocking: returns the run_id at once while the relay
    executes in the background, checkpointing after every hop. The console
    polls GET /api/runs/{run_id} to render live agent progress.
    """
    if req.wait:
        try:
            return await orchestrator.start_run(objective=req.objective)
        except Exception as exc:
            logger.error("Failed to start run: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    checkpointer.save_checkpoint(
        run_id=run_id,
        status="running",
        hop_index=0,
        state={
            "run_id": run_id,
            "objective": req.objective,
            "status": "running",
            "current_hop": 0,
            "current_agent": "Governor",
            "hops": [],
            "agent_reports": {},
            "proposal": None,
            "decision": None,
            "execution_results": [],
            "error": None,
        },
    )
    task = asyncio.create_task(orchestrator.start_run(objective=req.objective, run_id=run_id))
    _background_runs.add(task)
    task.add_done_callback(_background_runs.discard)
    return {"run_id": run_id, "status": "running", "objective": req.objective}


@app.get("/api/runs")
def list_runs() -> list[dict[str, Any]]:
    """List all saved runs and checkpoints."""
    return checkpointer.list_checkpoints()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    """Get the full state, proposal, and status of a specific run."""
    state = checkpointer.load_checkpoint(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return state


_SETTLED_STATUSES = ("pending_approval", "completed", "rejected", "failed")


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(run_id: str):
    """Server-Sent Events stream of a run's live state.

    Pushes the full checkpoint state as a `state` event the moment it changes
    (checked every 250ms server-side), then a final `done` event once the run
    settles. The console renders agent hops the instant they land instead of
    polling once per second.
    """
    import json as _json

    from fastapi.responses import StreamingResponse

    if not checkpointer.load_checkpoint(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    async def event_stream():
        last_payload: str | None = None
        beats_since_send = 0
        # 1200 * 250ms = 5 min hard cap so orphaned streams always close.
        for _ in range(1200):
            state = await asyncio.to_thread(checkpointer.load_checkpoint, run_id)
            if state:
                payload = _json.dumps(state, separators=(",", ":"))
                if payload != last_payload:
                    last_payload = payload
                    beats_since_send = 0
                    yield f"event: state\ndata: {payload}\n\n"
                    if state.get("status") in _SETTLED_STATUSES:
                        yield f"event: done\ndata: {_json.dumps({'status': state['status']})}\n\n"
                        return
            beats_since_send += 1
            if beats_since_send >= 60:  # 15s heartbeat keeps proxies from closing us
                beats_since_send = 0
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.25)
        yield "event: timeout\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/runs/{run_id}/approval")
def submit_approval(run_id: str, req: ApprovalRequest) -> dict[str, Any]:
    """Submit human decision (approved/rejected) to resume execution."""
    try:
        updated_state = orchestrator.resolve_approval(
            run_id=run_id,
            decision=req.decision,
            decision_notes=req.decision_notes,
        )
        return updated_state
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Approval resolution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/audit")
def get_run_audit_trail(run_id: str) -> list[dict[str, Any]]:
    """Retrieve full immutable audit trail of envelopes for a run."""
    return audit_trail.get_trail(run_id)


# --- BYOD & Knowledge Verification Endpoints ---

from modules.ads.byod_importer import get_finnovate_sample_data, parse_csv
from services.api.knowledge.citations import CitationVerifier

citation_verifier = CitationVerifier()


class VerifyCopyRequest(BaseModel):
    headline: str = Field(default="", json_schema_extra={"example": "Start Disciplined SIPs for Long-Term Growth"})
    primary_text: str = Field(default="", json_schema_extra={"example": "Mutual fund investments are subject to market risks."})


class ByodUploadRequest(BaseModel):
    csv_content: str = Field(..., json_schema_extra={"example": "campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status\ncmp_01,Search Intent,google_ads,45000,125000,8400,420,3.4,107.14,6.72,ENABLED"})


@app.get("/api/byod/sample")
def get_byod_sample() -> dict[str, Any]:
    """Get sample Finnovate marketing dataset."""
    sample_data = get_finnovate_sample_data()
    return {
        "dataset_name": "Finnovate_Q3_Growth_Sample",
        "sheets": list(sample_data.keys()),
        "data": sample_data,
    }


@app.post("/api/byod/parse")
def parse_byod_csv(req: ByodUploadRequest) -> dict[str, Any]:
    """Parse custom CSV dataset into CampaignSnapshot."""
    try:
        snapshot = parse_csv(req.csv_content)
        return {
            "platform": snapshot.platform.value,
            "campaign_count": len(snapshot.campaigns),
            "total_spend_inr": snapshot.total_spend_inr,
            "blended_roas": snapshot.blended_roas,
            "campaigns": [
                {
                    "campaign_id": c.campaign_id,
                    "campaign_name": c.campaign_name,
                    "platform": c.platform.value,
                    "spend_inr": c.spend_inr,
                    "roas": c.roas,
                    "cpa_inr": c.cpa_inr,
                    "ctr": c.ctr,
                }
                for c in snapshot.campaigns
            ]
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/citations/verify")
def verify_copy_citations(req: VerifyCopyRequest) -> dict[str, Any]:
    """Verify qualitative grounding and regulatory compliance of copy."""
    combined = f"{req.headline}\n\n{req.primary_text}".strip()
    verdict = citation_verifier.verify_text(combined, location="primary_text")
    return verdict.to_dict()



from services.api.db.synthetic_sqlite import (
    generate_synthetic_scenario,
    get_synthetic_meta,
    load_synthetic_daily_trends,
    load_synthetic_snapshot,
)


class GenerateSyntheticRequest(BaseModel):
    scenario: str = Field(default="growth_and_fatigue", json_schema_extra={"example": "growth_and_fatigue"})
    days: int = Field(default=30, ge=7, le=90, json_schema_extra={"example": 30})


@app.get("/api/synthetic/scenarios")
def list_synthetic_scenarios() -> list[dict[str, str]]:
    """List available synthetic marketing scenario profiles."""
    return [
        {
            "id": "growth_and_fatigue",
            "name": "Search Growth + Meta Fatigue",
            "description": "High-performing Google Search intent campaign paired with decayed Meta broad retargeting.",
        },
        {
            "id": "scale_winner",
            "name": "High-ROAS Winner Scaling",
            "description": "Strong converting SIP video campaigns with high ROAS ready for budget scaling.",
        },
        {
            "id": "sebi_risk_scenario",
            "name": "SEBI Compliance Risk & Loopback",
            "description": "Creatives containing guaranteed return claims to trigger deterministic safety loopback.",
        },
        {
            "id": "multi_channel_mix",
            "name": "Multi-Channel Balanced Mix",
            "description": "Multi-asset mix of Google Search, PMax, Meta Video, and ELSS tax saving campaigns.",
        },
    ]


@app.post("/api/synthetic/generate")
def create_synthetic_dataset(req: GenerateSyntheticRequest) -> dict[str, Any]:
    """Generate and seed coherent multi-channel synthetic dataset into SQLite."""
    try:
        result = generate_synthetic_scenario(scenario_name=req.scenario, days=req.days)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/synthetic/current")
def get_current_synthetic_snapshot() -> dict[str, Any]:
    """Fetch current snapshot of synthetic SQLite campaigns and aggregate metrics."""
    try:
        snapshot = load_synthetic_snapshot(lookback_days=30)
        daily_trends = load_synthetic_daily_trends(lookback_days=30)
        return {
            "source": snapshot.source,
            "campaign_count": len(snapshot.campaigns),
            "total_spend_inr": snapshot.total_spend_inr,
            "blended_roas": snapshot.blended_roas,
            "campaigns": [
                {
                    "campaign_id": c.campaign_id,
                    "campaign_name": c.campaign_name,
                    "platform": c.platform.value,
                    "spend_inr": c.spend_inr,
                    "impressions": c.impressions,
                    "clicks": c.clicks,
                    "conversions": c.conversions,
                    "roas": c.roas,
                    "cpa_inr": c.cpa_inr,
                    "ctr": c.ctr,
                    "status": c.status,
                }
                for c in snapshot.campaigns
            ],
            "daily_trends": daily_trends,
            "notes": snapshot.notes,
            "meta": get_synthetic_meta(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc



@app.get("/api/dashboard/stats")
def dashboard_stats() -> dict[str, Any]:
    """Quick stats for the console's right rail, computed from real data."""
    try:
        snapshot = connector.fetch_campaigns()
    except Exception as exc:
        logger.warning("Dashboard stats fetch failed: %s", exc)
        return {
            "active_campaigns": 0,
            "total_spend_inr": 0.0,
            "blended_roas": 0.0,
            "pending_approvals": 0,
            "data_source": "degraded",
            "error": str(exc),
        }

    checkpoints = checkpointer.list_checkpoints()
    pending = sum(1 for c in checkpoints if c.get("status") == "pending_approval")

    return {
        "active_campaigns": sum(
            1 for c in snapshot.campaigns if str(c.status).upper() in ("ENABLED", "ACTIVE")
        ),
        "total_campaigns": len(snapshot.campaigns),
        "total_spend_inr": snapshot.total_spend_inr,
        "blended_roas": snapshot.blended_roas,
        "pending_approvals": pending,
        "total_runs": len(checkpoints),
        "data_source": snapshot.source,
        "data_source_label": {
            "live": "Live platform API",
            "synthetic": "Synthetic dataset",
            "byod": "Imported dataset",
            "degraded": "Degraded — fetch failed",
        }.get(snapshot.source, snapshot.source),
    }


@app.post("/api/connections/verify")
def verify_connections() -> dict[str, Any]:
    """Probe each connected ad platform and report what actually answered.

    This is what makes the Settings screen trustworthy: it reports a live
    handshake, not merely the presence of stored credentials.
    """
    results: dict[str, Any] = {}

    for platform, builder in (
        ("google_ads", connector._build_google_client),
        ("meta_ads", connector._build_meta_client),
    ):
        if not connector.secret_store.has_credentials(platform):
            results[platform] = {"connected": False, "reason": "No credentials stored"}
            continue
        try:
            results[platform] = builder().verify()
        except Exception as exc:
            results[platform] = {"connected": False, "reason": str(exc)}

    return {
        "platforms": results,
        "data_source": "live" if any(r.get("connected") for r in results.values()) else "synthetic",
    }


# Mount Web Console frontend (React SPA)
web_dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "apps", "web", "dist")
web_src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "apps", "web")
web_dir = web_dist_dir if os.path.exists(web_dist_dir) else web_src_dir

if os.path.exists(web_dir):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")



