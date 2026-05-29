from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.providers.asset_reuse_provider import AssetReuseProvider
from app.providers.image_generation_provider import ImageGenerationProvider
from app.providers.material_types import (
    ArtifactRegistrar,
    CompletionStrategyProvider,
    MaterialContext,
    MaterialResult,
    ProgressEmitter,
)
from app.providers.tts_provider import TTSProvider
from app.providers.video_generation_provider import VideoGenerationProvider
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.image_gen_tool import ImageGenTool, ToolError
from app.tools.tts_tool import TTSTool
from app.tools.video_gen_tool import VideoGenTool

# Providers implemented in this plan. HyperFrames is registered in the HF plan (Wave 3).
AIGC_PROVIDERS = frozenset({"asset_reuse", "image_generation", "video_generation", "tts"})
SKIPPED_PROVIDERS = frozenset({"hyperframes_material", "text_completion", "packaging_completion"})


def filter_aigc_completion_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for action in actions:
        provider = str(action.get("provider") or action.get("strategy", ""))
        if provider in AIGC_PROVIDERS:
            filtered.append(action)
    return filtered


def expected_output_path(action: dict[str, Any], generated_root: Path) -> Path:
    slot_id = str(action["slotId"])
    provider = str(action.get("provider") or action.get("strategy", ""))
    if provider == "image_generation":
        return generated_root / f"{slot_id}.png"
    if provider == "video_generation":
        return generated_root / f"{slot_id}.mp4"
    if provider == "tts":
        return generated_root / f"{slot_id}.wav"
    if provider == "asset_reuse":
        return generated_root / f"{slot_id}-reuse.mp4"
    return generated_root / f"{slot_id}.bin"


def action_artifact_satisfied(action: dict[str, Any], generated_root: Path) -> bool:
    artifact_ref = action.get("artifactRef")
    if isinstance(artifact_ref, dict) and artifact_ref.get("uri"):
        path = Path(str(artifact_ref["uri"]))
        if path.is_file() and path.stat().st_size > 0:
            return True
    output = expected_output_path(action, generated_root)
    return output.is_file() and output.stat().st_size > 0


def register_default_providers(ctx: MaterialContext) -> None:
    ctx.providers = {
        "image_generation": ImageGenerationProvider(
            ImageGenTool(gateway=ctx.gateway, emit_progress=ctx.emit_progress)
        ),
        "video_generation": VideoGenerationProvider(
            VideoGenTool(gateway=ctx.gateway, emit_progress=ctx.emit_progress)
        ),
        "tts": TTSProvider(
            TTSTool(gateway=ctx.gateway, emit_progress=ctx.emit_progress)
        ),
        "asset_reuse": AssetReuseProvider(),
    }


def order_completion_actions(
    actions: list[dict[str, Any]],
    *,
    structure: dict[str, Any],
) -> list[dict[str, Any]]:
    importance_by_slot = {
        slot["id"]: slot.get("importance", "nice_to_have")
        for slot in structure.get("slots", [])
        if isinstance(slot, dict) and slot.get("id")
    }

    def sort_key(action: dict[str, Any]) -> tuple[int, str]:
        slot_id = str(action.get("slotId", ""))
        importance = importance_by_slot.get(slot_id, "nice_to_have")
        return (0 if importance == "must_have" else 1, slot_id)

    return sorted(actions, key=sort_key)


def execute_completion_plan(
    actions: list[dict[str, Any]],
    ctx: MaterialContext,
    *,
    fail_fast: bool = True,
    only_aigc: bool = True,
) -> list[MaterialResult]:
    """Execute completion actions via registered providers.

    When ``only_aigc`` is True (pipeline default), providers in ``SKIPPED_PROVIDERS``
    are ignored — e.g. ``hyperframes_material`` is completed in the HF plan.
    When False, unknown providers raise ``ToolError`` (used in unit tests).
    """
    results: list[MaterialResult] = []
    for action in order_completion_actions(actions, structure=ctx.structure):
        provider_name = str(action.get("provider") or action.get("strategy", ""))
        if only_aigc and provider_name in SKIPPED_PROVIDERS:
            continue
        if only_aigc and provider_name not in AIGC_PROVIDERS:
            continue
        if provider_name not in AIGC_PROVIDERS:
            raise ToolError(
                code="provider_not_registered",
                message=f"No completion provider registered for {provider_name}",
                retryable=False,
            )
        if (
            str(action["id"]) in ctx.completed_action_ids
            and action_artifact_satisfied(action, ctx.generated_root)
        ):
            continue
        provider = ctx.providers.get(provider_name)
        if provider is None:
            raise ToolError(
                code="provider_not_registered",
                message=f"Provider {provider_name} is not registered",
                retryable=False,
            )
        ctx.emit_progress("generating_material", f"Completing slot {action.get('slotId')}")
        result = provider.execute(action, ctx)
        results.append(result)
        if not result.get("ok"):
            if fail_fast:
                return results
            continue
        ctx.completed_action_ids.add(str(action["id"]))
    return results


