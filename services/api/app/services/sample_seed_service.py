from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.services.media_paths import resolve_existing_file


def _sample_root(storage_root: Path, project_id: str, sample_id: str) -> Path:
    return storage_root / "projects" / project_id / "samples" / sample_id


def _resolve_video_path(video_uri: str | None) -> Path | None:
    if not video_uri:
        return None
    return resolve_existing_file(video_uri)


def rewrite_structure_ids(
    structure: dict[str, Any],
    *,
    project_id: str,
    sample_id: str,
) -> dict[str, Any]:
    updated = json.loads(json.dumps(structure, ensure_ascii=False))
    updated["projectId"] = project_id
    updated["sourceVideoId"] = sample_id
    updated["id"] = f"video-structure-{sample_id}"
    return updated


def import_sample_from_knowledge_entry(
    storage_root: Path,
    project_store: Any,
    knowledge_store: Any,
    *,
    target_project_id: str,
    entry: dict[str, Any],
) -> str:
    importable, reason = knowledge_store.assess_entry_importable(entry, project_store)
    if not importable:
        raise ValueError(reason or "Knowledge entry is not importable")

    source_project_id = str(entry["sourceProjectId"])
    source_sample_id = str(entry["sourceSampleId"])
    source_sample = project_store.get_sample(source_sample_id)
    if source_sample is None:
        raise ValueError("Source sample not found")

    source_video = _resolve_video_path(source_sample.get("videoUri"))
    if source_video is None:
        raise ValueError("Source sample video file missing")

    structure = knowledge_store.read_structure(str(entry["id"]))
    if structure is None:
        raise ValueError("Knowledge structure file missing")

    created = project_store.create_sample(
        project_id=target_project_id,
        source_kind="local",
        status="uploaded",
    )
    new_sample_id = str(created["id"])
    suffix = source_video.suffix or ".mp4"
    relative_video = f"samples/{new_sample_id}/source{suffix}"
    target_video = storage_root / "projects" / target_project_id / relative_video
    target_video.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_video, target_video)

    source_analysis = _sample_root(storage_root, source_project_id, source_sample_id) / "analysis"
    target_analysis = _sample_root(storage_root, target_project_id, new_sample_id) / "analysis"
    if source_analysis.is_dir():
        if target_analysis.exists():
            shutil.rmtree(target_analysis)
        shutil.copytree(source_analysis, target_analysis)

    rewritten = rewrite_structure_ids(
        structure,
        project_id=target_project_id,
        sample_id=new_sample_id,
    )
    target_analysis.mkdir(parents=True, exist_ok=True)
    (target_analysis / "video-structure.json").write_text(
        json.dumps(rewritten, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    project_store.update_sample(
        new_sample_id,
        status="analyzed",
        video_uri=str(target_video.resolve()),
        structure=rewritten,
    )
    return new_sample_id
