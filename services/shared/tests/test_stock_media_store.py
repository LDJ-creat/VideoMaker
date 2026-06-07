from __future__ import annotations

from pathlib import Path

from stock_media.store import StockMediaStore


def test_stock_media_store_encrypt_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "videomaker.sqlite3"
    storage_root = tmp_path / "storage"
    store = StockMediaStore(db_path, storage_root)

    status = store.update_api_key("pexels-test-key")
    assert status["configured"] is True
    assert status["hasApiKey"] is True

    creds = store.get_credentials()
    assert creds is not None
    assert creds.api_key == "pexels-test-key"
