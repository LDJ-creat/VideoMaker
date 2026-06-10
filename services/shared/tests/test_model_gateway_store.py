from __future__ import annotations

import json
from pathlib import Path

import pytest

from model_gateway.crypto import decrypt_api_key, encrypt_api_key
from model_gateway.fixture import is_fixture_mode
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


def test_is_fixture_mode_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_FIXTURE_MODE", raising=False)
    assert is_fixture_mode() is False

    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "true")
    assert is_fixture_mode() is True


def test_encrypt_roundtrip(store_paths: tuple[Path, Path]) -> None:
    _, storage_root = store_paths
    ciphertext = encrypt_api_key(storage_root, "sk-test")
    assert decrypt_api_key(storage_root, ciphertext) == "sk-test"


def test_get_status_unconfigured(store: ModelGatewayStore) -> None:
    status = store.get_status()
    assert status["providers"]["text"]["configured"] is False
    assert status["providers"]["text"]["hasApiKey"] is False
    assert status["providers"]["image"]["configured"] is False


def test_update_and_get_status(store: ModelGatewayStore) -> None:
    store.update_providers(
        {
            "text": {
                "baseUrl": "https://api.openai.com/v1",
                "apiKey": "text-secret",
                "model": "gpt-4o",
            },
            "image": {
                "baseUrl": "https://api.openai.com/v1",
                "apiKey": "image-secret",
                "model": "dall-e-3",
            },
        }
    )
    status = store.get_status()
    assert status["providers"]["text"] == {
        "configured": True,
        "hasApiKey": True,
        "model": "gpt-4o",
        "driver": "openai_compatible",
        "baseUrl": "https://api.openai.com/v1",
    }
    assert status["providers"]["vision"]["configured"] is True
    assert status["providers"]["vision"]["model"] == "gpt-4o-mini"
    raw = json.dumps(status)
    assert "text-secret" not in raw
    assert "image-secret" not in raw


def test_update_preserves_api_key_when_omitted(store: ModelGatewayStore) -> None:
    store.update_providers(
        {
            "text": {
                "baseUrl": "https://api.openai.com/v1",
                "apiKey": "keep-me",
                "model": "gpt-4o-mini",
            }
        }
    )
    store.update_providers({"text": {"model": "gpt-4o"}})
    creds = store.get_credentials()
    assert creds["text"].api_key == "keep-me"
    assert creds["text"].model == "gpt-4o"


def test_update_clears_api_key_with_empty_string(store: ModelGatewayStore) -> None:
    store.update_providers({"text": {"apiKey": "temp-key", "model": "m"}})
    store.update_providers({"text": {"apiKey": ""}})
    assert store.get_credentials()["text"].api_key == ""
    assert store.get_status()["providers"]["text"]["configured"] is False


def test_vision_fallback_uses_text_credentials(store: ModelGatewayStore) -> None:
    store.update_providers(
        {
            "text": {"apiKey": "text-key", "model": "text-model"},
            "vision": {"apiKey": "vision-key", "model": "vision-model"},
        }
    )
    creds = store.get_credentials()
    assert creds["vision"].api_key == "vision-key"
    assert creds["vision"].model == "vision-model"

    store.update_providers({"vision": {"apiKey": ""}})
    creds = store.get_credentials()
    assert creds["vision"].api_key == "text-key"


def test_video_configured_with_base_url(store: ModelGatewayStore) -> None:
    store.update_providers(
        {
            "video": {
                "baseUrl": "https://video.example/v1",
                "model": "video-model",
                "driver": "generic_job",
            }
        }
    )
    status = store.get_status()
    assert status["providers"]["video"]["configured"] is True
    assert status["providers"]["video"]["model"] == "video-model"


def test_video_ark_normalizes_driver_and_wan_model(store: ModelGatewayStore) -> None:
    store.update_providers(
        {
            "video": {
                "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
                "model": "wan2.7-t2v",
                "driver": "generic_job",
            }
        }
    )
    status = store.get_status()
    assert status["providers"]["video"]["driver"] == "volcengine_seeddance"
    assert status["providers"]["video"]["model"] == "doubao-seedance-2-0-260128"
    creds = store.get_credentials()
    assert creds["video"].driver == "volcengine_seeddance"
    assert creds["video"].model == "doubao-seedance-2-0-260128"


def test_video_dashscope_normalizes_driver_and_image_model(store: ModelGatewayStore) -> None:
    store.update_providers(
        {
            "video": {
                "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "wan2.7-image-pro",
                "driver": "generic_job",
            }
        }
    )
    status = store.get_status()
    assert status["providers"]["video"]["driver"] == "dashscope_wan"
    assert status["providers"]["video"]["model"] == "wan2.7-t2v"
    creds = store.get_credentials()
    assert creds["video"].driver == "dashscope_wan"
    assert creds["video"].model == "wan2.7-t2v"
