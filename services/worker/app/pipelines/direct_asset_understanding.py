from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import Any

from app.pipelines.brief_structure_hints import structure_generation_hints
from app.agents.runner import AgentRunner
from app.pipelines.user_brief import normalize_user_brief
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract

TEXT_MIME_BY_SUFFIX = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}

_ROUTE_WARNING = "analysis_route:direct_multimodal"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def resolve_asset_path(storage_root: Path, project_id: str, uri: str) -> Path | None:
    candidate = Path(uri)
    if candidate.is_file():
        return candidate.resolve()
    if uri.startswith("storage://"):
        candidate = storage_root / uri.removeprefix("storage://")
    elif uri.startswith("projects/"):
        candidate = storage_root / uri
    else:
        candidate = storage_root / "projects" / project_id / uri
    return candidate.resolve() if candidate.is_file() else None


def read_text_asset_content(path: Path, *, max_chars: int | None = None) -> str:
    limit = max_chars if max_chars is not None else _env_int("VIDEOMAKER_ASSET_TEXT_MAX_CHARS", 8000)
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Text asset is not valid UTF-8: {path}") from exc
    text = raw.strip()
    if len(text) <= limit:
        return text
    return text[:limit]


def _video_mime(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed if guessed and guessed.startswith("video/") else "video/mp4"


def _image_mime(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed if guessed and guessed.startswith("image/") else "image/jpeg"


def _media_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def _assert_video_limits(path: Path, *, duration_sec: float | None) -> None:
    max_mb = _env_float("VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_MB", 50)
    max_sec = _env_float("VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_SEC", 300)
    size_mb = _media_size_mb(path)
    if size_mb > max_mb:
        raise ValueError(f"Asset video {size_mb:.1f}MB exceeds limit {max_mb}MB")
    if duration_sec is not None and float(duration_sec) > max_sec:
        raise ValueError(f"Asset duration {duration_sec}s exceeds limit {max_sec}s")


class PackedMediaItem:
    def __init__(
        self,
        *,
        asset_id: str,
        asset_type: str,
        path: Path | None,
        text_content: str = "",
        duration_sec: float | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ) -> None:
        self.asset_id = asset_id
        self.asset_type = asset_type
        self.path = path
        self.text_content = text_content
        self.duration_sec = duration_sec
        self.description = description
        self.tags = list(tags or [])
        self.size_mb = _media_size_mb(path) if path is not None else 0.0


def pack_asset_media_items(
    *,
    storage_root: Path,
    project_id: str,
    assets: list[dict[str, Any]],
) -> list[PackedMediaItem]:
    items: list[PackedMediaItem] = []
    text_limit = _env_int("VIDEOMAKER_ASSET_TEXT_MAX_CHARS", 8000)
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("id", ""))
        asset_type = str(asset.get("type", ""))
        uri = str(asset.get("uri", ""))
        media_path = resolve_asset_path(storage_root, project_id, uri)
        text_content = ""
        if asset_type == "text" and media_path is not None:
            text_content = read_text_asset_content(media_path, max_chars=text_limit)
        elif asset_type in {"video", "image"} and media_path is None:
            continue
        duration = asset.get("durationSec")
        duration_sec = float(duration) if duration is not None else None
        if asset_type == "video" and media_path is not None:
            _assert_video_limits(media_path, duration_sec=duration_sec)
        items.append(
            PackedMediaItem(
                asset_id=asset_id,
                asset_type=asset_type,
                path=media_path if asset_type in {"video", "image"} else None,
                text_content=text_content,
                duration_sec=duration_sec,
                description=str(asset.get("description") or ""),
                tags=list(asset.get("tags") or []),
            )
        )
    return items


def estimate_payload_limits(items: list[PackedMediaItem]) -> dict[str, Any]:
    max_count = _env_int("VIDEOMAKER_ASSET_UNDERSTANDING_MAX_MEDIA_COUNT", 6)
    max_total_mb = _env_float("VIDEOMAKER_ASSET_UNDERSTANDING_MAX_TOTAL_MB", 80)
    media_items = [item for item in items if item.asset_type in {"video", "image"}]
    total_mb = sum(item.size_mb for item in media_items)
    return {
        "mediaCount": len(media_items),
        "totalMb": total_mb,
        "maxCount": max_count,
        "maxTotalMb": max_total_mb,
        "needsBatch": len(media_items) > max_count or total_mb > max_total_mb,
    }


def split_media_batches(items: list[PackedMediaItem]) -> list[list[PackedMediaItem]]:
    max_count = _env_int("VIDEOMAKER_ASSET_UNDERSTANDING_MAX_MEDIA_COUNT", 6)
    max_total_mb = _env_float("VIDEOMAKER_ASSET_UNDERSTANDING_MAX_TOTAL_MB", 80)
    text_items = [item for item in items if item.asset_type == "text"]
    media_items = [item for item in items if item.asset_type in {"video", "image"}]

    if not media_items:
        return [items]

    batches: list[list[PackedMediaItem]] = []
    current: list[PackedMediaItem] = []
    current_mb = 0.0

    for item in media_items:
        would_exceed = len(current) >= max_count or (
            current and current_mb + item.size_mb > max_total_mb
        )
        if would_exceed:
            batches.append([*text_items, *current])
            current = [item]
            current_mb = item.size_mb
        else:
            current.append(item)
            current_mb += item.size_mb

    if current:
        batches.append([*text_items, *current])
    return batches


def build_agent_text_message(
    *,
    inventory: dict[str, Any],
    packed_items: list[PackedMediaItem],
    video_structure: dict[str, Any] | None,
) -> dict[str, Any]:
    brief = normalize_user_brief(inventory.get("userBrief", {}))
    assets_manifest: list[dict[str, Any]] = []
    for item in packed_items:
        entry: dict[str, Any] = {
            "id": item.asset_id,
            "type": item.asset_type,
            "description": item.description,
            "tags": item.tags,
        }
        if item.duration_sec is not None:
            entry["durationSec"] = item.duration_sec
        if item.text_content:
            entry["textContent"] = item.text_content
        assets_manifest.append(entry)

    message: dict[str, Any] = {
        "projectId": inventory.get("projectId"),
        "userBrief": brief,
        "assets": assets_manifest,
        "baselineFacts": list(inventory.get("extractedFacts") or []),
    }
    message.update(structure_generation_hints(video_structure))
    return message


def build_media_parts(packed_items: list[PackedMediaItem]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for item in packed_items:
        if item.path is None:
            continue
        if item.asset_type == "video":
            video_b64 = base64.b64encode(item.path.read_bytes()).decode("ascii")
            mime = _video_mime(item.path)
            parts.append(
                {
                    "type": "video_url",
                    "video_url": {"url": f"data:{mime};base64,{video_b64}"},
                }
            )
        elif item.asset_type == "image":
            image_b64 = base64.b64encode(item.path.read_bytes()).decode("ascii")
            mime = _image_mime(item.path)
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                }
            )
    return parts


