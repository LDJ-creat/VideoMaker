from __future__ import annotations

from pathlib import Path


def sample_media_path(project_id: str, sample_id: str) -> str:
    return f"/api/projects/{project_id}/media/samples/{sample_id}"


def asset_media_path(project_id: str, asset_id: str) -> str:
    return f"/api/projects/{project_id}/media/assets/{asset_id}"


def resolve_existing_file(uri: str) -> Path | None:
    path = Path(uri)
    if path.is_file():
        return path.resolve()
    return None