def load_material_state(path: Path) -> tuple[VideoGenQuota, set[str]]:
    if not path.is_file():
        return VideoGenQuota(), set()
    data = json.loads(path.read_text(encoding="utf-8"))
    quota = VideoGenQuota.from_checkpoint(data.get("videoGenQuota"))
    completed = set(data.get("completedActionIds", []))
    return quota, completed


def save_material_state(
    path: Path,
    *,
    quota: VideoGenQuota,
    completed_action_ids: set[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "videoGenQuota": quota.to_checkpoint(),
        "completedActionIds": sorted(completed_action_ids),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_material_results_to_plan(
    plan: dict[str, Any],
    *,
    results: list[MaterialResult],
) -> dict[str, Any]:
    results_by_action = {str(item.get("actionId")): item for item in results if item.get("actionId")}
    by_slot: dict[str, MaterialResult] = {}
    for result in results:
        if result.get("ok") and result.get("slotId"):
            by_slot[str(result["slotId"])] = result

    updated_actions: list[dict[str, Any]] = []
    for action in plan.get("completionActions", []):
        merged = dict(action)
        result = results_by_action.get(str(action.get("id")))
        if result and result.get("ok") and result.get("artifactRef"):
            merged["artifactRef"] = result["artifactRef"]
            merged["outputRef"] = result["artifactRef"]["uri"]
        updated_actions.append(merged)
    plan["completionActions"] = updated_actions

    storyboard = plan.get("storyboard", [])
    if isinstance(storyboard, list):
        updated_storyboard: list[dict[str, Any]] = []
        for scene in storyboard:
            if not isinstance(scene, dict):
                updated_storyboard.append(scene)
                continue
            merged_scene = dict(scene)
            slot_id = str(scene.get("slotId", ""))
            result = by_slot.get(slot_id)
            if result and result.get("ok"):
                merged_scene["source"] = "generated"
                artifact = result.get("artifactRef") or {}
                if artifact.get("uri"):
                    merged_scene["visual"] = str(artifact.get("uri"))
            updated_storyboard.append(merged_scene)
        plan["storyboard"] = updated_storyboard

    plan["timeline"] = _apply_generated_sources_to_timeline(
        plan.get("timeline", {}),
        results=results,
    )
    return plan


def _apply_generated_sources_to_timeline(
    timeline: dict[str, Any],
    *,
    results: list[MaterialResult],
) -> dict[str, Any]:
    by_slot: dict[str, MaterialResult] = {}
    for result in results:
        if result.get("ok") and result.get("slotId"):
            by_slot[str(result["slotId"])] = result

    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return timeline

    for track in tracks:
        if not isinstance(track, dict):
            continue
        for clip in track.get("clips", []):
            if not isinstance(clip, dict):
                continue
            clip_id = str(clip.get("id", ""))
            slot_id = clip_id.removeprefix("clip-") if clip_id.startswith("clip-") else ""
            result = by_slot.get(slot_id)
            if not result:
                continue
            artifact = result.get("artifactRef") or {}
            uri = artifact.get("uri")
            if not uri:
                continue
            clip["sourceRef"] = uri
            clip["generatedBy"] = {
                "provider": str(result.get("provider", "")),
            }
            if track.get("type") == "text" and artifact.get("type") in {"image", "video"}:
                clip.pop("content", None)
                clip.pop("styleRef", None)
    return timeline
