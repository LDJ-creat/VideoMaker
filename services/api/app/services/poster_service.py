from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.media_paths import project_file_media_path
from video.poster import generation_poster_path, sample_poster_path


def _legacy_keyframe_poster_url(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
) -> str | None:
    from app.services.sample_keyframes import load_sample_keyframes

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


def sample_poster_media_url(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
) -> str | None:
    poster_path = sample_poster_path(storage_root, project_id, sample_id)
    if poster_path.is_file() and poster_path.stat().st_size > 0:
        return project_file_media_path(project_id, f"samples/{sample_id}/poster.jpg")
    return _legacy_keyframe_poster_url(
        storage_root,
        project_id=project_id,
        sample_id=sample_id,
    )


def generation_poster_media_url(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
) -> str | None:
    poster_path = generation_poster_path(storage_root, project_id, generation_id)
    if poster_path.is_file() and poster_path.stat().st_size > 0:
        return project_file_media_path(
            project_id,
            f"renders/{generation_id}/poster.jpg",
        )
    return None


def _generation_has_render_output(
    storage_root: Path,
    project_id: str,
    generation_id: str,
) -> bool:
    output_path = (
        storage_root
        / "projects"
        / project_id
        / "renders"
        / generation_id
        / "output.mp4"
    )
    return output_path.is_file() and output_path.stat().st_size > 0


def _ordered_sample_ids_for_cover(
    project_store: Any,
    sample_selection_store: Any,
    project_id: str,
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    selection = sample_selection_store.get_selection(project_id)
    if selection:
        primary = selection.get("primarySampleId")
        if primary:
            ordered.append(str(primary))
            seen.add(str(primary))
        for sample_id in selection.get("referenceSampleIds") or []:
            sid = str(sample_id)
            if sid not in seen:
                ordered.append(sid)
                seen.add(sid)

    samples = project_store.list_samples(project_id)
    samples_sorted = sorted(
        samples,
        key=lambda item: str(item.get("createdAt") or ""),
    )
    for sample in samples_sorted:
        sid = str(sample["id"])
        if sid not in seen:
            ordered.append(sid)
            seen.add(sid)
    return ordered


def pick_project_cover_url(
    storage_root: Path,
    project_store: Any,
    sample_selection_store: Any,
    project_id: str,
) -> str | None:
    generations = project_store.list_generations_for_project(project_id)
    for generation in generations:
        generation_id = str(generation["id"])
        status = str(generation.get("status") or "")
        has_output = _generation_has_render_output(storage_root, project_id, generation_id)
        if status == "completed" or has_output:
            cover_url = generation_poster_media_url(
                storage_root,
                project_id=project_id,
                generation_id=generation_id,
            )
            if cover_url:
                return cover_url

    for sample_id in _ordered_sample_ids_for_cover(
        project_store,
        sample_selection_store,
        project_id,
    ):
        cover_url = sample_poster_media_url(
            storage_root,
            project_id=project_id,
            sample_id=sample_id,
        )
        if cover_url:
            return cover_url
    return None


def pick_category_cover_url(
    entries_ordered: list[dict[str, Any]],
    project_store: Any,
    storage_root: Path,
    *,
    assess_importable: Any,
) -> str | None:
    for entry in entries_ordered:
        if not assess_importable(entry, project_store)[0]:
            continue
        source_project_id = entry.get("sourceProjectId")
        source_sample_id = entry.get("sourceSampleId")
        if not source_project_id or not source_sample_id:
            continue
        cover_url = sample_poster_media_url(
            storage_root,
            project_id=str(source_project_id),
            sample_id=str(source_sample_id),
        )
        if cover_url:
            return cover_url
    return None
