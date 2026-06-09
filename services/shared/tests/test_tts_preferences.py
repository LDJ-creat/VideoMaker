from __future__ import annotations

import pytest

from model_gateway.tts_preferences import (
    normalize_tts_preferences,
    patch_tts_preferences,
)
from model_gateway.store import ModelGatewayStore


def test_normalize_tts_preferences_defaults() -> None:
    prefs = normalize_tts_preferences(None)
    assert prefs["resourceId"] == "seed-tts-2.0"
    assert prefs["speaker"] == "zh_female_vv_uranus_bigtts"


def test_patch_tts_preferences_validates_speech_rate() -> None:
    current = normalize_tts_preferences(None)
    with pytest.raises(ValueError, match="speechRate"):
        patch_tts_preferences(current, {"speechRate": 200})


def test_store_get_and_update_tts_preferences(store: ModelGatewayStore) -> None:
    status = store.get_status()
    assert status["ttsPreferences"]["resourceId"] == "seed-tts-2.0"

    updated = store.update_tts_preferences({"speechRate": 15, "contextTexts": "更活泼"})
    assert updated["speechRate"] == 15
    assert updated["contextTexts"] == "更活泼"

    status = store.get_status()
    assert status["ttsPreferences"]["speechRate"] == 15


@pytest.fixture()
def store(tmp_path) -> ModelGatewayStore:
    db_path = tmp_path / "videomaker.sqlite3"
    storage_root = tmp_path / "storage"
    gateway_store = ModelGatewayStore(db_path, storage_root)
    gateway_store.ensure_initialized()
    return gateway_store
