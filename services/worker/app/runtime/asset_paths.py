from __future__ import annotations

from pathlib import Path
from typing import Any


def asset_by_id(asset_id: str, inventory: dict[str, Any]) -> dict[str, Any] | None:
    for asset in inventory.get("assets", []):
        if isinstance(asset, dict) and asset.get("id") == asset_id:
            return asset
    return None


def resolve_asset_path(asset: dict[str, Any]) -> Path | None:
    uri = str(asset.get("uri", "")).strip()
    if not uri:
        return None
    path = Path(uri)
    if path.is_file():
        return path
    if uri.startswith("file://"):
        candidate = Path(uri.removeprefix("file://"))
        if candidate.is_file():
            return candidate
    return None


def resolve_match_asset_type(
    weak_match: dict[str, Any] | None,
    inventory: dict[str, Any],
) -> str | None:
    if weak_match is None:
        return None
    asset_id = str(weak_match.get("assetId", "")).strip()
    if not asset_id:
        return None
    asset = asset_by_id(asset_id, inventory)
    if asset is None:
        return None
    return str(asset.get("type", "")).lower() or None
