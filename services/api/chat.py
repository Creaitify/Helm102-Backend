"""The console's single send-path: one prompt in, a persisted exchange out.

`POST /api/chat` is what the composer calls. It owns the whole turn:

  1. Open (or reuse) a conversation and title it from the first prompt.
  2. Persist the user turn.
  3. Route to the selected mode — one specialist agent, or the full Governor relay.
  4. Persist the agent turn with its complete render payload.

Because step 4 stores the rendered blocks, reopening a conversation replays
exactly what the operator saw without re-running any agent or re-billing a
model call.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.api import agents, conversations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Composer modes -> the agent that handles them. `pipeline` is the full relay.
MODES: dict[str, dict[str, str]] = {
    "pipeline": {
        "label": "Full HELM Pipeline",
        "agent": "governor",
        "badge": "Full Pipeline Mode",
        "description": "All six hops: analyze, create, verify, budget, then pause for approval.",
    },
    "analyst": {
        "label": "Analyst",
        "agent": "analyst",
        "badge": "Direct Analyst Mode",
        "description": "Performance diagnosis only — fastest path to insight.",
    },
    "creative": {
        "label": "Creative",
        "agent": "creative",
        "badge": "Direct Creative Mode",
        "description": "Ad variations with a per-variation compliance verdict.",
    },
    "media_buyer": {
        "label": "Media Buyer",
        "agent": "media_buyer",
        "badge": "Direct Media Buyer Mode",
        "description": "Budget reallocation inside the ±25% policy envelope.",
    },
    "compliance": {
        "label": "Compliance",
        "agent": "compliance",
        "badge": "Direct Compliance Mode",
        "description": "Paste ad copy to scan it against the SEBI rulebook.",
    },
}


class ChatRequest(BaseModel):
    prompt: str = Field(..., json_schema_extra={"example": "Analyze campaign performance and recommend budget optimization"})
    mode: str = Field(default="pipeline")
    conversation_id: str | None = Field(default=None)
    grounded: bool = Field(default=True)


@router.get("/modes")
def list_modes() -> list[dict[str, Any]]:
    """Modes the composer dropdown offers."""
    return [{"id": mode_id, **meta} for mode_id, meta in MODES.items()]


@router.post("")
async def send_message(req: ChatRequest) -> dict[str, Any]:
    """Run one full conversational turn and persist both sides of it."""
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    mode = req.mode.lower().strip()
    if mode not in MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown mode '{mode}'. Available: {', '.join(MODES)}",
        )

    # 1. Conversation
    if req.conversation_id:
        conversation = conversations.get_conversation(req.conversation_id)
    else:
        conversation = conversations.create_conversation(title="New Conversation", mode=mode)

    conversation_id = conversation["id"]

    # 2. User turn
    user_message = conversations.append_message(
        conversation_id=conversation_id, role="user", content=prompt
    )
    conversations.autotitle(conversation_id, prompt)

    # 3. Agent turn
    agent_id = MODES[mode]["agent"]
    try:
        envelope = await agents.invoke_agent(
            agent_id,
            agents.AgentInvokeRequest(
                prompt=prompt, conversation_id=conversation_id, grounded=req.grounded
            ),
        )
    except HTTPException as exc:
        # Persist the failure so the thread reflects what actually happened.
        error_message = conversations.append_message(
            conversation_id=conversation_id,
            role="agent",
            agent=agent_id,
            content=f"{MODES[mode]['label']} could not complete this request: {exc.detail}",
            payload={
                "agent": agent_id,
                "agent_label": agents.AGENT_REGISTRY[agent_id]["label"],
                "error": str(exc.detail),
                "blocks": [],
                "mode": mode,
            },
        )
        return {
            "conversation_id": conversation_id,
            "mode": mode,
            "user_message": user_message,
            "agent_message": error_message,
            "error": str(exc.detail),
        }

    envelope["mode"] = mode
    envelope["mode_badge"] = MODES[mode]["badge"]

    agent_message = conversations.append_message(
        conversation_id=conversation_id,
        role="agent",
        agent=agent_id,
        content=envelope.get("message", ""),
        payload=envelope,
    )

    return {
        "conversation_id": conversation_id,
        "mode": mode,
        "user_message": user_message,
        "agent_message": agent_message,
    }
