"""Durable SQLite checkpointing for Governor runs."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GovernorCheckpointer:
    """Persistent SQLite checkpointer for Governor runs and HITL resumes."""

    def __init__(self, db_path: Path | str = "services/api/data/governor_checkpoints.sqlite") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        run_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        current_hop_index INTEGER NOT NULL,
                        state_json TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        finally:
            conn.close()

    def save_checkpoint(self, run_id: str, status: str, hop_index: int, state: dict[str, Any]) -> None:
        """Save or update checkpoint state."""
        state_json = json.dumps(state)
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("""
                    INSERT INTO checkpoints (run_id, status, current_hop_index, state_json, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(run_id) DO UPDATE SET
                        status=excluded.status,
                        current_hop_index=excluded.current_hop_index,
                        state_json=excluded.state_json,
                        updated_at=CURRENT_TIMESTAMP
                """, (run_id, status, hop_index, state_json))
        finally:
            conn.close()

    def load_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        """Load state for a run."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT state_json FROM checkpoints WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
        finally:
            conn.close()

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """List all saved checkpoints."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT run_id, status, current_hop_index, updated_at FROM checkpoints ORDER BY updated_at DESC")
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
