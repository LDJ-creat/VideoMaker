from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException

from app.services.variant_registry import default_variant_ids


def generation_render_video_url(
    storage_root: Path,
    project_id: str,
    generation_id: str,
) -> str | None:
    """Public media URL when HyperFrames produced a non-empty output.mp4."""
    mp4 = (
        storage_root
        / "projects"
        / project_id
        / "renders"
        / generation_id
        / "output.mp4"
    )
    if not mp4.is_file() or mp4.stat().st_size <= 0:
        return None
    segments = "/".join(
        quote(part, safe="")
        for part in ("renders", generation_id, "output.mp4")
    )
    return f"/api/projects/{project_id}/media/file/{segments}"


def build_generation_plan_response(
    record: dict[str, Any],
    *,
    storage_root: Path | None = None,
) -> dict[str, Any]:
    plan = record.get("plan")
    if plan is None:
        raise HTTPException(status_code=404, detail="Generation plan not ready")

    response: dict[str, Any] = {**plan, "id": record["id"]}
    if record.get("gapReport"):
        response["gapReport"] = record["gapReport"]
    if storage_root is not None:
        video_url = generation_render_video_url(
            storage_root,
            str(record["projectId"]),
            str(record["id"]),
        )
        if video_url:
            response["renderVideoUrl"] = video_url
    return response


def build_latest_generations_response(
    records: list[dict[str, Any]],
    *,
    storage_root: Path | None = None,
) -> dict[str, Any]:
    order = default_variant_ids()
    order_index = {variant_id: index for index, variant_id in enumerate(order)}

    def sort_key(record: dict[str, Any]) -> tuple[int, str]:
        variant = str(record.get("variant") or "default")
        return (order_index.get(variant, len(order)), variant)

    generations: list[dict[str, Any]] = []
    for record in sorted(records, key=sort_key):
        variant = str(record.get("variant") or "default")
        entry: dict[str, Any] = {
            "generationId": record["id"],
            "variant": variant,
            "taskId": record.get("taskId"),
            "status": record.get("status"),
        }
        if record.get("plan") is not None:
            plan = build_generation_plan_response(
                record,
                storage_root=storage_root,
            )
            entry["variant"] = record.get("variant") or plan.get("variant") or variant
            entry["plan"] = plan
            if storage_root is not None:
                video_url = generation_render_video_url(
                    storage_root,
                    str(record["projectId"]),
                    str(record["id"]),
                )
                if video_url:
                    entry["renderVideoUrl"] = video_url
        generations.append(entry)
    return {"generations": generations}
