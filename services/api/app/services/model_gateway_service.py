from __future__ import annotations

from pathlib import Path
from typing import Any

from model_gateway.store import ModelGatewayStatusResponse, ModelGatewayStore

from app.db.session import Database


class ModelGatewayService:
    def __init__(self, database: Database, storage_root: Path) -> None:
        self._store = ModelGatewayStore(database.path, storage_root)

    def get_status(self) -> ModelGatewayStatusResponse:
        return self._store.get_status()

    def update_providers(self, updates: dict[str, dict[str, Any]]) -> ModelGatewayStatusResponse:
        return self._store.update_providers(updates)
