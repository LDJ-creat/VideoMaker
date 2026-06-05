from __future__ import annotations

from pathlib import Path

import pytest

from model_gateway.store import ModelGatewayStore


@pytest.fixture()
def store_paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "videomaker.sqlite3", tmp_path / "storage"


@pytest.fixture()
def store(store_paths: tuple[Path, Path]) -> ModelGatewayStore:
    db_path, storage_root = store_paths
    gateway_store = ModelGatewayStore(db_path, storage_root)
    gateway_store.ensure_initialized()
    return gateway_store


def test_preferences_default_and_route_preview(store: ModelGatewayStore) -> None:
    status = store.get_status()
    assert status["preferences"]["directMultimodalAnalysisEnabled"] is True
    assert status["analysisRoutePreview"] == "map_reduce"
    assert "videoUnderstanding" in status["providers"]


def test_route_preview_direct_when_video_understanding_configured(
    store: ModelGatewayStore,
) -> None:
    store.update_providers(
        {
            "videoUnderstanding": {
                "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
                "apiKey": "video-secret",
                "model": "doubao-seed-1-6-250615",
            }
        }
    )
    status = store.get_status()
    assert status["analysisRoutePreview"] == "direct_multimodal"


def test_preferences_toggle_forces_map_reduce(store: ModelGatewayStore) -> None:
    store.update_providers(
        {
            "videoUnderstanding": {
                "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
                "apiKey": "video-secret",
                "model": "doubao-seed-1-6-250615",
            }
        }
    )
    store.update_preferences({"directMultimodalAnalysisEnabled": False})
    status = store.get_status()
    assert status["preferences"]["directMultimodalAnalysisEnabled"] is False
    assert status["analysisRoutePreview"] == "map_reduce"


def test_update_preferences_rejects_non_boolean(store: ModelGatewayStore) -> None:
    with pytest.raises(ValueError, match="directMultimodalAnalysisEnabled"):
        store.update_preferences({"directMultimodalAnalysisEnabled": "no"})
