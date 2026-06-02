from __future__ import annotations

from pathlib import Path

from model_gateway.store import ModelGatewayStatusResponse, ModelGatewayStore

from app.db.session import Database


def get_model_gateway_status(
    database: Database,
    storage_root: Path,
) -> ModelGatewayStatusResponse:
    return ModelGatewayStore(database.path, storage_root).get_status()
