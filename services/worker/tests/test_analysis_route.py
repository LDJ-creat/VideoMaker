from __future__ import annotations

import pytest

from model_gateway.store import ModelGatewayStore

from app.pipelines.analysis_route import resolve_structure_analysis_route


@pytest.fixture()
def store(tmp_path) -> ModelGatewayStore:
    gateway_store = ModelGatewayStore(tmp_path / "db.sqlite3", tmp_path / "storage")
    gateway_store.ensure_initialized()
    return gateway_store


def test_resolve_structure_analysis_route_defaults_map_reduce(store: ModelGatewayStore) -> None:
    assert resolve_structure_analysis_route(store) == "map_reduce"


def test_resolve_structure_analysis_route_direct_when_configured(
    store: ModelGatewayStore,
) -> None:
    store.update_providers(
        {
            "videoUnderstanding": {
                "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
                "apiKey": "secret",
                "model": "doubao-seed-1-6-250615",
            }
        }
    )
    assert resolve_structure_analysis_route(store) == "direct_multimodal"


def test_resolve_structure_analysis_route_respects_preference(store: ModelGatewayStore) -> None:
    store.update_providers(
        {
            "videoUnderstanding": {
                "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
                "apiKey": "secret",
                "model": "doubao-seed-1-6-250615",
            }
        }
    )
    store.update_preferences({"directMultimodalAnalysisEnabled": False})
    assert resolve_structure_analysis_route(store) == "map_reduce"
