from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db.session import Database
from stock_media.store import StockMediaStore, probe_pexels_api


class StockMediaService:
    def __init__(self, database: Database, storage_root: Path) -> None:
        self._store = StockMediaStore(database.path, storage_root)

    def get_status(self) -> dict[str, Any]:
        return self._store.get_status()

    def update_settings(self, *, api_key: str | None) -> dict[str, Any]:
        if api_key is not None and not api_key.strip():
            return self._store.update_api_key(None)
        if api_key is not None:
            return self._store.update_api_key(api_key.strip())
        raise ValueError("No stock media fields to update")

    def probe(self, *, api_key: str | None = None) -> dict[str, Any]:
        key = api_key
        if key is None:
            creds = self._store.get_credentials()
            if creds is None:
                raise ValueError("Pexels API key is not configured")
            key = creds.api_key
        return probe_pexels_api(api_key=key)

    def credentials_for_worker(self) -> str | None:
        creds = self._store.get_credentials()
        return creds.api_key if creds is not None else None
