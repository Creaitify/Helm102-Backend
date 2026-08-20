"""Conversation persistence — the sidebar's "Recent Conversations" is real state.

A conversation is an ordered list of messages. User turns store text; agent
turns store the full agent envelope (message + blocks + raw) so reopening a
conversation re-renders the exact cards the operator saw, without re-running
the agent.

Storage is a standalone SQLite file so it survives restarts and stays
independent of the checkpoint/audit stores.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "data", "helm_conversations.sqlite")
DB_PATH = os.environ.get("HELM_CONVERSATIONS_DB", _DEFAULT_DB)

_lock = threading.Lock()

# Icons match the Material Symbols the sidebar renders per conversation mode.
_MODE_ICONS = {
    "pipeline": "hub",
    "analyst": "analytics",
    "creative": "brush",
    "media_buyer": "account_balance_wallet",
    "compliance": "policy",
    "governor": "hub",
}


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    return conn


def init_db() -> None:
    """Create the conversation tables if they do not exist yet."""
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                mode        TEXT NOT NULL DEFAULT 'pipeline',
                pinned      INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role            TEXT NOT NULL,
                agent           TEXT,
                content         TEXT NOT NULL DEFAULT '',
                payload_json    TEXT,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated
                ON conversations(updated_at DESC);
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New Conversation")
    mode: str = Field(default="pipeline")


class UpdateConversationRequest(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    mode: str | None = None


class AppendMessageRequest(BaseModel):
    role: str = Field(..., json_schema_extra={"example": "user"})  # "user" | "agent" | "system"
    content: str = Field(default="")
    agent: str | None = Field(default=None)
    payload: dict[str, Any] | None = Field(
        default=None, description="Full agent envelope, replayed verbatim on reopen."
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _row_to_conversation(row: sqlite3.Row, message_count: int = 0) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "mode": row["mode"],
        "icon": _MODE_ICONS.get(row["mode"], "chat"),
        "pinned": bool(row["pinned"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "message_count": message_count,
    }


def _row_to_message(row: sqlite3.Row) -> dict[str, Any]:
    payload = None
    if row["payload_json"]:
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            logger.warning("Message %s has unparseable payload_json", row["id"])
    return {
        "id": row["id"],
        "role": row["role"],
        "agent": row["agent"],
        "content": row["content"],
        "payload": payload,
        "created_at": row["created_at"],
    }


def create_conversation(title: str = "New Conversation", mode: str = "pipeline") -> dict[str, Any]:
    """Create a conversation and return it (also used internally by the chat route)."""
    conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    now = _now()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, mode, pinned, created_at, updated_at) "
            "VALUES (?, ?, ?, 0, ?, ?)",
            (conv_id, title.strip() or "New Conversation", mode, now, now),
        )
    return {
        "id": conv_id,
        "title": title.strip() or "New Conversation",
        "mode": mode,
        "icon": _MODE_ICONS.get(mode, "chat"),
        "pinned": False,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }


def append_message(
    conversation_id: str,
    role: str,
    content: str = "",
    agent: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one turn and bump the conversation's updated_at."""
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = _now()
    with _lock, _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not exists:
            raise KeyError(conversation_id)

        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, agent, content, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                message_id,
                conversation_id,
                role,
                agent,
                content,
                json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                now,
            ),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id)
        )

    return {
        "id": message_id,
        "role": role,
        "agent": agent,
        "content": content,
        "payload": payload,
        "created_at": now,
    }


def autotitle(conversation_id: str, first_prompt: str) -> None:
    """Name an untitled conversation after its opening prompt."""
    title = " ".join(first_prompt.split())[:60].strip()
    if not title:
        return
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ? AND title = 'New Conversation'",
            (title, conversation_id),
        )


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("")
def list_conversations(limit: int = 50) -> list[dict[str, Any]]:
    """Most-recently-updated conversations, pinned ones first."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.pinned DESC, c.updated_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()
    return [_row_to_conversation(r, r["message_count"]) for r in rows]


@router.post("")
def create_conversation_route(req: CreateConversationRequest) -> dict[str, Any]:
    return create_conversation(title=req.title, mode=req.mode)


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str) -> dict[str, Any]:
    """One conversation with its full message history."""
    with _connect() as conn:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
        messages = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at, rowid",
            (conversation_id,),
        ).fetchall()

    return {
        **_row_to_conversation(conv, len(messages)),
        "messages": [_row_to_message(m) for m in messages],
    }


@router.patch("/{conversation_id}")
def update_conversation(conversation_id: str, req: UpdateConversationRequest) -> dict[str, Any]:
    """Rename, pin/unpin, or change the mode of a conversation."""
    fields: list[str] = []
    values: list[Any] = []
    if req.title is not None:
        fields.append("title = ?")
        values.append(req.title.strip() or "Untitled")
    if req.pinned is not None:
        fields.append("pinned = ?")
        values.append(1 if req.pinned else 0)
    if req.mode is not None:
        fields.append("mode = ?")
        values.append(req.mode)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    fields.append("updated_at = ?")
    values.extend([_now(), conversation_id])

    with _lock, _connect() as conn:
        cursor = conn.execute(
            f"UPDATE conversations SET {', '.join(fields)} WHERE id = ?", values
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

    return get_conversation(conversation_id)


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, Any]:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    return {"status": "deleted", "id": conversation_id}


@router.post("/{conversation_id}/messages")
def append_message_route(conversation_id: str, req: AppendMessageRequest) -> dict[str, Any]:
    try:
        return append_message(
            conversation_id=conversation_id,
            role=req.role,
            content=req.content,
            agent=req.agent,
            payload=req.payload,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Conversation {conversation_id} not found"
        ) from exc
