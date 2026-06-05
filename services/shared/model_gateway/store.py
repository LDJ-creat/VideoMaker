from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from model_gateway.constants import (
    DEFAULT_BASE_URL,
    DEFAULT_BASE_URLS,
    DEFAULT_DRIVERS,
    DEFAULT_MODELS,
    PROVIDERS,
)
from model_gateway.analysis_route import (
    DEFAULT_PREFERENCES,
    normalize_preferences,
    resolve_analysis_route_preview,
)
from model_gateway.crypto import decrypt_api_key, encrypt_api_key
from model_gateway.fixture import is_fixture_mode
from model_gateway.video_driver import (
    normalize_video_model,
    resolve_effective_video_driver,
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS model_gateway_providers (
  provider TEXT PRIMARY KEY,
  base_url TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  driver TEXT NOT NULL DEFAULT 'openai_compatible',
  api_key_ciphertext BLOB,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_gateway_preferences (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""
_PREFERENCES_KEY = "analysis"


class ProviderStatus(TypedDict):
    configured: bool
    hasApiKey: bool
    model: str | None
    driver: str
    baseUrl: str


class ModelGatewayStatusResponse(TypedDict):
    fixtureMode: bool
    providers: dict[str, ProviderStatus]
    preferences: dict[str, bool]
    analysisRoutePreview: str


@dataclass(frozen=True)
class ProviderCredentials:
    base_url: str
    api_key: str
    model: str
    driver: str


class ModelGatewayStore:
    def __init__(self, database_path: Path, storage_root: Path) -> None:
        self._database_path = database_path
        self._storage_root = storage_root

    def _connect(self) -> sqlite3.Connection:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA_SQL)
            connection.commit()

    def ensure_initialized(self) -> None:
        self.ensure_schema()
        now = _now_iso()
        with self._connect() as connection:
            for provider in PROVIDERS:
                default_base = DEFAULT_BASE_URLS.get(provider, DEFAULT_BASE_URL)
                connection.execute(
                    """
                    INSERT OR IGNORE INTO model_gateway_providers (
                      provider, base_url, model, driver, api_key_ciphertext, updated_at
                    ) VALUES (?, ?, ?, ?, NULL, ?)
                    """,
                    (
                        provider,
                        default_base if provider in DEFAULT_BASE_URLS else "",
                        DEFAULT_MODELS[provider],
                        DEFAULT_DRIVERS[provider],
                        now,
                    ),
                )
            _ensure_default_preferences(connection, now)
            _repair_video_provider_rows(connection)
            connection.commit()

    def get_preferences(self) -> dict[str, bool]:
        self.ensure_initialized()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM model_gateway_preferences WHERE key = ?",
                (_PREFERENCES_KEY,),
            ).fetchone()
        if row is None:
            return dict(DEFAULT_PREFERENCES)
        try:
            payload = json.loads(str(row["value_json"]))
        except json.JSONDecodeError:
            return dict(DEFAULT_PREFERENCES)
        return normalize_preferences(payload if isinstance(payload, dict) else None)

    def update_preferences(self, patch: dict[str, Any]) -> dict[str, bool]:
        self.ensure_initialized()
        current = self.get_preferences()
        if "directMultimodalAnalysisEnabled" in patch:
            value = patch["directMultimodalAnalysisEnabled"]
            if not isinstance(value, bool):
                raise ValueError("directMultimodalAnalysisEnabled must be a boolean")
            current["directMultimodalAnalysisEnabled"] = value
        now = _now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO model_gateway_preferences (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value_json = excluded.value_json,
                  updated_at = excluded.updated_at
                """,
                (_PREFERENCES_KEY, json.dumps(current, ensure_ascii=False), now),
            )
            connection.commit()
        return current

    def get_status(self) -> ModelGatewayStatusResponse:
        self.ensure_initialized()
        rows = self._load_all_rows()
        credentials = self._rows_to_credentials(rows)
        providers: dict[str, ProviderStatus] = {}
        for provider in PROVIDERS:
            providers[provider] = _status_for_provider(
                provider,
                rows[provider],
                credentials,
            )
        preferences = self.get_preferences()
        return {
            "fixtureMode": is_fixture_mode(),
            "providers": providers,
            "preferences": preferences,
            "analysisRoutePreview": resolve_analysis_route_preview(
                preferences=preferences,
                video_understanding=providers["videoUnderstanding"],
            ),
        }

    def get_credentials(self) -> dict[str, ProviderCredentials]:
        """Decrypted credentials for worker GatewayConfig (includes vision fallback)."""
        self.ensure_initialized()
        rows = self._load_all_rows()
        return self._rows_to_credentials(rows)

    def update_providers(self, updates: dict[str, dict[str, Any]]) -> ModelGatewayStatusResponse:
        self.ensure_initialized()
        now = _now_iso()
        with self._connect() as connection:
            for provider, patch in updates.items():
                if provider not in PROVIDERS:
                    raise ValueError(f"Unknown provider: {provider}")
                row = connection.execute(
                    "SELECT * FROM model_gateway_providers WHERE provider = ?",
                    (provider,),
                ).fetchone()
                if row is None:
                    raise ValueError(f"Provider not initialized: {provider}")

                base_url = row["base_url"]
                model = row["model"]
                driver = row["driver"]
                ciphertext = row["api_key_ciphertext"]

                if "baseUrl" in patch and patch["baseUrl"] is not None:
                    base_url = str(patch["baseUrl"]).strip()
                if "model" in patch and patch["model"] is not None:
                    model = str(patch["model"]).strip()
                if "driver" in patch and patch["driver"] is not None:
                    driver = str(patch["driver"]).strip()

                if provider == "video":
                    base_url = str(base_url or "").strip()
                    model = normalize_video_model(str(model or "").strip(), base_url=base_url)
                    driver = resolve_effective_video_driver(str(driver or "").strip(), base_url)

                if "apiKey" in patch:
                    api_key_value = patch["apiKey"]
                    if api_key_value is None:
                        pass
                    elif api_key_value == "":
                        ciphertext = None
                    else:
                        ciphertext = encrypt_api_key(
                            self._storage_root,
                            str(api_key_value).strip(),
                        )

                connection.execute(
                    """
                    UPDATE model_gateway_providers
                    SET base_url = ?, model = ?, driver = ?, api_key_ciphertext = ?, updated_at = ?
                    WHERE provider = ?
                    """,
                    (base_url, model, driver, ciphertext, now, provider),
                )
            connection.commit()
        return self.get_status()

    def update_settings(
        self,
        *,
        provider_updates: dict[str, dict[str, Any]] | None = None,
        preference_updates: dict[str, Any] | None = None,
    ) -> ModelGatewayStatusResponse:
        if provider_updates:
            self.update_providers(provider_updates)
        if preference_updates:
            self.update_preferences(preference_updates)
        return self.get_status()

    def _load_all_rows(self) -> dict[str, sqlite3.Row]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_gateway_providers ORDER BY provider"
            ).fetchall()
        by_provider = {str(row["provider"]): row for row in rows}
        for provider in PROVIDERS:
            if provider not in by_provider:
                raise RuntimeError(f"Missing provider row: {provider}")
        return by_provider

    def _rows_to_credentials(
        self,
        rows: dict[str, sqlite3.Row],
    ) -> dict[str, ProviderCredentials]:
        raw: dict[str, ProviderCredentials] = {}
        for provider in PROVIDERS:
            row = rows[provider]
            stored_base = (row["base_url"] or "").strip()
            base_url = stored_base or DEFAULT_BASE_URL
            model = (row["model"] or "").strip() or DEFAULT_MODELS[provider]
            driver = (row["driver"] or "").strip() or DEFAULT_DRIVERS[provider]
            if provider == "video":
                model = normalize_video_model(model, base_url=base_url)
                driver = resolve_effective_video_driver(driver, base_url)
            api_key = decrypt_api_key(self._storage_root, row["api_key_ciphertext"])
            raw[provider] = ProviderCredentials(
                base_url=base_url,
                api_key=api_key,
                model=model,
                driver=driver,
            )

        text = raw["text"]
        vision_row = rows["vision"]
        vision = raw["vision"]
        vision_base = (vision_row["base_url"] or "").strip()
        if not _row_has_ciphertext(vision_row):
            raw["vision"] = ProviderCredentials(
                base_url=vision_base or text.base_url,
                api_key=text.api_key,
                model=text.model,
                driver=vision.driver,
            )
        elif not vision_base:
            raw["vision"] = ProviderCredentials(
                base_url=text.base_url,
                api_key=vision.api_key,
                model=vision.model,
                driver=vision.driver,
            )

        return raw


def _ensure_default_preferences(connection: sqlite3.Connection, now: str) -> None:
    row = connection.execute(
        "SELECT key FROM model_gateway_preferences WHERE key = ?",
        (_PREFERENCES_KEY,),
    ).fetchone()
    if row is not None:
        return
    connection.execute(
        """
        INSERT INTO model_gateway_preferences (key, value_json, updated_at)
        VALUES (?, ?, ?)
        """,
        (_PREFERENCES_KEY, json.dumps(DEFAULT_PREFERENCES, ensure_ascii=False), now),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _row_has_ciphertext(row: sqlite3.Row) -> bool:
    return row["api_key_ciphertext"] is not None and len(row["api_key_ciphertext"]) > 0


def _repair_video_provider_rows(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT * FROM model_gateway_providers WHERE provider = ?",
        ("video",),
    ).fetchone()
    if row is None:
        return
    stored_base = (row["base_url"] or "").strip()
    if not stored_base:
        return
    model = normalize_video_model((row["model"] or "").strip(), base_url=stored_base)
    driver = resolve_effective_video_driver((row["driver"] or "").strip(), stored_base)
    if model == (row["model"] or "").strip() and driver == (row["driver"] or "").strip():
        return
    connection.execute(
        """
        UPDATE model_gateway_providers
        SET model = ?, driver = ?, updated_at = ?
        WHERE provider = ?
        """,
        (model, driver, _now_iso(), "video"),
    )


def _status_for_provider(
    provider: str,
    row: sqlite3.Row,
    credentials: dict[str, ProviderCredentials],
) -> ProviderStatus:
    driver = (row["driver"] or "").strip() or DEFAULT_DRIVERS[provider]
    stored_base = (row["base_url"] or "").strip()
    stored_model = (row["model"] or "").strip()
    cred = credentials[provider]
    text_cred = credentials["text"]

    if provider == "video":
        configured = bool(stored_base)
        effective_driver = resolve_effective_video_driver(driver, stored_base)
        display_model = stored_model or cred.model if configured else None
        if configured and stored_base:
            display_model = normalize_video_model(display_model or "", base_url=stored_base)
        return {
            "configured": configured,
            "hasApiKey": _row_has_ciphertext(row),
            "model": display_model if configured else None,
            "driver": effective_driver,
            "baseUrl": stored_base,
        }

    if provider == "vision":
        configured = bool(cred.api_key.strip()) or bool(text_cred.api_key.strip())
        has_key = _row_has_ciphertext(row) or bool(text_cred.api_key.strip())
        display_model = stored_model or (cred.model if configured else None)
        if configured and not stored_model and text_cred.model:
            display_model = text_cred.model
        return {
            "configured": configured,
            "hasApiKey": has_key,
            "model": display_model if configured else None,
            "driver": driver,
            "baseUrl": stored_base or cred.base_url,
        }

    if provider == "videoUnderstanding":
        configured = bool(cred.api_key.strip())
        return {
            "configured": configured,
            "hasApiKey": _row_has_ciphertext(row),
            "model": stored_model or cred.model if configured else None,
            "driver": driver,
            "baseUrl": stored_base or cred.base_url,
        }

    configured = bool(cred.api_key.strip())
    return {
        "configured": configured,
        "hasApiKey": _row_has_ciphertext(row),
        "model": stored_model or cred.model if configured else None,
        "driver": driver,
        "baseUrl": stored_base or cred.base_url,
    }
