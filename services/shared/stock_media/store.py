from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from model_gateway.crypto import decrypt_api_key, encrypt_api_key

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stock_media_providers (
  provider TEXT PRIMARY KEY,
  api_key_ciphertext BLOB,
  updated_at TEXT NOT NULL
);
"""

PROVIDER_PEXELS = "pexels"


class StockMediaStatus(TypedDict):
    configured: bool
    hasApiKey: bool
    provider: str


@dataclass(frozen=True)
class StockMediaCredentials:
    api_key: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class StockMediaStore:
    def __init__(self, database_path: Path, storage_root: Path) -> None:
        self._database_path = database_path
        self._storage_root = storage_root

    def _connect(self) -> sqlite3.Connection:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def ensure_initialized(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA_SQL)
            now = _now_iso()
            connection.execute(
                """
                INSERT OR IGNORE INTO stock_media_providers (
                  provider, api_key_ciphertext, updated_at
                ) VALUES (?, NULL, ?)
                """,
                (PROVIDER_PEXELS, now),
            )
            connection.commit()

    def get_status(self) -> StockMediaStatus:
        self.ensure_initialized()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT api_key_ciphertext FROM stock_media_providers WHERE provider = ?",
                (PROVIDER_PEXELS,),
            ).fetchone()
        has_key = row is not None and row["api_key_ciphertext"] is not None
        return {
            "provider": PROVIDER_PEXELS,
            "configured": has_key,
            "hasApiKey": has_key,
        }

    def update_api_key(self, api_key: str | None) -> StockMediaStatus:
        self.ensure_initialized()
        now = _now_iso()
        ciphertext = encrypt_api_key(self._storage_root, api_key) if api_key else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO stock_media_providers (provider, api_key_ciphertext, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                  api_key_ciphertext = excluded.api_key_ciphertext,
                  updated_at = excluded.updated_at
                """,
                (PROVIDER_PEXELS, ciphertext, now),
            )
            connection.commit()
        return self.get_status()

    def get_credentials(self) -> StockMediaCredentials | None:
        self.ensure_initialized()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT api_key_ciphertext FROM stock_media_providers WHERE provider = ?",
                (PROVIDER_PEXELS,),
            ).fetchone()
        if row is None or row["api_key_ciphertext"] is None:
            return None
        api_key = decrypt_api_key(self._storage_root, row["api_key_ciphertext"])
        if not api_key.strip():
            return None
        return StockMediaCredentials(api_key=api_key.strip())


def probe_pexels_api(*, api_key: str) -> dict[str, Any]:
    import httpx

    key = api_key.strip()
    if not key:
        raise ValueError("apiKey is required")
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": "nature", "per_page": 1},
        )
    if response.status_code == 401:
        raise ValueError("Pexels API key is invalid")
    if response.status_code == 429:
        raise ValueError("Pexels API rate limit exceeded")
    if response.status_code >= 400:
        raise ValueError(f"Pexels probe failed with status {response.status_code}")
    payload = response.json()
    total = int(payload.get("total_results") or 0) if isinstance(payload, dict) else 0
    return {"ok": True, "provider": PROVIDER_PEXELS, "sampleResultCount": total}
