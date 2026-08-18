"""HELM02 Secret Store implementation.

Implements `mureo.core.secret_store.SecretStore` Protocol with server-side custody.
Guarantees that credentials are never stored in or read from `~/.mureo/`.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)


class HelmSecretStore:
    """Server-side credential store for HELM02.
    
    Adheres to the `mureo.core.secret_store.SecretStore` protocol without
    touching the user's home directory.
    """

    def __init__(self, storage_path: Path | None = None, memory_only: bool = False) -> None:
        self._memory_only = memory_only
        self._in_memory_store: dict[str, dict[str, Any]] = {}
        
        if storage_path is None:
            base_dir = Path(os.environ.get("HELM_SECRETS_DIR", "services/api/data"))
            self.storage_path = base_dir / "vault.json"
        else:
            self.storage_path = storage_path

        if not self._memory_only and self.storage_path.exists():
            self._load_from_disk()

    @property
    def credentials_write_path(self) -> Path | None:
        """Server-controlled storage path."""
        return None if self._memory_only else self.storage_path

    @property
    def multi_account_auth(self) -> bool:
        """HELM operates as multi-account orchestration."""
        return True

    def _load_from_disk(self) -> None:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._in_memory_store = data
        except Exception as exc:
            logger.warning("Could not load secrets from %s: %s", self.storage_path, exc)

    def _persist_to_disk(self) -> None:
        if self._memory_only:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.storage_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self._in_memory_store, f, indent=2)
        temp_path.replace(self.storage_path)

    def load(self, key: str) -> dict[str, Any]:
        """Return credentials for platform key or empty dict."""
        return dict(self._in_memory_store.get(key, {}))

    def save(self, key: str, value: dict[str, Any]) -> None:
        """Persist credentials for platform key."""
        self._in_memory_store[key] = dict(value)
        self._persist_to_disk()

    def delete(self, key: str) -> None:
        """Idempotently delete credentials for platform key."""
        if key in self._in_memory_store:
            del self._in_memory_store[key]
            self._persist_to_disk()

    def has_credentials(self, key: str) -> bool:
        """Check if active credentials exist for platform key."""
        val = self._in_memory_store.get(key)
        return bool(val and isinstance(val, dict) and len(val) > 0)