def merge_asset_inventories(
    baseline: dict[str, Any],
    partials: list[dict[str, Any]],
    *,
    route: str,
) -> dict[str, Any]:
    merged = dict(baseline)
    facts: list[dict[str, Any]] = list(baseline.get("extractedFacts") or [])
    seen_facts = {(str(f.get("kind")), str(f.get("text"))) for f in facts if isinstance(f, dict)}
    moments: list[dict[str, Any]] = []
    seen_moment_ids: set[str] = set()
    assets_by_id = {
        str(asset.get("id")): dict(asset)
        for asset in baseline.get("assets", [])
        if isinstance(asset, dict) and asset.get("id")
    }

    tone_summary: str | None = None
    for partial in partials:
        if not isinstance(partial, dict):
            continue
        if partial.get("toneSummary") and not tone_summary:
            tone_summary = str(partial["toneSummary"])
        for fact in partial.get("extractedFacts") or []:
            if not isinstance(fact, dict):
                continue
            key = (str(fact.get("kind")), str(fact.get("text")))
            if key in seen_facts:
                continue
            seen_facts.add(key)
            facts.append(dict(fact))
        for moment in partial.get("candidateMoments") or []:
            if not isinstance(moment, dict):
                continue
            moment_id = str(moment.get("id", ""))
            if not moment_id or moment_id in seen_moment_ids:
                continue
            seen_moment_ids.add(moment_id)
            moments.append(dict(moment))
        for asset in partial.get("assets") or []:
            if not isinstance(asset, dict):
                continue
            asset_id = str(asset.get("id", ""))
            if asset_id not in assets_by_id:
                continue
            target = assets_by_id[asset_id]
            if asset.get("description"):
                target["description"] = str(asset["description"])
            tags = list(target.get("tags") or [])
            for tag in asset.get("tags") or []:
                tag_text = str(tag).strip()
                if tag_text and tag_text not in tags:
                    tags.append(tag_text)
            target["tags"] = tags

    moments.sort(key=lambda item: float(item.get("highlightScore", 0.0)), reverse=True)
    merged["extractedFacts"] = facts
    merged["candidateMoments"] = moments[:5]
    merged["assets"] = list(assets_by_id.values())
    merged["assetUnderstandingRoute"] = route
    warnings = list(merged.get("assetUnderstandingWarnings") or [])
    if _ROUTE_WARNING not in warnings:
        warnings.append(_ROUTE_WARNING)
    merged["assetUnderstandingWarnings"] = warnings

    if tone_summary:
        brief = normalize_user_brief(merged.get("userBrief", {}))
        if not brief.get("tone"):
            brief["tone"] = tone_summary
        merged["userBrief"] = brief

    validation = validate_contract("asset-inventory", merged)
    if not validation.valid:
        raise ValueError(f"Invalid AssetInventory payload: {validation.errors}")
    return merged


