from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.media_paths import project_file_media_path


def _relative_keyframe_path(path_value: str, *, analysis_root: Path) -> str | None:
    raw = path_value.strip().replace("\\", "/")
    if not raw:
        return None
    candidate = Path(path_value)
    if candidate.is_file():
        try:
            rel = candidate.resolve().relative_to(analysis_root.resolve())
            return rel.as_posix()
        except ValueError:
            pass
    if raw.startswith("keyframes/"):
        return raw
    marker = "/analysis/"
    if marker in raw:
        suffix = raw.split(marker, 1)[1]
        if suffix.startswith("keyframes/"):
            return suffix
    name = Path(raw).name
    if name:
        return f"keyframes/{name}"
    return None


def load_sample_keyframes(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
) -> list[dict[str, Any]]:
    analysis_root = (
        storage_root / "projects" / project_id / "samples" / sample_id / "analysis"
    )
    keyframes_path = analysis_root / "keyframes.json"
    if not keyframes_path.is_file():
        return []

    try:
        payload = json.loads(keyframes_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    items: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        rel = _relative_keyframe_path(str(entry.get("path", "")), analysis_root=analysis_root)
        if rel is None:
            continue
        file_path = analysis_root / rel.replace("/", "\\") if "\\" in str(analysis_root) else analysis_root / rel
        if not file_path.is_file():
            file_path = analysis_root / Path(rel).name
        if not file_path.is_file():
            continue
        media_rel = f"samples/{sample_id}/analysis/{rel.replace(chr(92), '/')}"
        items.append(
            {
                "timeSec": float(entry.get("timeSec", 0.0)),
                "score": float(entry.get("score", 0.0)),
                "width": int(entry.get("width", 0) or 0),
                "height": int(entry.get("height", 0) or 0),
                "relativePath": rel.replace("\\", "/"),
                "previewUrl": project_file_media_path(project_id, media_rel),
            }
        )
    items.sort(key=lambda item: (item["timeSec"], -item["score"]))
    return items


def pick_sample_poster_url(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
) -> str | None:
    """Best-scoring keyframe JPEG for sharp list thumbnails (not video downscale)."""
    keyframes = load_sample_keyframes(
        storage_root,
        project_id=project_id,
        sample_id=sample_id,
    )
    if not keyframes:
        return None
    best = max(keyframes, key=lambda item: float(item.get("score", 0.0)))
    preview = best.get("previewUrl")
    return str(preview) if preview else None
