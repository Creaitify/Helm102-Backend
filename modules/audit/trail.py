"""Append-only immutable audit log storing every envelope and execution action."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from modules.governor.envelope import HandoffEnvelope

logger = logging.getLogger(__name__)


class AuditTrail:
    """Immutable audit trail for all orchestration hops and platform dispatches."""

    def __init__(self, db_path: Path | str = "services/api/data/helm_audit.sqlite") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        hop_index INTEGER NOT NULL,
                        source TEXT NOT NULL,
                        target TEXT NOT NULL,
                        action TEXT NOT NULL,
                        status TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        rationale TEXT,
                        error TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_run_id ON audit_events (run_id)")
        finally:
            conn.close()

    def record(self, run_id: str, envelope: HandoffEnvelope) -> None:
        """Append an envelope to the immutable log."""
        payload_json = json.dumps(envelope.payload)
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("""
                    INSERT INTO audit_events (
                        run_id, hop_index, source, target, action, status, payload_json, rationale, error, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id,
                    envelope.hop_index,
                    envelope.source,
                    envelope.target,
                    envelope.action,
                    envelope.status.value,
                    payload_json,
                    envelope.rationale,
                    envelope.error,
                    envelope.timestamp,
                ))
        finally:
            conn.close()

    def get_trail(self, run_id: str) -> list[dict[str, Any]]:
        """Retrieve full chronological trail for a run."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, run_id, hop_index, source, target, action, status, payload_json, rationale, error, created_at
                FROM audit_events
                WHERE run_id = ?
                ORDER BY id ASC
            """, (run_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "run_id": r["run_id"],
                    "hop_index": r["hop_index"],
                    "source": r["source"],
                    "target": r["target"],
                    "action": r["action"],
                    "status": r["status"],
                    "payload": json.loads(r["payload_json"]),
                    "rationale": r["rationale"],
                    "error": r["error"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()