def run_direct_asset_understanding(
    runner: AgentRunner,
    *,
    inventory: dict[str, Any],
    context: TaskContext,
    generation_id: str | None = None,
    video_structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.agents.asset_inventory_analyst import run_asset_inventory_analyst

    context.emit_event(
        stage="analyzing_assets",
        progress=12,
        message="Direct multimodal user asset understanding",
    )

    normalized = dict(inventory)
    normalized["userBrief"] = normalize_user_brief(inventory.get("userBrief", {}))
    storage_root = Path(context.storage_root)
    project_id = str(normalized["projectId"])
    packed = pack_asset_media_items(
        storage_root=storage_root,
        project_id=project_id,
        assets=list(normalized.get("assets") or []),
    )
    limits = estimate_payload_limits(packed)
    batches = [packed] if not limits["needsBatch"] else split_media_batches(packed)
    route = "direct_multimodal_batched" if len(batches) > 1 else "direct_multimodal"

    partials: list[dict[str, Any]] = []
    for index, batch in enumerate(batches):
        context.emit_event(
            stage="analyzing_assets",
            progress=12 + min(index, 3),
            message=f"Direct multimodal asset batch {index + 1}/{len(batches)}",
        )
        partials.append(
            run_asset_inventory_analyst(
                runner,
                inventory=normalized,
                packed_items=batch,
                context=context,
                generation_id=generation_id,
                video_structure=video_structure,
                progress=15 + index,
            )
        )

    return merge_asset_inventories(normalized, partials, route=route)


def apply_tone_summary(inventory: dict[str, Any], tone_summary: str | None) -> dict[str, Any]:
    if not tone_summary:
        return inventory
    merged = dict(inventory)
    brief = normalize_user_brief(merged.get("userBrief", {}))
    if not brief.get("tone"):
        brief["tone"] = tone_summary
    merged["userBrief"] = brief
    return merged
